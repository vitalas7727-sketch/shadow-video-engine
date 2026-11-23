#!/usr/bin/env python3
"""Cloud AI video pipeline: image -> Kling 2.6 Pro -> Russian TTS -> final audio mix."""
from __future__ import annotations
import asyncio, os, subprocess, sys
from pathlib import Path
import requests
import edge_tts
import fal_client

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd[:8]), "...", flush=True)
    subprocess.run(cmd, check=True)

async def make_voice(text: str, voice: str, mood: str, path: Path) -> None:
    rate, pitch, volume = "+0%", "-2Hz", "+0%"
    if mood == "dramatic":
        rate, pitch, volume = "-12%", "-4Hz", "+8%"
    elif mood == "slow":
        rate, pitch = "-18%", "-2Hz"
    await edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch, volume=volume).save(str(path))

def main() -> None:
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        raise RuntimeError("GitHub Secret FAL_KEY is missing. Add it in Settings -> Secrets and variables -> Actions.")
    image_path = ROOT / os.environ["IMAGE_PATH"]
    if not image_path.is_file():
        raise FileNotFoundError(f"Source image not found: {image_path}")
    prompt = os.environ["VIDEO_PROMPT"].strip()
    duration = os.environ.get("VIDEO_DURATION", "5")
    if duration not in {"5", "10"}:
        raise ValueError("Duration must be 5 or 10 seconds.")
    print("Uploading source image to fal storage...", flush=True)
    image_url = fal_client.upload_file(str(image_path))
    print("Submitting Kling 2.6 Pro image-to-video request...", flush=True)
    result = fal_client.subscribe(
        "fal-ai/kling-video/v2.6/pro/image-to-video",
        arguments={
            "prompt": prompt,
            "start_image_url": image_url,
            "duration": duration,
            "generate_audio": False,
            "negative_prompt": "cartoon, illustration, anime, plastic CGI, distorted anatomy, extra limbs, flicker, jitter, morphing, text, subtitles, watermark, low resolution, blurry details",
            "cfg_scale": 0.5,
        },
        with_logs=True,
    )
    video_url = result.get("video", {}).get("url")
    if not video_url:
        raise RuntimeError(f"fal response did not contain video.url: {result}")
    raw_video = OUT / "ai-video.mp4"
    response = requests.get(video_url, timeout=180)
    response.raise_for_status()
    raw_video.write_bytes(response.content)
    print(f"AI video downloaded: {len(response.content)} bytes", flush=True)

    title = os.environ.get("VIDEO_TITLE", "Shadow Video Engine").strip()
    narration = os.environ.get("NARRATION", "").strip()
    voice = os.environ.get("VOICE", "ru-RU-DmitryNeural")
    mood = os.environ.get("VOICE_MOOD", "normal")
    music_value = os.environ.get("MUSIC_PATH", "").strip()
    music_path = ROOT / music_value if music_value else None
    if music_path and not music_path.is_file():
        raise FileNotFoundError(f"Music file not found: {music_path}")

    voice_path = OUT / "voice.mp3"
    if narration:
        print("Synthesizing Russian neural voice...", flush=True)
        asyncio.run(make_voice(narration, voice, mood, voice_path))
        voice_probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(voice_path)],
            capture_output=True, text=True, check=True
        )
        voice_seconds = float(voice_probe.stdout.strip())
        if voice_seconds > seconds * 1.65:
            raise RuntimeError(
                f"Voice-over is too long ({voice_seconds:.1f}s) for a {seconds:.0f}s clip. "
                "Shorten the narration in the app and run again."
            )
        if voice_seconds > seconds:
            fitted_voice = OUT / "voice-fitted.mp3"
            tempo = min(1.65, voice_seconds / seconds)
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice_path),
                 "-filter:a", f"atempo={tempo:.3f}", "-q:a", "3", str(fitted_voice)])
            fitted_voice.replace(voice_path)

    # Build a restrained cinematic ambience bed; user music can be mixed on top.
    seconds = float(duration)
    ambience = OUT / "ambience.wav"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.035:duration={seconds}:sample_rate=48000",
        "-f", "lavfi", "-i", f"sine=frequency=55:sample_rate=48000:duration={seconds}",
        "-filter_complex", "[0:a]lowpass=f=420,highpass=f=45,volume=0.34[n];[1:a]volume=0.045[b];[n][b]amix=inputs=2:duration=longest,afade=t=out:st="+str(max(0,seconds-1)) + ":d=1[a]",
        "-map", "[a]", "-c:a", "pcm_s16le", str(ambience)
    ])

    inputs = ["-i", str(raw_video), "-i", str(ambience)]
    mix_parts = ["[1:a]volume=0.45[amb]"]
    audio_labels = ["[amb]"]
    idx = 2
    if narration:
        inputs += ["-i", str(voice_path)]
        mix_parts.append(f"[{idx}:a]highpass=f=90,lowpass=f=12000,volume=1.25[vox]")
        audio_labels.append("[vox]")
        idx += 1
    if music_path:
        inputs += ["-i", str(music_path)]
        mix_parts.append(f"[{idx}:a]volume=0.22[music]")
        audio_labels.append("[music]")
    mix_parts.append("".join(audio_labels) + f"amix=inputs={len(audio_labels)}:duration=first:dropout_transition=2,alimiter=limit=0.95[aout]")
    final = OUT / "final-video.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + [
        "-filter_complex", ";".join(mix_parts),
        "-map", "0:v:0", "-map", "[aout]", "-t", str(seconds),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(final)
    ]
    run(cmd)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-show_entries", "stream=codec_type,codec_name,width,height", "-of", "json", str(final)], capture_output=True, text=True, check=True)
    print("FINAL VIDEO:", probe.stdout, flush=True)
    print(f"PROJECT TITLE: {title}", flush=True)

if __name__ == "__main__":
    main()
