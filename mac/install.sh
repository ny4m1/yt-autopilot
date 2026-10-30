#!/bin/bash
# Installs a background job on your Mac that downloads new yt-autopilot videos every 30 minutes
# into ~/Movies/yt-autopilot (one folder per video). Safe to run again; it just updates itself.
set -e
mkdir -p "$HOME/.yt-autopilot" "$HOME/Movies/yt-autopilot" "$HOME/Library/LaunchAgents"

cat > "$HOME/.yt-autopilot/sync.sh" <<'SCRIPT'
#!/bin/bash
DEST="$HOME/Movies/yt-autopilot"
mkdir -p "$DEST"
curl -fsSL "https://api.github.com/repos/ny4m1/yt-autopilot/releases?per_page=60" \
  | grep -o '"browser_download_url": *"[^"]*"' \
  | sed 's/.*"\(https[^"]*\)"/\1/' \
  | while read -r url; do
      tag=$(echo "$url" | awk -F/ '{print $(NF-1)}')
      file=$(basename "$url")
      mkdir -p "$DEST/$tag"
      if [ ! -f "$DEST/$tag/$file" ]; then
        if curl -fsSL -o "$DEST/$tag/$file.part" "$url"; then
          mv "$DEST/$tag/$file.part" "$DEST/$tag/$file"
        else
          rm -f "$DEST/$tag/$file.part"
        fi
      fi
    done
SCRIPT
chmod +x "$HOME/.yt-autopilot/sync.sh"

PLIST="$HOME/Library/LaunchAgents/com.ny4m1.yt-autopilot-sync.plist"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ny4m1.yt-autopilot-sync</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$HOME/.yt-autopilot/sync.sh</string></array>
  <key>StartInterval</key><integer>1800</integer>
  <key>RunAtLoad</key><true/>
</dict></plist>
PL

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
echo "Done. New videos will appear in: $HOME/Movies/yt-autopilot"
open "$HOME/Movies/yt-autopilot"
