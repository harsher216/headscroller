#!/usr/bin/env python3
"""
HeadScroller — tilt your head to scroll any app.

Uses MediaPipe FaceLandmarker to detect head pitch (tilt forward/backward).
Sends scroll events via CoreGraphics (macOS, no extra deps).

Controls:
  q        — quit
  d        — toggle debug overlay
  +/-      — increase/decrease sensitivity
  [/]      — increase/decrease dead zone
  c        — recalibrate neutral position
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import argparse
import ctypes
import ctypes.util
import os
import json
import subprocess

# ── Scroll backend using ctypes + CoreGraphics ──────────────────────────────
_cg_path = ctypes.util.find_library("CoreGraphics")
_cg = ctypes.cdll.LoadLibrary(_cg_path)

_cg.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
_cg.CGEventCreateScrollWheelEvent.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32,
]
_cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

_cf_path = ctypes.util.find_library("CoreFoundation")
_cf = ctypes.cdll.LoadLibrary(_cf_path)
_cf.CFRelease.argtypes = [ctypes.c_void_p]

kCGScrollEventUnitLine = 1
kCGHIDEventTap = 0


PIPE_SCROLL_MODE = False


def scroll(amount):
    amt = int(amount)
    if amt == 0:
        return
    if PIPE_SCROLL_MODE:
        # Output scroll command for parent process to execute
        import sys
        sys.stdout.write(f"SCROLL:{amt}\n")
        sys.stdout.flush()
        return
    event = _cg.CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, amt)
    if event:
        _cg.CGEventPost(kCGHIDEventTap, event)
        _cf.CFRelease(event)


# ── MediaPipe FaceLandmarker setup ───────────────────────────────────────────
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# Key landmark indices (same as the classic 468-point mesh)
NOSE_TIP = 1
FOREHEAD = 10
CHIN = 152

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_landmarker.task")
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULTS = {"sensitivity": 10.0, "deadzone": 0.04, "cam": 1}


def load_settings():
    """Load settings from JSON file, falling back to defaults."""
    settings = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                saved = json.load(f)
            settings.update(saved)
        except (json.JSONDecodeError, IOError):
            pass
    return settings


def save_settings(sensitivity, deadzone, cam):
    """Persist current settings to JSON file."""
    data = {"sensitivity": sensitivity, "deadzone": deadzone, "cam": cam}
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass


def get_head_pitch(landmarks):
    """
    Estimate head pitch from normalized face landmarks.
    Returns roughly [-1, 1]: negative = tilted down, positive = tilted up.
    """
    nose = landmarks[NOSE_TIP]
    forehead = landmarks[FOREHEAD]
    chin = landmarks[CHIN]

    face_height = chin.y - forehead.y
    if face_height < 0.01:
        return 0.0

    mid_y = (forehead.y + chin.y) / 2.0
    offset = nose.y - mid_y

    return offset / face_height


def control_main():
    """Persistent mode: init heavy deps once, toggle camera via stdin commands."""
    import sys
    import select

    global PIPE_SCROLL_MODE
    PIPE_SCROLL_MODE = True

    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model not found at {MODEL_PATH}", flush=True)
        return

    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = FaceLandmarker.create_from_options(options)

    print("READY", flush=True)

    def poll_cmd():
        if select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline()
            return line.strip() if line else "QUIT"
        return None

    def wait_cmd():
        line = sys.stdin.readline()
        return line.strip() if line else "QUIT"

    while True:
        cmd = wait_cmd()
        if cmd == "QUIT":
            break
        if cmd != "START":
            continue

        s = load_settings()
        sensitivity, deadzone, cam = s["sensitivity"], s["deadzone"], s["cam"]

        cap = cv2.VideoCapture(cam)
        if not cap.isOpened():
            print("ERROR: camera unavailable", flush=True)
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print("Calibrating", flush=True)
        neutral_pitch = None
        calibration_readings = []
        calibration_frames = 15
        pitch_smooth = 0.0
        alpha = 0.35
        scroll_accumulator = 0.0
        last_time = time.time()
        last_settings_check = time.time()
        frame_ts = 0
        stop_all = False

        while True:
            ctrl = poll_cmd()
            if ctrl in ("STOP", "QUIT"):
                stop_all = (ctrl == "QUIT")
                break
            if ctrl == "RECAL":
                neutral_pitch = None
                calibration_readings = []
                pitch_smooth = 0.0
                scroll_accumulator = 0.0
                print("Calibrating", flush=True)

            ret, frame = cap.read()
            if not ret:
                break

            now_check = time.time()
            if now_check - last_settings_check > 0.5:
                last_settings_check = now_check
                try:
                    fresh = load_settings()
                    sensitivity = fresh["sensitivity"]
                    deadzone = fresh["deadzone"]
                except Exception:
                    pass

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            frame_ts += 33
            results = landmarker.detect_for_video(mp_image, frame_ts)

            if not results.face_landmarks:
                continue

            raw_pitch = get_head_pitch(results.face_landmarks[0])

            if neutral_pitch is None:
                calibration_readings.append(raw_pitch)
                if len(calibration_readings) >= calibration_frames:
                    neutral_pitch = float(np.mean(calibration_readings))
                    print("Calibrated", flush=True)
                continue

            pitch = raw_pitch - neutral_pitch
            pitch_smooth = alpha * pitch + (1 - alpha) * pitch_smooth

            effective = 0.0
            if abs(pitch_smooth) > deadzone:
                effective = pitch_smooth - np.sign(pitch_smooth) * deadzone

            now = time.time()
            dt = now - last_time
            last_time = now

            scroll_accumulator += -effective * sensitivity * 60 * dt
            scroll_int = int(scroll_accumulator)
            if scroll_int != 0:
                scroll(scroll_int)
                scroll_accumulator -= scroll_int

        cap.release()
        print("STOPPED", flush=True)
        if stop_all:
            break

    landmarker.close()


def main():
    # Load persisted settings as defaults
    saved = load_settings()

    parser = argparse.ArgumentParser(description="HeadScroller — tilt to scroll")
    parser.add_argument("--cam", type=int, default=saved["cam"],
                        help=f"Camera index (saved: {saved['cam']})")
    parser.add_argument("--sensitivity", type=float, default=saved["sensitivity"],
                        help=f"Scroll speed multiplier (saved: {saved['sensitivity']})")
    parser.add_argument("--deadzone", type=float, default=saved["deadzone"],
                        help=f"Pitch dead zone (saved: {saved['deadzone']})")
    parser.add_argument("--no-debug", action="store_true",
                        help="Start with debug overlay hidden")
    parser.add_argument("--no-window", action="store_true",
                        help="Run headless (no preview window)")
    parser.add_argument("--pipe-scroll", action="store_true",
                        help="Output scroll commands to stdout instead of posting CGEvents")
    parser.add_argument("--control", action="store_true",
                        help="Persistent control mode: read START/STOP/RECAL/QUIT from stdin")
    args = parser.parse_args()

    if args.control:
        control_main()
        return

    global PIPE_SCROLL_MODE
    PIPE_SCROLL_MODE = args.pipe_scroll

    sensitivity = args.sensitivity
    deadzone = args.deadzone
    cam = args.cam
    show_debug = not args.no_debug
    show_window = not args.no_window

    # Save whatever we're starting with (merges CLI overrides into the file)
    save_settings(sensitivity, deadzone, cam)

    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model not found at {MODEL_PATH}")
        print("Download it with:")
        print('  curl -L -o face_landmarker.task "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"')
        return

    # Set up FaceLandmarker
    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = FaceLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(cam)
    if not cap.isOpened():
        print("ERROR: Could not open camera. Check --cam index.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Smoothing
    pitch_smooth = 0.0
    alpha = 0.35

    # Calibration
    neutral_pitch = None
    calibration_frames = 15
    calibration_readings = []

    # Create preview window as always-on-top, small overlay that doesn't steal focus
    preview_initialized = False
    prev_app = None
    if show_window:
        # Remember which app is active before we create the window
        try:
            prev_app = subprocess.check_output([
                "osascript", "-e",
                'tell application "System Events" to get name of first process whose frontmost is true'
            ], stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            pass
        cv2.namedWindow("HeadScroller", cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL)
        cv2.resizeWindow("HeadScroller", 320, 240)
        cv2.setWindowProperty("HeadScroller", cv2.WND_PROP_TOPMOST, 1)

    print("HeadScroller starting!", flush=True)
    print("Look straight at the camera for calibration...", flush=True)
    print(f"Sensitivity: {sensitivity}  |  Dead zone: {deadzone}", flush=True)
    print("Keys: q=quit  d=debug  +/-=sensitivity  [/]=deadzone  c=recalibrate", flush=True)

    scroll_accumulator = 0.0
    last_time = time.time()
    last_settings_check = time.time()
    frame_ts = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Hot-reload settings from file every 0.5s
        now_check = time.time()
        if now_check - last_settings_check > 0.5:
            last_settings_check = now_check
            try:
                fresh = load_settings()
                if fresh["sensitivity"] != sensitivity or fresh["deadzone"] != deadzone:
                    sensitivity = fresh["sensitivity"]
                    deadzone = fresh["deadzone"]
            except Exception:
                pass

        frame = cv2.flip(frame, 1)
        img_h, img_w = frame.shape[:2]

        # Convert to MediaPipe Image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        frame_ts += 33  # ~30fps timestamp in ms

        results = landmarker.detect_for_video(mp_image, frame_ts)

        face_detected = False

        if results.face_landmarks:
            face_detected = True
            landmarks = results.face_landmarks[0]
            raw_pitch = get_head_pitch(landmarks)

            # Calibration phase
            if neutral_pitch is None:
                calibration_readings.append(raw_pitch)
                if len(calibration_readings) >= calibration_frames:
                    neutral_pitch = np.mean(calibration_readings)
                    print(f"Calibrated! Neutral pitch: {neutral_pitch:.4f}", flush=True)
                else:
                    if show_window:
                        pct = int(len(calibration_readings) / calibration_frames * 100)
                        cv2.putText(frame, f"Calibrating... {pct}%",
                                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                                    (0, 255, 255), 2)
                        cv2.imshow("HeadScroller", frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    continue

            pitch = raw_pitch - neutral_pitch
            pitch_smooth = alpha * pitch + (1 - alpha) * pitch_smooth

            effective = 0.0
            if abs(pitch_smooth) > deadzone:
                effective = pitch_smooth - np.sign(pitch_smooth) * deadzone

            now = time.time()
            dt = now - last_time
            last_time = now

            # effective > 0 = head down → scroll down (negative CGEvent value)
            # effective < 0 = head up → scroll up (positive CGEvent value)
            scroll_amount = -effective * sensitivity * 60 * dt
            scroll_accumulator += scroll_amount

            scroll_int = int(scroll_accumulator)
            if scroll_int != 0:
                scroll(scroll_int)
                scroll_accumulator -= scroll_int
                print(f"SCROLL: {scroll_int} (pitch={pitch_smooth:.3f} eff={effective:.3f})", flush=True)

            # ── Debug overlay ────────────────────────────────────────────
            if show_window and show_debug:
                for idx in [NOSE_TIP, FOREHEAD, CHIN]:
                    lm = landmarks[idx]
                    x, y = int(lm.x * img_w), int(lm.y * img_h)
                    cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

                # Pitch bar on right side
                bar_x = img_w - 60
                bar_cy = img_h // 2
                bar_h = int(pitch_smooth * 500)
                color = (0, 0, 255) if abs(pitch_smooth) > deadzone else (128, 128, 128)
                cv2.rectangle(frame, (bar_x, bar_cy),
                              (bar_x + 30, bar_cy + bar_h), color, -1)
                dz_px = int(deadzone * 500)
                cv2.line(frame, (bar_x - 5, bar_cy - dz_px),
                         (bar_x + 35, bar_cy - dz_px), (255, 255, 0), 1)
                cv2.line(frame, (bar_x - 5, bar_cy + dz_px),
                         (bar_x + 35, bar_cy + dz_px), (255, 255, 0), 1)

                cv2.putText(frame, f"Pitch: {pitch_smooth:+.3f}", (20, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Sens: {sensitivity:.1f}  DZ: {deadzone:.3f}",
                            (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

                if effective > 0.01:
                    label, lcolor = "v DOWN v", (0, 0, 255)
                elif effective < -0.01:
                    label, lcolor = "^ UP ^", (0, 255, 0)
                else:
                    label, lcolor = "---", (128, 128, 128)
                cv2.putText(frame, label, (20, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, lcolor, 3)

        elif show_window and show_debug:
            cv2.putText(frame, "No face detected", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

        if show_window:
            cv2.imshow("HeadScroller", frame)

            # After first frame, return focus to whatever app was active before
            if not preview_initialized:
                preview_initialized = True
                if prev_app:
                    cv2.waitKey(50)
                    subprocess.Popen([
                        "osascript", "-e",
                        f'tell application "{prev_app}" to activate'
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                save_settings(sensitivity, deadzone, cam)
                break
            elif key == ord('d'):
                show_debug = not show_debug
            elif key in (ord('+'), ord('=')):
                sensitivity = min(30.0, sensitivity + 1.0)
                save_settings(sensitivity, deadzone, cam)
                print(f"Sensitivity: {sensitivity:.1f}")
            elif key == ord('-'):
                sensitivity = max(1.0, sensitivity - 1.0)
                save_settings(sensitivity, deadzone, cam)
                print(f"Sensitivity: {sensitivity:.1f}")
            elif key == ord(']'):
                deadzone = min(0.2, deadzone + 0.005)
                save_settings(sensitivity, deadzone, cam)
                print(f"Dead zone: {deadzone:.3f}")
            elif key == ord('['):
                deadzone = max(0.0, deadzone - 0.005)
                save_settings(sensitivity, deadzone, cam)
                print(f"Dead zone: {deadzone:.3f}")
            elif key == ord('c'):
                neutral_pitch = None
                calibration_readings = []
                pitch_smooth = 0.0
                scroll_accumulator = 0.0
                print("Recalibrating... look straight at camera")
        else:
            time.sleep(0.01)

    save_settings(sensitivity, deadzone, cam)
    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print("HeadScroller stopped.")


if __name__ == "__main__":
    main()
