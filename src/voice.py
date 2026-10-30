"""Text-to-speech with edge-tts (free, no API key) + word timings for subtitles."""
import asyncio
import os
import subprocess
from pathlib import Path

import edge_tts


async def _speak(text: str, voice: str, rate: str, out: Path):
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset/duration are in 100-nanosecond units
                words.append(
                    {
                        "text": chunk["text"],
                        "start": chunk["offset"] / 1e7,
                        "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                    }
                )
    return words


def audio_duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        text=True,
    )
    return float(out.strip())


def _fake_voice(scene: dict, out: Path):
    """Offline test mode: silent audio sized to the text, with evenly spaced word timings."""
    toks = scene["narration"].split()
    dur = max(1.5, len(toks) * 0.4)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", f"{dur:.2f}", str(out)],
        check=True,
    )
    step = dur / len(toks)
    return [{"text": t, "start": i * step, "end": (i + 1) * step} for i, t in enumerate(toks)]


def synthesize(scenes: list[dict], cfg: dict, workdir: Path) -> None:
    """Adds scene['audio'], scene['duration'], scene['words'] to every scene."""
    offline = bool(os.environ.get("YT_OFFLINE_TEST"))
    for i, scene in enumerate(scenes):
        out = workdir / f"voice_{i:02d}.mp3"
        if offline:
            scene["words"] = _fake_voice(scene, out)
            scene["audio"] = out
            scene["duration"] = audio_duration(out)
            continue
        last = None
        for _ in range(3):
            try:
                words = asyncio.run(_speak(scene["narration"], cfg["voice"], cfg["voice_rate"], out))
                break
            except Exception as e:  # noqa: BLE001
                last = e
        else:
            raise RuntimeError(f"TTS failed for scene {i}: {last}")
        scene["audio"] = out
        scene["duration"] = audio_duration(out)
        scene["words"] = words
