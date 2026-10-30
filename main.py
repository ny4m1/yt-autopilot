"""yt-autopilot: one command = one finished video + upload-ready metadata.

Usage:
    python main.py            # full run (needs GEMINI_API_KEY, optional PEXELS_API_KEY)
    python main.py --demo     # built-in sample script, no Gemini key needed (still needs internet for voice)
    python main.py --count 3  # make several videos in a row
    python main.py --upload   # also upload to YouTube (needs the YT_* secrets)
"""
import argparse
import datetime as dt
import json
import re
import shutil
from pathlib import Path

from src import assemble, script, upload, visuals, voice

ROOT = Path(__file__).parent
HISTORY = ROOT / "history.json"

DEMO = {
    "topic": "Venus day longer than year",
    "title": "A Day on Venus Is Longer Than Its Year",
    "description": "On Venus, one rotation takes longer than one trip around the Sun. Here is why.\n\n#space #venus #science #shorts",
    "tags": ["space", "venus", "planets", "science facts", "astronomy", "shorts", "did you know"],
    "scenes": [
        {"narration": "On Venus, a single day lasts longer than an entire year.", "search_query": "planet venus"},
        {"narration": "Venus spins incredibly slowly, taking about two hundred forty-three Earth days to rotate once.", "search_query": "slow rotation planet"},
        {"narration": "But it circles the Sun in only two hundred twenty-five Earth days.", "search_query": "sun space"},
        {"narration": "Even stranger, it spins backwards compared to most planets, so the Sun rises in the west.", "search_query": "sunrise clouds"},
        {"narration": "Follow for more space facts that sound fake but are completely true.", "search_query": "galaxy stars"},
    ],
}


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "video"


def load_history() -> list[str]:
    return json.loads(HISTORY.read_text()) if HISTORY.exists() else []


def make_one(cfg: dict, demo: bool, do_upload: bool = False) -> Path:
    history = load_history()
    data = DEMO if demo else script.generate(cfg, history)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = ROOT / "output" / f"{stamp}_{slugify(data['title'])}"
    work = ROOT / "work" / out_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    scenes = data["scenes"]
    print(f"[1/4] Script: {data['title']} ({len(scenes)} scenes)")
    print("[2/4] Voice-over ...")
    voice.synthesize(scenes, cfg, work)
    print("[3/4] Footage ...")
    visuals.fetch_all(scenes, cfg, work)
    print("[4/4] Assembling video ...")
    assemble.build(scenes, cfg, work, out_dir / "video.mp4")
    assemble.thumbnail(scenes, data["title"], cfg, out_dir / "thumbnail.jpg", work)

    meta = {k: data[k] for k in ("title", "description", "tags", "topic")}
    meta["script"] = [s["narration"] for s in scenes]
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    # paste-ready text for the YouTube upload form
    (out_dir / "upload.txt").write_text(
        f"TITLE:\n{meta['title']}\n\nDESCRIPTION:\n{meta['description']}\n\nTAGS:\n{', '.join(meta['tags'])}\n"
    )

    if do_upload and not demo:
        if upload.configured():
            try:
                vid = upload.upload(out_dir / "video.mp4", meta, cfg)
                print(f"Uploaded to YouTube: https://www.youtube.com/watch?v={vid}")
                (out_dir / "youtube_url.txt").write_text(f"https://www.youtube.com/watch?v={vid}\n")
            except Exception as e:  # noqa: BLE001 - keep the video even if upload fails
                print(f"WARNING: upload failed, video is still saved as a download: {e}")
        else:
            print("Upload skipped: YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN not set.")

    if not demo:
        HISTORY.write_text(json.dumps(history + [data["topic"]], indent=2))
    shutil.rmtree(work, ignore_errors=True)
    print(f"Done -> {out_dir}")
    return out_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use built-in sample script")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--upload", action="store_true", help="upload to YouTube after making the video")
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    for _ in range(args.count):
        make_one(cfg, args.demo, args.upload)


if __name__ == "__main__":
    main()
