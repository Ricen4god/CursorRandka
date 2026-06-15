from pathlib import Path
import re
src = Path(r"C:\Users\nazar\OneDrive\Рабочий стол\CursorRandka\make_tiktok_video.py")
text = src.read_text(encoding="utf-8")

def repl_script_scenes(m):
    return (
        "SCRIPT = (\n"
        "    \"Szukasz mi\u0142o\u015bci w swoim mie\u015bcie? \"\n"
        "    \"Randka PL \u2014 randki w Telegramie! \"\n"
        "    \"Przesuwaj, lajkuj, znajd\u017a par\u0119. \"\n"
        "    \"Pi\u0119tna\u015bcie miast w Polsce. Za darmo! \"\n"
        "    \"Wpisz w Telegramie: Randka PL bot, u\u017cytkownik RandkaaPL_bot.\"\n"
        ")\n\n"
        "SCENES = [\n"
        "    {\"text\": \"Szukasz mi\u0142o\u015bci\\nw swoim mie\u015bcie? \U0001f495\", \"sub\": \"Randka PL\", \"duration\": 4.0},\n"
        "    {\"text\": \"Przesuwaj \u00b7 Lajkuj\\nZnajd\u017a par\u0119 \U0001f498\", \"sub\": \"Randki w Telegramie\", \"duration\": 5.0},\n"
        "    {\"text\": \"15 miast\\nw Polsce \U0001f1f5\U0001f1f1\", \"sub\": \"Za darmo \u2014 od razu!\", \"duration\": 4.5},\n"
        "    {\"text\": \"@RandkaaPL_bot\", \"sub\": \"Wpisz w Telegramie \u2192 START\", \"duration\": 5.0},\n"
        "]\n\n"
    )

text = text.replace(
    "Generate TikTok promo video for @RandkaaPL_bot - minimal deps.",
    "TikTok promo for @RandkaaPL_bot - style matched to randkapl_flyer.png.",
)
text = text.replace("import os\nimport shutil", "import os\nimport random\nimport shutil")
text = re.sub(r"SCRIPT = \(.*?\)\n\nSCENES = \[.*?\]\n\n", repl_script_scenes, text, count=1, flags=re.DOTALL)
old_colors = """GRAD_TOP = (255, 120, 160)
GRAD_BOT = (180, 50, 100)
DEEP_PINK = (220, 40, 100)
WHITE = (255, 255, 255)"""
new_colors = """GRAD_STOPS = [
    (0.0, (241, 31, 243)),
    (0.35, (224, 32, 128)),
    (0.65, (200, 1, 118)),
    (1.0, (23, 10, 43)),
]
ACCENT_PINK = (241, 31, 243)
DEEP_PINK = (200, 1, 118)
WHITE = (255, 255, 255)
SOFT_WHITE = (255, 230, 245)
TARGET_MIN, TARGET_MAX = 22.0, 28.0
random.seed(42)
HEARTS = [
    (random.randint(40, W - 40), random.randint(80, H - 80), random.randint(18, 42), random.uniform(0, 6.28318))
    for _ in range(28)
]"""
text = text.replace(old_colors, new_colors)
old_grad_fn = """def make_gradient_bg() -> Image.Image:
    base = Image.new(\"RGB\", (W, H))
    px = base.load()
    for y in range(H):
        t = y / H
        r = int(GRAD_TOP[0] * (1 - t) + GRAD_BOT[0] * t)
        g = int(GRAD_TOP[1] * (1 - t) + GRAD_BOT[1] * t)
        b = int(GRAD_TOP[2] * (1 - t) + GRAD_BOT[2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return base"""
new_grad_fn = """def lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def sample_gradient(t: float):
    t = max(0.0, min(1.0, t))
    for i in range(len(GRAD_STOPS) - 1):
        t0, c0 = GRAD_STOPS[i]
        t1, c1 = GRAD_STOPS[i + 1]
        if t0 <= t <= t1:
            local = (t - t0) / (t1 - t0) if t1 > t0 else 0
            return lerp_color(c0, c1, local)
    return GRAD_STOPS[-1][1]


def draw_heart(draw, cx, cy, size, fill):
    s = size
    draw.ellipse((cx - s, cy - s // 2, cx, cy + s // 3), fill=fill)
    draw.ellipse((cx, cy - s // 2, cx + s, cy + s // 3), fill=fill)
    draw.polygon([(cx - s, cy), (cx + s, cy), (cx, cy + s)], fill=fill)


def overlay_hearts(base: Image.Image, phase: float, opacity: float = 0.22):
    layer = Image.new(\"RGBA\", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for i, (hx, hy, sz, _rot) in enumerate(HEARTS):
        drift = 25 * math.sin(phase * math.pi * 2 + i * 0.7)
        alpha = int(255 * opacity * (0.6 + 0.4 * math.sin(phase * 4 + i)))
        col = (*SOFT_WHITE, alpha) if i % 3 else (*ACCENT_PINK, alpha)
        draw_heart(draw, int(hx + drift), int(hy + drift * 0.3), sz, col)
    layer = layer.rotate(2 * math.sin(phase * math.pi), resample=Image.Resampling.BICUBIC, center=(W // 2, H // 2))
    base.paste(Image.alpha_composite(base.convert(\"RGBA\"), layer).convert(\"RGB\"))


def make_gradient_bg(time_phase: float = 0.0) -> Image.Image:
    base = Image.new(\"RGB\", (W, H))
    px = base.load()
    shift = 0.03 * math.sin(time_phase * math.pi * 2)
    for y in range(H):
        t = y / H + shift * (0.5 - y / H)
        col = sample_gradient(t)
        for x in range(W):
            px[x, y] = col
    return base"""
text = text.replace(old_grad_fn, new_grad_fn)
text = text.replace(
    "def render_scene_frame(scene_idx, progress, photos, avatar, flyer) -> Image.Image:\n    base = make_gradient_bg()",
    "def render_scene_frame(scene_idx, progress, global_phase, photos, avatar, flyer) -> Image.Image:\n    base = make_gradient_bg(global_phase)\n    overlay_hearts(base, global_phase + scene_idx * 0.2)",
)
text = text.replace("fill=(255, 220, 235)", "fill=SOFT_WHITE")
text = text.replace(
    "    idx = 0\n    for scene_idx, dur in enumerate(scene_durations):",
    "    idx = 0\n    total_frames = sum(max(1, int(d * FPS)) for d in scene_durations)\n    for scene_idx, dur in enumerate(scene_durations):",
)
text = text.replace(
    "            frame = render_scene_frame(scene_idx, progress, photos, avatar, flyer)",
    "            global_phase = idx / max(total_frames - 1, 1)\n            frame = render_scene_frame(scene_idx, progress, global_phase, photos, avatar, flyer)",
)
text = text.replace(
    "    voice_duration = await generate_voiceover(SCRIPT, voice_path)\n    print(f\"Voice: {voice_duration:.1f}s\")\n\n    print(\"Rendering frames...\")\n    silent_video = render_frames_to_video(photos, voice_duration)",
    "    voice_duration = await generate_voiceover(SCRIPT, voice_path)\n    print(f\"Voice: {voice_duration:.2f}s\")\n    target = max(TARGET_MIN, min(TARGET_MAX, voice_duration + 0.3))\n    if voice_duration > TARGET_MAX:\n        target = voice_duration + 0.2\n\n    print(\"Rendering frames...\")\n    silent_video = render_frames_to_video(photos, target)",
)
text = text.replace("generate_bg_music(voice_duration + 0.5, music_path)", "generate_bg_music(target + 0.5, music_path)")
text = text.replace("    shutil.copy2(temp_out, OUTPUT)", "    if OUTPUT.exists():\n        OUTPUT.unlink()\n    shutil.copy2(temp_out, OUTPUT)")
text = text.replace("=== Randka PL TikTok Promo Generator ===", "=== Randka PL TikTok (make_tiktok_video.py) ===")
text = text.replace('"pl-PL-ZofiaNeural", rate="+8%"', '"pl-PL-ZofiaNeural", rate="+5%"')
src.write_text(text, encoding="utf-8")
print("patched ok")
