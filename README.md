# HeadScroller

A macOS menu bar app that lets you scroll by tilting your head. Uses your webcam and MediaPipe face tracking to detect head movement and convert it into scroll events.

## Download

**[Download HeadScroller.zip](https://github.com/harsher216/headscroller/releases/latest/download/HeadScroller.zip)** (macOS 13+, Apple Silicon)

1. Download and unzip
2. Drag `HeadScroller.app` to `/Applications/`
3. Open it — the head icon appears in your menu bar
4. Grant Camera and Accessibility permissions when prompted

No Python, no terminal, no dependencies needed.

## Build from source (optional)

<details>
<summary>Click to expand</summary>

### Requirements

- macOS 13+ (Apple Silicon)
- Python 3
- Webcam

```bash
git clone https://github.com/harsher216/headscroller.git
cd headscroller

# Install Python dependencies
pip3 install pyinstaller mediapipe opencv-python numpy matplotlib

# Build the self-contained .app bundle
./build.sh

# Run it
open HeadScroller.app
```

### Install to Applications

```bash
cp -R HeadScroller.app /Applications/
```

</details>

## Auto-start on login

To have HeadScroller start automatically when you log in:

```bash
mkdir -p ~/Library/LaunchAgents

cat > ~/Library/LaunchAgents/com.headscroller.menubar.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.headscroller.menubar</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/HeadScroller.app/Contents/MacOS/HeadScrollerMenuBar</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.headscroller.menubar.plist
```

If you installed the app somewhere other than `/Applications/`, update the path above accordingly.

To stop auto-start:

```bash
launchctl unload ~/Library/LaunchAgents/com.headscroller.menubar.plist
rm ~/Library/LaunchAgents/com.headscroller.menubar.plist
```

## Usage

- Click the head icon in the menu bar
- Click **Start Tracking** to begin
- Tilt your head down to scroll down, up to scroll up
- Adjust **Sensitivity**, **Dead Zone**, and **Camera** from the menu
- Click **Recalibrate** if tracking drifts

## Permissions

macOS will prompt you for:
- **Camera access** — to track your head
- **Accessibility access** — to send scroll events (System Settings > Privacy & Security > Accessibility)

## Settings

Settings are saved to `~/Library/Application Support/HeadScroller/settings.json` and persist between sessions. You can adjust everything from the menu bar dropdown:

- **Sensitivity** — how fast scrolling responds to head movement
- **Dead Zone** — how much head tilt is ignored (prevents accidental scrolling)
- **Camera** — which camera to use (if you have multiple)

## Troubleshooting

- **App doesn't scroll**: Make sure Accessibility access is granted in System Settings > Privacy & Security > Accessibility
- **Wrong camera selected**: Change it from the Camera submenu. Camera 0 is usually an iPhone (Continuity Camera), Camera 1 is usually the built-in MacBook camera
- **Tracking feels off**: Click Recalibrate and hold your head in a neutral position
- **After updating: app stops scrolling even though Accessibility looks enabled**: macOS revokes Accessibility permission when an app's signature changes between versions. Fix:
  1. Quit HeadScroller (menu bar → Quit)
  2. System Settings → Privacy & Security → **Accessibility** → select HeadScroller → click the **−** button to remove it
  3. Do the same under **Privacy & Security → Camera** if scrolling still fails
  4. Replace the old app: drag the new `HeadScroller.app` into `/Applications/` (overwrite)
  5. Open HeadScroller and re-grant both permissions when prompted

  (This is an unavoidable side effect of the app being ad-hoc signed. A future release signed with an Apple Developer ID will make updates seamless.)
