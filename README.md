# yt-autopilot

Fully automatic, free, AI-generated faceless YouTube videos. One run produces a finished
vertical Short (or a long video) plus the title, description and tags. You only do the upload.

```
Gemini (script + metadata) -> edge-tts (voice) -> Pexels (stock footage) -> ffmpeg (video + captions)
```

All parts are free: Gemini free tier, Pexels free API, edge-tts needs no key, GitHub Actions free minutes.

## 1. Get the two free API keys

1. **Gemini**: https://aistudio.google.com/apikey -> Create API key.
2. **Stock footage** (optional, either one or both; without any you get plain animated backgrounds):
   - **Pixabay**: sign up at https://pixabay.com, then open https://pixabay.com/api/docs/ while logged in; your key is shown there. Secret name: `PIXABAY_API_KEY`.
   - **Pexels**: https://www.pexels.com/api/ (new key requests are sometimes paused). Secret name: `PEXELS_API_KEY`.

## 2. Run it automatically on GitHub

1. Repo -> **Settings -> Secrets and variables -> Actions -> New repository secret**.
   Add `GEMINI_API_KEY` and, for footage, `PIXABAY_API_KEY` and/or `PEXELS_API_KEY`.
2. Repo -> **Actions** tab -> *Make video* -> **Run workflow** (test run).
3. When it finishes, open the run and download the **videos-N** artifact. Inside each folder:
   - `video.mp4`: upload this to YouTube
   - `upload.txt`: paste-ready title, description, tags
   - `thumbnail.jpg`: optional thumbnail
4. It then runs every day by itself (edit the `cron` line in `.github/workflows/make-video.yml`).
   Artifacts are kept 14 days, so download them within that time.

## 2b. Optional: auto-upload to YouTube

Add three more secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` (Google Cloud project with the
YouTube Data API enabled and an OAuth client; the refresh token comes from the OAuth Playground with the
`youtube.upload` scope). Each run then uploads the video itself. Until your Google project passes YouTube's
API audit, uploads are forced to **private**, so switch them to Public in YouTube Studio.
Set `youtube_privacy` in `config.json` (`private`, `unlisted` or `public`; public only works after the audit).

## 2c. Run 5 times a day and save the videos on your Mac

The workflow runs 5 times a day and publishes each video as a GitHub Release. To have your Mac download new
videos automatically into `~/Movies/yt-autopilot`, paste this once into Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/ny4m1/yt-autopilot/main/mac/install.sh | bash
```

It checks every 30 minutes while your Mac is on, and catches up on anything it missed.

## 3. Or run it on your computer

```bash
# needs Python 3.10+ and ffmpeg installed
pip install -r requirements.txt
export GEMINI_API_KEY=...      # Windows PowerShell: $env:GEMINI_API_KEY="..."
export PIXABAY_API_KEY=...   # and/or PEXELS_API_KEY
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
| `gemini_models` | Preferred models, tried first. The script also asks Google which models your key can use and falls back to them automatically |
| `background_music_dir` | Drop royalty-free `.mp3` files in `assets/music/` and they are mixed in quietly |

## Things to know before monetising

- YouTube's monetisation rules target "inauthentic / mass-produced" content. Channels with only
  templated, repetitive AI videos can be refused or demonetised. Add real value: a distinct
  niche, good scripts, varied visuals, and review each video before uploading.
- Check every fact the script states. Gemini can be wrong.
- Pexels and Pixabay footage is free to use, but read their licences (pexels.com/license, pixabay.com/service/license-summary/).
- Only use music you have the rights to.
- In the YouTube upload form, tick the option disclosing realistic AI-generated or synthetic content when it applies.
