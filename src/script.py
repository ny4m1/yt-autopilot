"""Generate a video script + YouTube metadata with the free Gemini API."""
import json
import os
import re
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """You write viral, factually accurate scripts for a faceless YouTube {fmt} channel.

Channel niche: {niche}
Audience: {audience}
Language: {language}
Target narration length: about {seconds} seconds (~{words} words total).

Do NOT reuse any of these previous topics:
{history}

Return ONLY valid JSON with exactly this shape:
{{
  "topic": "short topic label",
  "title": "click-worthy YouTube title, max 90 chars, no clickbait lies",
  "description": "2-3 sentence description followed by a blank line and 3-5 hashtags",
  "tags": ["8 to 15 tags"],
  "scenes": [
    {{
      "narration": "1-2 spoken sentences for this scene",
      "search_query": "2-4 word stock-footage search query that visually matches the narration"
    }}
  ]
}}

Rules:
- 6 to 9 scenes. Scene 1 must be a strong hook (a surprising claim or question).
- The last scene must be a short call to action (like / subscribe) tied to the topic.
- Only state facts you are confident are true. No made-up statistics.
- Narration is plain spoken text: no emojis, no stage directions, no markdown.
- search_query must be concrete and filmable (e.g. "galaxy nebula", "ocean waves"), never abstract.
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def _validate(data: dict) -> dict:
    for key in ("title", "description", "tags", "scenes"):
        if key not in data:
            raise ValueError(f"missing key: {key}")
    scenes = [s for s in data["scenes"] if s.get("narration") and s.get("search_query")]
    if len(scenes) < 4:
        raise ValueError("too few scenes")
    data["scenes"] = scenes
    data.setdefault("topic", data["title"])
    data["title"] = data["title"][:100]
    return data


def generate(cfg: dict, history: list[str]) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    seconds = cfg["target_seconds"]
    prompt = PROMPT.format(
        fmt="Shorts" if cfg["format"] == "shorts" else "long-form",
        niche=cfg["niche"],
        audience=cfg["audience"],
        language=cfg["language"],
        seconds=seconds,
        words=int(seconds * 2.5),
        history="\n".join(f"- {h}" for h in history[-cfg["avoid_repeating_last_n"]:]) or "(none yet)",
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0},
    }

    last_err = None
    for model in cfg["gemini_models"]:
        for attempt in range(3):
            try:
                r = requests.post(
                    API.format(model=model), params={"key": key}, json=body, timeout=90
                )
                if r.status_code == 429:
                    time.sleep(20 * (attempt + 1))
                    continue
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return _validate(_extract_json(text))
            except Exception as e:  # noqa: BLE001 - retry on any parse/network error
                last_err = e
                time.sleep(3)
    raise RuntimeError(f"Gemini script generation failed: {last_err}")
