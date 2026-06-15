"""Generate TikTok promo video for RandkaaPL_bot."""

import asyncio
import os
from pathlib import Path

import edge_tts
import numpy as np
from PIL import Image
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
)

DESKTOP = Path(os.environ["USERPROFILE"]) / "OneDrive" / "\u0420\u0430\u0431\u043e\u0447\u0438\u0439 \u0441\u0442\u043e\u043b"
RANDKABOT = DESKTOP / "randkabot"
OUTPUT = DESKTOP / "randka_tiktok_promo.mp4"
WORKDIR = DESKTOP / "CursorRandka"
BOT_HANDLE = "@RandkaaPL_bot"

SCRIPT = (
    "Szukasz kogo\u015b w swoim mie\u015bcie? Randka PL w Telegramie! "
    "Przesuwaj profile, znajd\u017a par\u0119 w Warszawie, Krakowie, Wroc\u0142awiu i innych miastach. "
    "Za darmo, bez instalacji. Szukaj Randka PL bot w Telegramie!"
)

VOICE = "pl-PL-ZofiaNeural"
W, H = 1080, 1920
FPS = 30
# Sampled from randkapl_flyer.png
GRAD_STOPS = [
    (0.0, np.array([241, 31, 243], dtype=np.float32)),
    (0.35, np.array([224, 32, 128], dtype=np.float32)),
    (0.65, np.array([200, 1, 118], dtype=np.float32)),
    (1.0, np.array([23, 10, 43], dtype=np.float32)),
]
PINK = (241, 31, 243)
PINK_LIGHT = (255, 200, 235)
PINK_DARK = (200, 1, 118)
TARGET_MIN, TARGET_MAX = 22.0, 28.0


def collect_images():
    images = []
    for name in ["randkapl_flyer.png", "randkapl_bot_avatar.png"]:
        path = DESKTOP / name
        if path.exists():
            images.append(path)
    if RANDKABOT.is_dir():
        jpgs = list(RANDKABOT.glob("*.jpg"))

        def sort_key(p):
            return int(p.stem) if p.stem.isdigit() else 999

        jpgs.sort(key=sort_key)
        for j in jpgs:
            if j not in images:
                images.append(j)
    for i in range(1, 21):
        path = DESKTOP / f"{i}.jpg"
        if path.exists() and path not in images:
            images.append(path)
    for name in ["12.jpg", "13.jpg", "dsa.jpg"]:
        path = DESKTOP / name
        if path.exists() and path not in images:
            images.append(path)
    if not images:
        raise FileNotFoundError("No image assets found on desktop")
    return images


def _sample_grad(t: float):
    t = max(0.0, min(1.0, t))
    for i in range(len(GRAD_STOPS) - 1):
        t0, c0 = GRAD_STOPS[i]
        t1, c1 = GRAD_STOPS[i + 1]
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return (c0 * (1 - u) + c1 * u).astype(np.uint8)
    return GRAD_STOPS[-1][1].astype(np.uint8)


def make_gradient_frame(phase: float = 0.0):
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    shift = 0.025 * np.sin(phase * 2 * np.pi)
    for y in range(H):
        t = y / max(H - 1, 1) + shift * (0.5 - y / max(H - 1, 1))
        arr[y, :] = _sample_grad(t)
    return arr


def image_on_gradient(img_path):
    bg = make_gradient_frame(0.0).copy()
    pil_img = Image.open(img_path).convert("RGB")
    target_w, target_h = W - 100, int(H * 0.52)
    iw, ih = pil_img.size
    scale = max(target_w / iw, target_h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    pil_img = pil_img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - target_w) // 2)
    top = max(0, (nh - target_h) // 2)
    pil_img = pil_img.crop((left, top, left + target_w, top + target_h))
    bg_pil = Image.fromarray(bg)
    x = (W - target_w) // 2
    y = int(H * 0.28)
    bg_pil.paste(pil_img, (x, y))
    return np.array(bg_pil)


def make_image_segment(img_path, duration, overlay_text, font_size=58):
    frame = image_on_gradient(img_path)

    def make_frame(_t):
        return frame

    base = VideoClip(make_frame, duration=duration).with_fps(FPS)
    txt = (
        TextClip(
            text=overlay_text,
            font_size=font_size,
            color="white",
            method="caption",
            size=(W - 120, None),
            stroke_color="#880045",
            stroke_width=2,
        )
        .with_duration(duration)
        .with_position(("center", 70))
    )
    return CompositeVideoClip([base, txt], size=(W, H)).with_duration(duration)


def make_cta_segment(duration=4.5):
    bg = ColorClip(size=(W, H), color=PINK_DARK).with_duration(duration)
    layers = [bg]
    avatar = DESKTOP / "randkapl_bot_avatar.png"
    if avatar.exists():
        av = (
            ImageClip(str(avatar))
            .with_duration(duration)
            .resized(height=420)
            .with_position(("center", 520))
        )
        layers.append(av)
    title = (
        TextClip(
            text=BOT_HANDLE,
            font_size=86,
            color="white",
            stroke_color="black",
            stroke_width=3,
        )
        .with_duration(duration)
        .with_position(("center", 180))
    )
    sub = (
        TextClip(
            text="Randka PL w Telegramie\nZa darmo \u2022 Bez instalacji",
            font_size=52,
            color="#FFE4F0",
            method="caption",
            size=(W - 100, None),
            text_align="center",
        )
        .with_duration(duration)
        .with_position(("center", 1050))
    )
    layers.extend([title, sub])
    return CompositeVideoClip(layers, size=(W, H)).with_duration(duration)


async def generate_voice(path: Path):
    communicate = edge_tts.Communicate(SCRIPT, VOICE, rate="-3%")
    await communicate.save(str(path))


def build_video(voice_path: Path):
    voice = AudioFileClip(str(voice_path))
    voice_dur = float(voice.duration)
    total_target = min(max(voice_dur + 1.2, TARGET_MIN), TARGET_MAX)
    cta_dur = min(5.5, max(4.0, total_target * 0.22))
    main_target = max(8.0, total_target - cta_dur)

    images = collect_images()
    hooks = [
        "Szukasz kogo\u015b\nw swoim mie\u015bcie?",
        "Randka PL\nw Telegramie!",
        "Przesuwaj profile",
        "Warszawa \u2022 Krak\u00f3w \u2022 Wroc\u0142aw",
        "Znajd\u017a par\u0119 w swoim mie\u015bcie",
        "Za darmo, bez instalacji",
        "Szukaj: Randka PL bot",
    ]

    n_use = min(len(images), max(5, int(main_target / 2.8)))
    picked = images[:n_use]
    seg_dur = main_target / len(picked)

    segments = []
    for i, img in enumerate(picked):
        hook = hooks[min(i, len(hooks) - 1)]
        fs = 72 if i == 0 else 56
        segments.append(make_image_segment(img, seg_dur, hook, font_size=fs))

    main = concatenate_videoclips(segments, method="compose")
    if main.duration > main_target:
        main = main.subclipped(0, main_target)

    end = make_cta_segment(cta_dur)
    video = concatenate_videoclips([main, end], method="compose")

    if video.duration > total_target:
        video = video.subclipped(0, total_target)
    elif video.duration < total_target:
        pad = total_target - video.duration
        end2 = make_cta_segment(pad)
        video = concatenate_videoclips([video, end2], method="compose").subclipped(0, total_target)

    final_dur = float(video.duration)
    v_audio = voice.subclipped(0, min(voice.duration, final_dur - 0.15))
    video = video.with_audio(v_audio)
    return video


def main():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    voice_path = WORKDIR / "tiktok_voice.mp3"
    print("Generating Polish voiceover...")
    asyncio.run(generate_voice(voice_path))
    print("Building video...")
    video = build_video(voice_path)
    print("Writing output:", OUTPUT)
    video.write_videofile(
        str(OUTPUT),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger="bar",
    )
    video.close()
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    with VideoFileClip(str(OUTPUT)) as v:
        dur = v.duration
    print("OUTPUT=" + str(OUTPUT))
    print("SIZE_MB=%.2f" % size_mb)
    print("DURATION_SEC=%.1f" % dur)


if __name__ == "__main__":
    main()
