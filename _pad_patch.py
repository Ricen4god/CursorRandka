from pathlib import Path
p = Path(r"C:\Users\nazar\OneDrive\Рабочий стол\CursorRandka\make_tiktok_video.py")
t = p.read_text(encoding="utf-8")
if "def pad_audio_to_duration" not in t:
    t = t.replace(
        "def mux_final(silent_video: Path, voice_path: Path, music_path: Path, out_path: Path):",
        """def pad_audio_to_duration(in_path: Path, out_path: Path, duration: float):
    pad = max(0.0, duration)
    subprocess.run(
        [
            ffmpeg_exe(), "-y",
            "-i", str(in_path),
            "-af", "apad=pad_dur=" + str(pad),
            "-t", str(duration),
            str(out_path),
        ],
        check=True, capture_output=True,
    )


def mux_final(silent_video: Path, voice_path: Path, music_path: Path, out_path: Path):""",
    )
    t = t.replace(
        '    print("Muxing...")\n    mux_final(silent_video, voice_path, music_path, temp_out)',
        '    voice_padded = WORK_DIR / "voiceover_padded.mp3"\n    print(f"Padding voice to {target:.1f}s...")\n    pad_audio_to_duration(voice_path, voice_padded, target)\n\n    print("Muxing...")\n    mux_final(silent_video, voice_padded, music_path, temp_out)',
    )
    p.write_text(t, encoding="utf-8")
print("done")
