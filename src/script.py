"""Generate a video script + YouTube metadata with the free Gemini API."""
import json
import os
import re
import time

import requests

BASE = "https://generativelanguage.googleapis.com/v1beta"
API = BASE + "/models/{model}:generateContent"

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


def _version(name: str) -> tuple:
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)


def _candidate_models(key: str, preferred: list[str]) -> list[str]:
    """Ask Google which models this key can call, so retired model names never break the run.

    Order: Flash-Lite models first (cheapest / most free-tier friendly), newest version first,
    then regular Flash models. Models from config.json that still exist go first.
    """
    try:
        r = requests.get(f"{BASE}/models", params={"key": key, "pageSize": 200}, timeout=30)
        r.raise_for_status()
        available = [
            m["name"].split("/")[-1]
            for m in r.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
    except Exception as e:  # noqa: BLE001
        print(f"  (could not list models: {e}; using config.json list)")
        return preferred

    bad = ("tts", "live", "image", "audio", "embedding", "robotics", "computer", "lyria", "veo", "native", "thinking-exp", "latest")
    flash = [m for m in available if "flash" in m and not any(b in m for b in bad)]
    stable = [m for m in flash if "preview" not in m and "exp" not in m]
    rest = [m for m in flash if m not in stable]
    ranked = sorted(stable, key=lambda m: ("lite" not in m, tuple(-x for x in _version(m)))) + \
             sorted(rest, key=lambda m: ("lite" not in m, tuple(-x for x in _version(m))))
    ordered = [m for m in preferred if m in available] + [m for m in ranked if m not in preferred]
    print(f"  Gemini models to try: {ordered[:6]}")
    return ordered or preferred


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

    errors = []
    for model in _candidate_models(key, cfg["gemini_models"])[:6]:
        for attempt in range(3):
            try:
                r = requests.post(
                    API.format(model=model), params={"key": key}, json=body, timeout=120
                )
                if r.status_code == 429:
                    errors.append(f"{model}: rate limited (429)")
                    time.sleep(20 * (attempt + 1))
                    continue
                if r.status_code in (400, 401, 403, 404):
                    # not usable with this key (retired, paid-only, bad key): try the next model
                    errors.append(f"{model}: HTTP {r.status_code} {r.text[:200]}")
                    break
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                print(f"  Script written by {model}")
                return _validate(_extract_json(text))
            except Exception as e:  # noqa: BLE001 - retry on parse/network error
                errors.append(f"{model}: {type(e).__name__}: {e}")
                time.sleep(3)
    # keys are masked by GitHub, but never print the URL anyway
    raise RuntimeError("Gemini script generation failed:\n  " + "\n  ".join(errors[-8:]))
