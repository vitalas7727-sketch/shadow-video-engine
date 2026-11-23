#!/usr/bin/env python3
"""Shadow Video Engine prototype: still image -> cinematic MP4 (720p)."""
from __future__ import annotations
import argparse, math, subprocess, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


W, H = 1280, 720
FPS = 24

def load_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()

def cover_crop(img: Image.Image, w: int, h: int, zoom: float, pan_x: float, pan_y: float):
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height) * zoom
    rw, rh = max(w, int(img.width * scale)), max(h, int(img.height * scale))
    img = img.resize((rw, rh), Image.Resampling.LANCZOS)
    extra_x, extra_y = rw - w, rh - h
    # pan range is -1..1; positive values move the camera toward the right/bottom
    cx = extra_x * (0.5 + pan_x * 0.45)
    cy = extra_y * (0.5 + pan_y * 0.45)
    left = max(0, min(extra_x, int(cx)))
    top = max(0, min(extra_y, int(cy)))
    return img.crop((left, top, left + w, top + h))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", default="assets/scene.png")
    p.add_argument("--output", default="output/shadow-video.mp4")
    p.add_argument("--title", default="SHADOW VIDEO ENGINE")
    p.add_argument("--duration", type=float, default=5.0)
    p.add_argument("--zoom", type=float, default=1.08)
    p.add_argument("--pan-x", type=float, default=0.08)
    p.add_argument("--pan-y", type=float, default=-0.04)
    p.add_argument("--music", default="assets/music.mp3")
    args = p.parse_args()
    if args.duration <= 0 or args.duration > 30:
        p.error("duration must be between 0 and 30 seconds for this prototype")
    if args.zoom < 1.0 or args.zoom > 1.5:
        p.error("zoom must be between 1.0 and 1.5")
    if not -1.0 <= args.pan_x <= 1.0 or not -1.0 <= args.pan_y <= 1.0:
        p.error("pan-x and pan-y must be between -1 and 1")
    src = Path(args.image)
    if not src.exists():
        p.error(f"image not found: {src}")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(args.duration * FPS))
    base = Image.open(src).convert("RGB")
    title_font = load_font(42, True)
    subtitle_font = load_font(22)
    rng = random.Random(842)
    fog_blobs = [(rng.randint(-100, W+100), rng.randint(180, H+120), rng.randint(70, 190), rng.randint(35, 90), rng.random()*math.tau) for _ in range(24)]
    particles = [(rng.uniform(0,W), rng.uniform(0,H), rng.uniform(0.4,1.5), rng.uniform(0,math.tau)) for _ in range(45)]
    vf = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(vf, stdin=subprocess.PIPE)
    try:
        for i in range(frames):
            t = i / max(1, frames-1)
            eased = t*t*(3-2*t)
            z = 1.0 + (args.zoom - 1.0) * eased
            frame = cover_crop(base, W, H, z, args.pan_x * eased, args.pan_y * eased)
            # Atmospheric darkening and a soft vignette-like gradient.
            shade = Image.new("RGB", (W,H), (5, 9, 18))
            frame = Image.blend(frame, shade, 0.18)
            overlay = Image.new("RGBA", (W,H), (0,0,0,0))
            od = ImageDraw.Draw(overlay)
            for x, y, rx, ry, phase in fog_blobs:
                yy = y + math.sin(t*2.4 + phase)*22
                xx = x + t*35 + math.cos(t*1.6 + phase)*12
                alpha = int(14 + 12*(0.5+0.5*math.sin(t*2+phase)))
                od.ellipse((xx-rx, yy-ry, xx+rx, yy+ry), fill=(150,180,210,alpha))
            for x, y, speed, phase in particles:
                px = (x + t*24*speed) % W
                py = (y - t*18*speed) % H
                pulse = 0.5 + 0.5*math.sin(t*5+phase)
                r = 1 + pulse*2
                od.ellipse((px-r,py-r,px+r,py+r), fill=(170,220,255,int(60+90*pulse)))
            overlay = overlay.filter(ImageFilter.GaussianBlur(18))
            frame = Image.alpha_composite(frame.convert("RGBA"), overlay)
            d = ImageDraw.Draw(frame)
            # Gentle title fade in/out.
            fade = min(1.0, t*5, (1-t)*5)
            alpha = int(230 * max(0, fade))
            title = args.title.strip()
            box = d.textbbox((0,0), title, font=title_font)
            tw = box[2]-box[0]
            d.text(((W-tw)//2, H-115), title, font=title_font, fill=(235,245,255,alpha), stroke_width=1, stroke_fill=(20,30,45,alpha))
            sub = "CINEMATIC SCENE • PROTOTYPE"
            sb = d.textbbox((0,0), sub, font=subtitle_font)
            sw = sb[2]-sb[0]
            d.text(((W-sw)//2, H-62), sub, font=subtitle_font, fill=(130,190,225,int(alpha*0.8)))
            proc.stdin.write(frame.convert("RGB").tobytes())
        proc.stdin.close()
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"FFmpeg video render exited with {code}")
    except Exception:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        raise
    music = Path(args.music)
    if music.exists():
        mux = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-stream_loop", "-1", "-i", str(music), "-t", str(args.duration), "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out.with_name(out.stem+"_audio.mp4") )]
        subprocess.run(mux, check=True)
        out.with_name(out.stem+"_audio.mp4").replace(out)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(out)], capture_output=True, text=True, check=True)
    print(f"DONE: {out} | duration={probe.stdout.strip()}s | frames={frames} | resolution={W}x{H} | fps={FPS}")

if __name__ == "__main__":
    main()
