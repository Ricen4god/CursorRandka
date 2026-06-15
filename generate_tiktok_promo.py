#!/usr/bin/env python3
"""Generate TikTok promo video for @RandkaaPL_bot — minimal deps."""

import asyncio
import math
import os
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

# --- Paths ---
DESKTOP = Path(r"C:\Users\nazar\OneDrive\Рабочий стол")
OUTPUT = DESKTOP / "randka_tiktok_promo.mp4"
WORK_DIR = DESKTOP / "CursorRandka" / "tiktok_promo_assets"
WORK_DIR.mkdir(parents=True, exist_ok=True)

AVATAR = DESKTOP / "randkapl_bot_avatar.png"
FLYER = DESKTOP / "randkapl_flyer.png"
PHOTO_DIRS = [DESKTOP / "randkabot", DESKTOP]

W, H = 1080, 1920
FPS = 30

SCRIPT = (
    "Szukasz kogoś w swoim mieście? "
    "Randka PL — randki w Telegramie! "
    "Przesuwaj profile, lajkuj i znajdź matcha. "
    "Piętnaście miast w całej Polsce. "
    "Wejdź teraz — szukaj bota RandkaaPL_bot w Telegramie!"
)

SCENES = [
    {"text": "Szukasz kogoś\nw swoim mieście? 💕", "sub": "Randka PL", "duration": 3.5},
    {"text": "Przesuwaj ❤️\nLajkuj 💕\nMatch!", "sub": "Jak Tinder, ale w Telegramie", "duration": 4.0},
    {"text": "15 miast\nw Polsce 🇵🇱", "sub": "Warszawa • Kraków • Wrocław i więcej", "duration": 4.0},
    {"text": "@RandkaaPL_bot", "sub": "Szukaj w Telegramie → START", "duration": 4.5},
]

GRAD_TOP = (255, 120, 160)
GRAD_BOT = (180, 50, 100)
DEEP_PINK = (220, 40, 100)
WHITE = (255, 255, 255)


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def collect_photos() -> list[Path]:
    photos = []
    for d in PHOTO_DIRS:
        if not d.exists():
            continue
        for i in range(1, 21):
            p = d / f"{i}.jpg"
            if p.exists():
                photos.append(p)
    seen, unique = set(), []
    for p in photos:
        k = str(p.resolve())
        if k not in seen:
            seen.add(k)
            unique.append(p)
    return unique[:8]


def make_gradient_bg() -> Image.Image:
    base = Image.new("RGB", (W, H))
    px = base.load()
    for y in range(H):
        t = y / H
        r = int(GRAD_TOP[0] * (1 - t) + GRAD_BOT[0] * t)
        g = int(GRAD_TOP[1] * (1 - t) + GRAD_BOT[1] * t)
        b = int(GRAD_TOP[2] * (1 - t) + GRAD_BOT[2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return base


def fit_cover(img: Image.Image, tw: int, th: int) -> Image.Image:
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def draw_rounded_card(base: Image.Image, card: Image.Image, box: tuple, radius: int = 40):
    x, y, cw, ch = box
    card = fit_cover(card, cw, ch)
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw, ch), radius=radius, fill=255)
    base.paste(card, (x, y), mask)


def draw_text_centered(draw, text, y_center, font, fill=WHITE, shadow=True):
    lines = text.split("\n")
    metrics = [draw.textbbox((0, 0), ln, font=font) for ln in lines]
    heights = [m[3] - m[1] for m in metrics]
    widths = [m[2] - m[0] for m in metrics]
    total_h = sum(heights) + (len(lines) - 1) * 20
    y = y_center - total_h // 2
    for i, line in enumerate(lines):
        x = (W - widths[i]) // 2
        if shadow:
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += heights[i] + 20


def render_scene_frame(scene_idx, progress, photos, avatar, flyer) -> Image.Image:
    base = make_gradient_bg()
    draw = ImageDraw.Draw(base)
    title_font = get_font(72, bold=True)
    sub_font = get_font(42)
    cta_font = get_font(56, bold=True)
    scene = SCENES[scene_idx]

    if scene_idx == 0:
        if flyer:
            y = 280 + int(20 * math.sin(progress * math.pi * 2))
            draw_rounded_card(base, flyer, ((W - 900) // 2, y, 900, 1100), 50)
        elif photos:
            draw_rounded_card(base, Image.open(photos[0]).convert("RGB"), (90, 300, 900, 1100), 50)
        draw_text_centered(draw, scene["text"], 1700, title_font)
        draw_text_centered(draw, scene["sub"], 1820, sub_font, fill=(255, 220, 235))

    elif scene_idx == 1:
        if photos:
            for j, off in enumerate([-120, 0, 120]):
                idx = (j + int(progress * 3)) % len(photos)
                card = fit_cover(Image.open(photos[idx]).convert("RGB"), 700, 900)
                card = card.rotate(off / 15.0, resample=Image.Resampling.BICUBIC, expand=True)
                cx = W // 2 + off + int(80 * math.sin(progress * math.pi))
                cw, ch = card.size
                base.paste(card, (cx - cw // 2, 750 - ch // 2))
        like_x = W // 2 + 200 + int(30 * progress)
        draw.ellipse((like_x - 50, 1350, like_x + 50, 1450), fill=(80, 220, 100))
        draw.text((like_x - 18, 1375), "❤", font=get_font(48), fill=WHITE)
        draw_text_centered(draw, scene["text"], 1580, get_font(60, bold=True))
        draw_text_centered(draw, scene["sub"], 1750, sub_font, fill=(255, 220, 235))

    elif scene_idx == 2:
        cities = ["Warszawa", "Kraków", "Wrocław", "Gdańsk", "Poznań", "Łódź"]
        grid_photos = photos[:6] if len(photos) >= 6 else photos
        for i, photo_path in enumerate(grid_photos):
            col, row = i % 2, i // 2
            px, py = 80 + col * 480, 350 + row * 380
            draw_rounded_card(base, Image.open(photo_path).convert("RGB"), (px, py, 440, 340), 30)
            draw.rounded_rectangle((px, py + 280, px + 440, py + 340), radius=20, fill=DEEP_PINK)
            draw.text((px + 20, py + 292), f"📍 {cities[i % len(cities)]}", font=get_font(32, bold=True), fill=WHITE)
        draw_text_centered(draw, scene["text"], 200, title_font)
        draw_text_centered(draw, scene["sub"], 1680, sub_font, fill=(255, 220, 235))

    elif scene_idx == 3:
        if avatar:
            av = avatar.resize((280, 280), Image.Resampling.LANCZOS)
            mask = Image.new("L", (280, 280), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 280, 280), fill=255)
            base.paste(av, ((W - 280) // 2, 420), mask)
        pulse = 1.0 + 0.05 * math.sin(progress * math.pi * 4)
        box_w, box_h = int(920 * pulse), 160
        bx, by = (W - box_w) // 2, 900
        draw.rounded_rectangle((bx, by, bx + box_w, by + box_h), radius=40, fill=DEEP_PINK)
        draw_text_centered(draw, "@RandkaaPL_bot", by + box_h // 2, cta_font)
        draw_text_centered(draw, "RANDKA PL", 780, get_font(90, bold=True))
        draw_text_centered(draw, scene["sub"], 1120, sub_font, fill=(255, 220, 235))
        draw_text_centered(draw, "💕 Telegram Dating 💕", 1750, get_font(44))

    return base


def get_media_duration(path: Path) -> float:
    result = subprocess.run(
        [ffmpeg_exe(), "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for line in result.stderr.splitlines():
        if "Duration:" in line:
            dur_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = dur_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 22.0


async def generate_voiceover(text: str, out_path: Path) -> float:
    communicate = edge_tts.Communicate(text, "pl-PL-ZofiaNeural", rate="+8%")
    await communicate.save(str(out_path))
    return get_media_duration(out_path)


def generate_bg_music(duration: float, out_path: Path, sample_rate: int = 44100):
    n = int(sample_rate * duration)
    freqs = [220.0, 277.18, 329.63]
    samples = []
    for i in range(n):
        t = i / sample_rate
        env = min(t / 1.5, 1.0) * min((duration - t) / 1.5, 1.0)
        val = sum(0.04 * math.sin(2 * math.pi * f * t) for f in freqs)
        val *= env * (0.85 + 0.15 * math.sin(2 * math.pi * 0.5 * t))
        val = max(-1.0, min(1.0, val)) * 0.35
        samples.append(int(val * 32767))
    with wave.open(str(out_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def render_frames_to_video(photos, voice_duration: float) -> Path:
    total_scene_dur = sum(s["duration"] for s in SCENES)
    scale = voice_duration / total_scene_dur
    scene_durations = [s["duration"] * scale for s in SCENES]

    avatar = Image.open(AVATAR).convert("RGBA") if AVATAR.exists() else None
    flyer = Image.open(FLYER).convert("RGB") if FLYER.exists() else None

    frames_dir = WORK_DIR / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir()

    idx = 0
    for scene_idx, dur in enumerate(scene_durations):
        n_frames = max(1, int(dur * FPS))
        for f in range(n_frames):
            progress = f / max(n_frames - 1, 1)
            frame = render_scene_frame(scene_idx, progress, photos, avatar, flyer)
            frame.save(frames_dir / f"frame_{idx:05d}.jpg", quality=92)
            idx += 1

    silent_video = WORK_DIR / "silent_video.mp4"
    subprocess.run(
        [
            ffmpeg_exe(), "-y",
            "-framerate", str(FPS),
            "-i", str(frames_dir / "frame_%05d.jpg"),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(silent_video),
        ],
        check=True, capture_output=True,
    )
    return silent_video


def mux_final(silent_video: Path, voice_path: Path, music_path: Path, out_path: Path):
    subprocess.run(
        [
            ffmpeg_exe(), "-y",
            "-i", str(silent_video),
            "-i", str(voice_path),
            "-i", str(music_path),
            "-filter_complex",
            "[1:a]volume=1.0[voice];[2:a]volume=0.12[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest",
            str(out_path),
        ],
        check=True, capture_output=True,
    )


async def main():
    print("=== Randka PL TikTok Promo Generator ===")
    photos = collect_photos()
    print(f"Photos: {len(photos)} | Avatar: {AVATAR.exists()} | Flyer: {FLYER.exists()}")

    voice_path = WORK_DIR / "voiceover.mp3"
    print("Generating voiceover...")
    voice_duration = await generate_voiceover(SCRIPT, voice_path)
    print(f"Voice: {voice_duration:.1f}s")

    print("Rendering frames...")
    silent_video = render_frames_to_video(photos, voice_duration)

    music_path = WORK_DIR / "bg_music.wav"
    print("Generating music...")
    generate_bg_music(voice_duration + 0.5, music_path)

    temp_out = WORK_DIR / "final_mux.mp4"
    print("Muxing...")
    mux_final(silent_video, voice_path, music_path, temp_out)
    shutil.copy2(temp_out, OUTPUT)

    dur = get_media_duration(OUTPUT)
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"\nDONE: {OUTPUT}")
    print(f"Duration: {dur:.1f}s | Size: {size_mb:.1f} MB | {W}x{H}@{FPS}fps")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
