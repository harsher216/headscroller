# HeadScroller

A macOS menu bar app that lets you scroll by tilting your head. Uses your webcam and MediaPipe face tracking to detect head movement and convert it into scroll events.

## Requirements

- macOS 13+
- Python 3
- Webcam

## Install

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Download the MediaPipe face model (if not included)
curl -L -o face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task

# Build the app
./build.sh

# Run it
open HeadScroller.app

# Or install to Applications
cp -R HeadScroller.app /Applications/
```

## Usage

- Click the head icon in the menu bar
- Click **Start Tracking** to begin
- Tilt your head down to scroll down, up to scroll up
- Adjust **Sensitivity**, **Dead Zone**, and **Camera** from the menu
- Click **Recalibrate** if tracking drifts

## Permissions

The app will ask for:
- **Camera access** — to track your head
- **Accessibility access** — to send scroll events
