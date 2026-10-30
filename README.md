# yt-autopilot

Fully automatic, free, AI-generated faceless YouTube videos. One run produces a finished
vertical Short (or a long video) plus the title, description and tags. You only do the upload.

```
Gemini (script + metadata) -> edge-tts (voice) -> Pexels (stock footage) -> ffmpeg (video + captions)
```

All parts are free: Gemini free tier, Pexels free API, edge-tts needs no key, GitHub Actions free minutes.

## 1. Get the two free API keys

1. **Gemini**: https://aistudio.google.com/apikey -> Create API key.
2. **Pexels**: https://www.pexels.com/api/ -> sign up -> your key is shown on the API page.
   (Optional. Without it you get plain animated backgrounds instead of stock footage.)

## 2. Run it automatically on GitHub

1. Repo -> **Settings -> Secrets and variables -> Actions -> New repository secret**.
   Add `GEMINI_API_KEY` and `PEXELS_API_KEY`.
2. Repo -> **Actions** tab -> *Make video* -> **Run workflow** (test run).
3. When it finishes, open the run and download the **videos-N** artifact. Inside each folder:
   - `video.mp4`: upload this to YouTube
   - `upload.txt`: paste-ready title, description, tags
   - `thumbnail.jpg`: optional thumbnail
4. It then runs every day by itself (edit the `cron` line in `.github/workflows/make-video.yml`).
   Artifacts are kept 14 days, so download them within that time.

## 3. Or run it on your computer

```bash
# needs Python 3.10+ and ffmpeg installed
pip install -r requirements.txt
export GEMINI_API_KEY=...      # Windows PowerShell: $env:GEMINI_API_KEY="..."
export PEXELS_API_KEY=...
python main.py            # one video
python main.py --count 3  # three videos
python main.py --demo     # sample script, no Gemini key needed
```

## 4. Customise

Edit `config.json`:

| Setting | What it does |
| --- | --- |
| `niche`, `audience` | What the channel is about. Change this first. |
| `format` | `shorts` (1080x1920) or `long` (1920x1080; also set `pexels_orientation` to `landscape` and raise `target_seconds`) |
| `voice` | Any edge-tts voice. List them with `edge-tts --list-voices` |
| `gemini_models` | Tried in order. If a model name stops working, update it from https://ai.google.dev/gemini-api/docs/models |
| `background_music_dir` | Drop royalty-free `.mp3` files in `assets/music/` and they are mixed in quietly |

## Things to know before monetising

- YouTube's monetisation rules target "inauthentic / mass-produced" content. Channels with only
  templated, repetitive AI videos can be refused or demonetised. Add real value: a distinct
  niche, good scripts, varied visuals, and review each video before uploading.
- Check every fact the script states. Gemini can be wrong.
- Pexels footage is free to use, but read their licence at https://www.pexels.com/license/.
- Only use music you have the rights to.
- In the YouTube upload form, tick the option disclosing realistic AI-generated or synthetic content when it applies.
