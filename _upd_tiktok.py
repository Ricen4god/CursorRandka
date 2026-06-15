from pathlib import Path
p = Path(r"C:\Users\nazar\OneDrive\Рабочий стол\CursorRandka\make_tiktok_video.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    "Szukasz kogo\u015b w swoim mie\u015bcie? Randka PL w Telegramie! "
    "Przesuwaj profile, znajd\u017a par\u0119 w Warszawie, Krakowie, Wroc\u0142awiu i innych miastach. "
    "Za darmo, bez instalacji. Szukaj Randka PL bot w Telegramie!",
    "Szukasz mi\u0142o\u015bci w swoim mie\u015bcie? Randka PL \u2014 randki w Telegramie! "
    "Przesuwaj, lajkuj, znajd\u017a par\u0119. Pi\u0119tna\u015bcie miast w Polsce. Za darmo! "
    "Wpisz: Randka PL bot. Szukaj RandkaaPL_bot w Telegramie.",
)
text = text.replace("PINK = (255, 105, 180)\nPINK_LIGHT = (255, 200, 220)\nPINK_DARK = (180, 30, 100)", """# Sampled from randkapl_flyer.png
GRAD_STOPS = [
    (0.0, np.array([241, 31, 243], dtype=np.float32)),
    (0.35, np.array([224, 32, 128], dtype=np.float32)),
    (0.65, np.array([200, 1, 118], dtype=np.float32)),
    (1.0, np.array([23, 10, 43], dtype=np.float32)),
]
PINK = (241, 31, 243)
PINK_LIGHT = (255, 200, 235)
PINK_DARK = (200, 1, 118)
TARGET_MIN, TARGET_MAX = 22.0, 28.0""")
old_grad = """def make_gradient_frame():
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y / max(H - 1, 1)
        for c in range(3):
            arr[y, :, c] = int(PINK_LIGHT[c] * (1 - t) + PINK[c] * t)
    return arr"""
new_grad = """def _sample_grad(t: float):
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
    return arr"""
text = text.replace(old_grad, new_grad)
text = text.replace("    bg = make_gradient_frame().copy()", "    bg = make_gradient_frame(0.0).copy()")
# collect desktop numbered jpgs
needle = "    for name in [\"12.jpg\", \"13.jpg\", \"dsa.jpg\"]:"
insert = "    for i in range(1, 21):\n        path = DESKTOP / f\"{i}.jpg\"\n        if path.exists() and path not in images:\n            images.append(path)\n"
if insert.strip() not in text:
    text = text.replace(needle, insert + needle)
# voice rate
text = text.replace("communicate = edge_tts.Communicate(SCRIPT, VOICE)", "communicate = edge_tts.Communicate(SCRIPT, VOICE, rate=\"-3%\")")
# build_video duration logic
old_build = """    voice_dur = float(voice.duration)
    cta_dur = 4.5
    main_target = min(max(voice_dur + 0.8, 20 - cta_dur), 30 - cta_dur)
    total_target = min(max(voice_dur + 1.0, 20), 30)"""
new_build = """    voice_dur = float(voice.duration)
    total_target = min(max(voice_dur + 1.2, TARGET_MIN), TARGET_MAX)
    cta_dur = min(5.5, max(4.0, total_target * 0.22))
    main_target = max(8.0, total_target - cta_dur)"""
text = text.replace(old_build, new_build)
text = text.replace(
    "    hooks = [\n        \"Szukasz kogo\u015b\\nw swoim mie\u015bcie?\",\n        \"Randka PL\\nw Telegramie!\",\n        \"Przesuwaj profile\",\n        \"Warszawa \u2022 Krak\u00f3w \u2022 Wroc\u0142aw\",\n        \"Znajd\u017a par\u0119 w swoim mie\u015bcie\",\n        \"Za darmo, bez instalacji\",\n        \"Szukaj: Randka PL bot\",\n    ]",
    "    hooks = [\n        \"Szukasz mi\u0142o\u015bci\\nw swoim mie\u015bcie? \U0001f495\",\n        \"Randka PL\\nrandki w Telegramie!\",\n        \"Przesuwaj \u00b7 Lajkuj \U0001f498\",\n        \"15 miast w Polsce \U0001f1f5\U0001f1f1\",\n        \"Znajd\u017a par\u0119\",\n        \"Za darmo!\",\n        \"@RandkaaPL_bot\",\n    ]",
)
old_pad = """    if video.duration > total_target:
        video = video.subclipped(0, total_target)
    elif video.duration < 20:
        pad = 20 - video.duration
        end2 = make_cta_segment(pad)
        video = concatenate_videoclips([video, end2], method=\"compose\").subclipped(0, 20)

    final_dur = float(video.duration)
    v_audio = voice.subclipped(0, min(voice.duration, final_dur - 0.2))
    video = video.with_audio(v_audio)"""
new_pad = """    if video.duration > total_target:
        video = video.subclipped(0, total_target)
    elif video.duration < total_target:
        pad = total_target - video.duration
        end2 = make_cta_segment(pad)
        video = concatenate_videoclips([video, end2], method=\"compose\").subclipped(0, total_target)

    final_dur = float(video.duration)
    v_audio = voice.subclipped(0, min(voice.duration, final_dur - 0.15))
    video = video.with_audio(v_audio)"""
text = text.replace(old_pad, new_pad)
text = text.replace(
    "text=\"Randka PL w Telegramie\\nZa darmo \u2022 Bez instalacji\",",
    "text=\"Wpisz w Telegramie \u2192 START\\nRandka PL \u2022 Za darmo \U0001f495\",",
)
p.write_text(text, encoding="utf-8")
print("updated")
