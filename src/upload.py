"""Upload a finished video to YouTube with the YouTube Data API (free).

Needs three GitHub secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Without them the upload is skipped and the video is only saved as a download.

NOTE: until your Google Cloud project passes YouTube's API compliance audit, Google forces
every API upload to "private". You then switch it to Public in YouTube Studio (10 seconds).
"""
import json
import os
from pathlib import Path

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def configured() -> bool:
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def _access_token() -> str:
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["YT_CLIENT_ID"],
            "client_secret": os.environ["YT_CLIENT_SECRET"],
            "refresh_token": os.environ["YT_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"YouTube login failed ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


def _start_session(token: str, body: dict) -> str:
    r = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
        data=json.dumps(body),
        timeout=60,
    )
    return r


def upload(video: Path, meta: dict, cfg: dict) -> str:
    """Uploads video.mp4 and returns the YouTube video id."""
    token = _access_token()
    description = meta["description"]
    if cfg.get("format") == "shorts" and "#shorts" not in description.lower():
        description += "\n\n#Shorts"
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": description[:4900],
            "tags": meta["tags"][:15],
            "categoryId": str(cfg.get("youtube_category_id", "28")),  # 28 = Science & Technology
            "defaultLanguage": cfg.get("language", "en"),
        },
        "status": {
            "privacyStatus": os.environ.get("YT_PRIVACY", cfg.get("youtube_privacy", "private")),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # discloses AI-generated content, as YouTube requires
        },
    }
    r = _start_session(token, body)
    if r.status_code == 400 and "containsSyntheticMedia" in r.text:
        body["status"].pop("containsSyntheticMedia")
        r = _start_session(token, body)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube upload could not start ({r.status_code}): {r.text[:400]}")

    session_url = r.headers["Location"]
    with open(video, "rb") as f:
        up = requests.put(
            session_url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"},
            data=f,
            timeout=900,
        )
    if up.status_code not in (200, 201):
        raise RuntimeError(f"YouTube upload failed ({up.status_code}): {up.text[:400]}")
    return up.json()["id"]
