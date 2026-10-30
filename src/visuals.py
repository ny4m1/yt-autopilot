"""Fetch free stock footage from Pexels and/or Pixabay (free API keys). Falls back to a generated background."""
import os
import random
import subprocess
from pathlib import Path

import requests

PEXELS = "https://api.pexels.com/videos/search"
PIXABAY = "https://pixabay.com/api/videos/"


def _search(query: str, orientation: str, min_seconds: float, used: set) -> str | None:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    r = requests.get(
        PEXELS,
        headers={"Authorization": key},
        params={"query": query, "orientation": orientation, "per_page": 15, "size": "medium"},
        timeout=30,
    )
    if r.status_code != 200:
        return None
    videos = [v for v in r.json().get("videos", []) if v["id"] not in used]
    # prefer clips long enough for the scene
    long_enough = [v for v in videos if v.get("duration", 0) >= min_seconds] or videos
    if not long_enough:
        return None
    video = random.choice(long_enough[:6])
    used.add(video["id"])
    files = [f for f in video["video_files"] if f.get("file_type") == "video/mp4"]
    # pick the file closest to 1080 on the long side without being huge
    files.sort(key=lambda f: abs(max(f.get("width", 0), f.get("height", 0)) - 1920))
    return files[0]["link"] if files else None


def _search_pixabay(query: str, orientation: str, min_seconds: float, used: set) -> str | None:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    r = requests.get(
        PIXABAY,
        params={"key": key, "q": query, "per_page": 20, "safesearch": "true"},
        timeout=30,
    )
    if r.status_code != 200:
        return None
    hits = [h for h in r.json().get("hits", []) if ("pb", h["id"]) not in used]
    if orientation == "portrait":  # prefer tall clips, but landscape is fine (center-cropped)
        tall = [h for h in hits if h["videos"].get("medium", {}).get("height", 0)
                > h["videos"].get("medium", {}).get("width", 0)]
        hits = tall or hits
    hits = [h for h in hits if h.get("duration", 0) >= min_seconds] or hits
    if not hits:
        return None
    hit = random.choice(hits[:6])
    used.add(("pb", hit["id"]))
    for size in ("large", "medium", "small"):
        url = hit["videos"].get(size, {}).get("url")
        if url:
            return url
    return None


def _find_clip(query: str, cfg: dict, min_seconds: float, used: set) -> str | None:
    for search in (_search, _search_pixabay):
        try:
            url = search(query, cfg["pexels_orientation"], min_seconds, used)
        except requests.RequestException:
            url = None
        if url:
            return url
    return None


def _download(url: str, out: Path):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def _fallback(out: Path, size: tuple[int, int], seconds: float, seed: int):
    """Animated dark gradient so the pipeline still works without Pexels."""
    w, h = size
    colors = ["0x1b1464", "0x0f2027", "0x2c0b3f", "0x07323b", "0x3a1c71"]
    c = colors[seed % len(colors)]
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"gradients=s={w}x{h}:c0={c}:c1=0x000000:speed=0.02:d={seconds + 1}",
         "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )


def fetch_all(scenes: list[dict], cfg: dict, workdir: Path) -> None:
    """Adds scene['clip'] (path to a video file) to every scene."""
    size = tuple(cfg["resolutions"][cfg["format"]])
    used: set = set()
    for i, scene in enumerate(scenes):
        out = workdir / f"clip_{i:02d}.mp4"
        url = None
        for query in (scene["search_query"], " ".join(scene["search_query"].split()[:2])):
            url = _find_clip(query, cfg, scene["duration"], used)
            if url:
                break
        try:
            if url:
                _download(url, out)
            else:
                raise RuntimeError("no stock clip")
        except Exception:  # noqa: BLE001
            _fallback(out, size, scene["duration"], i)
        scene["clip"] = out
