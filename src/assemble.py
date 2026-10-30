"""Assemble the final video with ffmpeg: clips + voice + burned-in subtitles + optional music."""
import random
import subprocess
import textwrap
from pathlib import Path

PAD = 0.25  # seconds of breathing room after each scene


def _run(cmd: list[str]):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *cmd], check=True)


def _ts(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _build_scene(scene: dict, idx: int, size: tuple[int, int], fps: int, workdir: Path) -> Path:
    w, h = size
    out = workdir / f"scene_{idx:02d}.mp4"
    dur = scene["duration"] + PAD
    scene["total"] = dur
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,fps={fps},format=yuv420p"
    )
    _run([
        "-stream_loop", "-1", "-i", str(scene["clip"]),
        "-i", str(scene["audio"]),
        "-t", f"{dur:.3f}",
        "-vf", vf,
        "-af", "apad,aresample=44100",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-ac", "2", "-b:a", "160k",
        str(out),
    ])
    return out


def _chunks(scene: dict, per: int = 3):
    words = scene.get("words") or []
    if not words:  # fallback: spread the words evenly
        toks = scene["narration"].split()
        step = scene["duration"] / max(len(toks), 1)
        words = [{"text": t, "start": i * step, "end": (i + 1) * step} for i, t in enumerate(toks)]
    for i in range(0, len(words), per):
        group = words[i:i + per]
        yield " ".join(w["text"] for w in group), group[0]["start"], group[-1]["end"]


def _write_ass(scenes: list[dict], cfg: dict, size: tuple[int, int], path: Path):
    w, h = size
    margin_v = int(h * 0.22) if cfg["format"] == "shorts" else int(h * 0.08)
    size_pt = cfg["subtitle_size"] if cfg["format"] == "shorts" else cfg["subtitle_size"] // 2
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Default,{cfg['subtitle_font']},{size_pt},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,0,0,1,6,2,2,60,60,{margin_v},1",
        "", "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    offset = 0.0
    for scene in scenes:
        for text, start, end in _chunks(scene):
            lines.append(
                f"Dialogue: 0,{_ts(offset + start)},{_ts(offset + max(end, start + 0.2))},"
                f"Default,,0,0,0,,{text.upper().replace(chr(10), ' ')}"
            )
        offset += scene["total"]
    path.write_text("\n".join(lines), encoding="utf-8")


def _pick_music(cfg: dict) -> Path | None:
    d = Path(cfg["background_music_dir"])
    if not d.is_dir():
        return None
    tracks = [p for p in d.iterdir() if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg"}]
    return random.choice(tracks) if tracks else None


def build(scenes: list[dict], cfg: dict, workdir: Path, out_video: Path) -> None:
    size = tuple(cfg["resolutions"][cfg["format"]])
    parts = [_build_scene(s, i, size, cfg["fps"], workdir) for i, s in enumerate(scenes)]

    concat_list = workdir / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    joined = workdir / "joined.mp4"
    _run(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(joined)])

    ass = workdir / "subs.ass"
    _write_ass(scenes, cfg, size, ass)
    # ffmpeg filter paths need escaping of ':' and '\'
    ass_path = str(ass.resolve()).replace("\\", "/").replace(":", "\\:")
    vf = f"subtitles='{ass_path}'"

    music = _pick_music(cfg)
    if music:
        total = sum(s["total"] for s in scenes)
        _run([
            "-i", str(joined), "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            f"[1:a]volume={cfg['music_volume']},atrim=0:{total:.2f}[m];"
            f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-vf", vf, "-map", "0:v", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_video),
        ])
    else:
        _run([
            "-i", str(joined), "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-c:a", "copy", "-movflags", "+faststart", str(out_video),
        ])


def thumbnail(scenes: list[dict], title: str, cfg: dict, out_jpg: Path, workdir: Path) -> None:
    """Simple thumbnail: first scene frame + big title text. Best-effort."""
    w, h = (1280, 720)
    wrapped = "\n".join(textwrap.wrap(title.upper(), 22)[:4])
    txt = workdir / "thumb.txt"
    txt.write_text(wrapped, encoding="utf-8")
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.45:t=fill,"
        f"drawtext=textfile='{txt.resolve()}':fontcolor=white:fontsize=92:borderw=6:bordercolor=black:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=12"
    )
    try:
        _run(["-ss", "0.5", "-i", str(scenes[0]["clip"]), "-frames:v", "1", "-vf", vf, "-q:v", "3", str(out_jpg)])
    except subprocess.CalledProcessError:
        pass
