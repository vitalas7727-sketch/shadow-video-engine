# Shadow Video Engine — Prototype 0.1

A tiny cloud video-rendering engine for Android-first workflows. The first prototype turns one image into a 720p cinematic MP4 with slow camera zoom/pan, atmospheric fog, floating particles, and a title. Optional music can be added as `assets/music.mp3`.

## Run in GitHub Actions (phone-friendly)
1. Create a **new public** GitHub repository named `shadow-video-engine`. Do not modify the Forge of Shadows repo.
2. Upload these project files to the new repository (keep `.github/workflows/render.yml`).
3. Put a scene image at `assets/scene.png` (replace the included sample image). Optional: add `assets/music.mp3`.
4. Open **Actions → Render Shadow Video → Run workflow**. Choose title, duration (5–30 seconds), zoom (1.0–1.5), and pan (-1..1).
5. Wait for the green run, open it, and download the artifact `shadow-video-N`. The MP4 is available inside the ZIP.

## Defaults
- 1280x720 (720p), 24 fps, H.264 MP4
- Render duration: 5 seconds
- `zoom=1.08`; pan defaults are subtle
- Run manually only (no automatic rendering on every commit)
- Artifact retention: 2 days to conserve storage

## Optional music
Add an audio file named `assets/music.mp3`. The renderer loops it and muxes it into the final video. Keep audio rights clear for your intended use.

## Local render
Requires Python 3.10+, Pillow, FFmpeg, and ffprobe.
```bash
pip install -r requirements.txt
python render.py --image assets/scene.png --output output/demo.mp4 --title "Into the Shadow" --duration 5 --zoom 1.12 --pan-x 0.12 --pan-y -0.04
```

## Prototype boundaries
- 30 seconds max per run for predictable render time
- Single still image input; no character rig or generative video model
- Fog/particles are procedural overlays; later iterations can add layered parallax, transitions, multi-scene timeline, and sound effects
- For GitHub Free, public repositories have free standard runner usage; artifacts and private-repository usage have plan limits. Check current account billing/settings before scaling.
