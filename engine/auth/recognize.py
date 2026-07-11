"""
Face Authentication module — called by phoenix.py on startup.
Returns 1 if face recognized, 0 if not.

Streams live webcam frames to the browser via eel base64 JPEG.

KEY FIX: eel JS calls from background threads must use eel.sleep(0)
         to pump the websocket event loop. time.sleep() blocks it entirely
         and the browser never receives the camera frames.
"""

import cv2
import os
import base64
import time
import json
import eel
from datetime import datetime, timezone
from engine.auth.cascade import resolve_frontal_face_cascade

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(__file__)
TRAINER_FILE = os.path.join(BASE_DIR, "trainer", "trainer.yml")
USERS_FILE   = os.path.join(BASE_DIR, "dataset", "users.json")
AUTH_STATE_FILE = os.path.join(BASE_DIR, "auth_state.json")
AUTH_EVENTS_FILE = os.path.join(BASE_DIR, "auth_events.jsonl")

# ── Config ────────────────────────────────────────────────────────────────────
# LBPH confidence: 0 = perfect match, 100+ = very different face.
# 45 is strict — only the trained face passes.
# If your face is being rejected, raise to 50. Never go above 55.
CONFIDENCE_THRESHOLD = 45

# Extra safety: completely reject if confidence is above this (unknown person)
REJECT_THRESHOLD     = 55    # anything >= 55 is treated as unknown regardless of ID

MAX_ATTEMPTS         = 200   # ~20 seconds at ~10fps
CONSECUTIVE_NEEDED   = 5     # Consecutive matches needed to pass (stricter)
LOCKOUT_FAILURE_LIMIT = 3
LOCKOUT_SECONDS = 120


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_auth_state():
    if not os.path.exists(AUTH_STATE_FILE):
        return {"failed_sessions": 0, "locked_until": 0}
    try:
        with open(AUTH_STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
        return {
            "failed_sessions": int(state.get("failed_sessions", 0) or 0),
            "locked_until": float(state.get("locked_until", 0) or 0),
        }
    except (OSError, ValueError, TypeError):
        return {"failed_sessions": 0, "locked_until": 0}


def save_auth_state(state):
    with open(AUTH_STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


def record_auth_event(status, user="", reason="", failed_sessions=None, locked_until=None):
    event = {
        "timestamp": utc_now(),
        "status": status,
        "user": user or "",
        "reason": reason or "",
    }
    if failed_sessions is not None:
        event["failed_sessions"] = failed_sessions
    if locked_until:
        event["locked_until"] = locked_until
    try:
        with open(AUTH_EVENTS_FILE, "a", encoding="utf-8") as file:
            file.write(json.dumps(event, separators=(",", ":")) + "\n")
    except OSError:
        pass


def auth_lockout_remaining():
    state = load_auth_state()
    remaining = int(max(0, state.get("locked_until", 0) - time.time()))
    if remaining <= 0 and state.get("locked_until", 0):
        state["locked_until"] = 0
        save_auth_state(state)
    return remaining


def record_auth_success(user_name):
    save_auth_state({"failed_sessions": 0, "locked_until": 0})
    record_auth_event("success", user=user_name, reason="recognized")


def record_auth_failure(reason):
    state = load_auth_state()
    state["failed_sessions"] = int(state.get("failed_sessions", 0) or 0) + 1
    if state["failed_sessions"] >= LOCKOUT_FAILURE_LIMIT:
        state["locked_until"] = time.time() + LOCKOUT_SECONDS
    save_auth_state(state)
    record_auth_event(
        "failure",
        reason=reason,
        failed_sessions=state["failed_sessions"],
        locked_until=state.get("locked_until", 0),
    )
    return state


def show_lockout_countdown(seconds):
    record_auth_event("blocked", reason="cooldown_active", locked_until=time.time() + seconds)
    while seconds > 0:
        eel.setFaceAuthText(f"AUTH LOCKED - TRY AGAIN IN {seconds}s")()
        eel.setStatus(f"Face auth cooldown: {seconds}s")()
        eel.sleep(1)
        seconds -= 1


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return {int(user_id): str(name) for user_id, name in data.items()}
    except (OSError, ValueError, TypeError):
        return {}


def AuthenticateFace():
    """
    Opens webcam, runs LBPH recognition, streams frames to browser.
    Returns 1 (authenticated) or 0 (failed).
    """

    # ── Guard: trainer must exist ─────────────────────────────────────────────
    remaining = auth_lockout_remaining()
    if remaining > 0:
        show_lockout_countdown(remaining)
        return 0

    if not os.path.exists(TRAINER_FILE):
        eel.setFaceAuthText("MODEL NOT FOUND — RUN trainer.py FIRST")()
        eel.setStatus("No face model. Run engine/auth/trainer.py")()
        record_auth_event("error", reason="trainer_missing")
        time.sleep(3)
        return 0

    # ── Load LBPH model + cascade ─────────────────────────────────────────────
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(TRAINER_FILE)
    except Exception as e:
        eel.setFaceAuthText(f"MODEL LOAD ERROR: {e}")()
        record_auth_event("error", reason=f"model_load_error: {e}")
        time.sleep(3)
        return 0

    try:
        cascade_path = resolve_frontal_face_cascade()
    except FileNotFoundError as e:
        eel.setFaceAuthText("HAAR CASCADE NOT FOUND")()
        eel.setStatus("Reinstall opencv-contrib-python 4.10.0.84")()
        record_auth_event("error", reason=str(e))
        time.sleep(3)
        return 0

    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        eel.setFaceAuthText("HAAR CASCADE NOT FOUND")()
        record_auth_event("error", reason=f"haar_cascade_unreadable: {cascade_path}")
        time.sleep(2)
        return 0

    # ── Open camera ───────────────────────────────────────────────────────────
    # CAP_DSHOW = DirectShow backend, much faster startup on Windows
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(0)   # fallback

    if not cam.isOpened():
        eel.setFaceAuthText("CAMERA NOT FOUND")()
        eel.setStatus("Cannot open webcam (index 0).")()
        record_auth_event("error", reason="camera_missing")
        time.sleep(3)
        return 0

    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cam.set(cv2.CAP_PROP_FPS, 15)

    # Warm up — discard first few frames (often black/green on Windows)
    for _ in range(6):
        cam.read()
        eel.sleep(0.03)

    attempts      = 0
    consecutive   = 0
    authenticated = False
    authenticated_user_name = ""
    users = load_users()

    eel.setFaceAuthText("SCANNING FACE . . .")()

    while attempts < MAX_ATTEMPTS:
        ret, frame = cam.read()
        if not ret or frame is None:
            attempts += 1
            eel.sleep(0.05)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)   # boost contrast in low light

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(50, 50),
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        recognized_this_frame = False

        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            user_id, confidence = recognizer.predict(face_roi)

            # Any trained user can pass. Unknown faces are rejected by confidence.
            is_authorized = confidence < CONFIDENCE_THRESHOLD and confidence < REJECT_THRESHOLD

            if is_authorized:
                authenticated_user_name = users.get(user_id, f"User {user_id}")
                label = f"{authenticated_user_name.upper()} [{int(confidence)}]"
                color = (0, 230, 80)
                recognized_this_frame = True
            else:
                label = f"UNKNOWN [{int(confidence)}]"
                color = (0, 60, 255)

            # Draw HUD overlay on frame
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            cv2.rectangle(frame, (x, y-28), (x+w, y), color, -1)
            cv2.putText(frame, label, (x+4, y-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

        # ── Stream frame to browser as base64 JPEG ────────────────────────────
        try:
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 55])
            b64 = base64.b64encode(buffer).decode("utf-8")
            eel.updateFaceCam(b64)()
        except Exception:
            pass

        # ── Update status text ────────────────────────────────────────────────
        if recognized_this_frame:
            consecutive += 1
            eel.setFaceAuthText(
                f"RECOGNIZED — VERIFYING  {consecutive} / {CONSECUTIVE_NEEDED}"
            )()
        else:
            if consecutive > 0:
                consecutive = 0
            eel.setFaceAuthText(
                "SCANNING FACE . . ." if len(faces) == 0 else "FACE NOT RECOGNIZED"
            )()

        if consecutive >= CONSECUTIVE_NEEDED:
            authenticated = True
            break

        attempts += 1

        # ── KEY FIX ───────────────────────────────────────────────────────────
        # eel.sleep() instead of time.sleep() — pumps the eel/gevent event loop
        # so the browser actually receives the JS callback with the frame data.
        # time.sleep() blocks the greenlet and frames never arrive.
        eel.sleep(0.07)

    cam.release()

    if authenticated:
        record_auth_success(authenticated_user_name)
        if authenticated_user_name:
            eel.setFaceAuthText(f"AUTHENTICATION SUCCESSFUL - {authenticated_user_name}")()
            try:
                eel.setStatus(f"Authenticated as {authenticated_user_name}")()
            except Exception:
                pass
        else:
            eel.setFaceAuthText("AUTHENTICATION SUCCESSFUL")()
        return 1
    else:
        state = record_auth_failure("face_not_recognized")
        if state.get("locked_until", 0):
            eel.setFaceAuthText(f"AUTHENTICATION FAILED - LOCKED FOR {LOCKOUT_SECONDS}s")()
            try:
                eel.setStatus(f"Face auth locked for {LOCKOUT_SECONDS}s")()
            except Exception:
                pass
        else:
            remaining_attempts = max(0, LOCKOUT_FAILURE_LIMIT - state.get("failed_sessions", 0))
            eel.setFaceAuthText(f"AUTHENTICATION FAILED - {remaining_attempts} RETRIES LEFT")()
        return 0
