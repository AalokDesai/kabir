"""
STEP 1 - Capture a face dataset for one user.

Usage:
    python engine/auth/dataset_gen.py
    python engine/auth/dataset_gen.py --name Aalok

For every new user, this script creates:
    engine/auth/dataset/<User Name>/User.<id>.<sample>.jpg

After capture, run:
    python engine/auth/trainer.py
"""

import argparse
import json
import re
from pathlib import Path

import cv2
from engine.auth.cascade import resolve_frontal_face_cascade


SAMPLE_COUNT = 100
BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
USERS_FILE = DATASET_DIR / "users.json"


def clean_user_name(name):
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not name:
        raise ValueError("User name is required.")
    return name


def safe_folder_name(name):
    folder = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", name).strip()
    folder = re.sub(r"\s+", "_", folder)
    folder = folder.strip(". ")
    if not folder:
        raise ValueError("User name must contain a valid folder character.")
    return folder


def load_users():
    if not USERS_FILE.exists():
        return {}
    try:
        with USERS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return {int(user_id): str(name) for user_id, name in data.items()}
    except (OSError, ValueError, TypeError):
        return {}


def save_users(users):
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    serializable = {str(user_id): name for user_id, name in sorted(users.items())}
    with USERS_FILE.open("w", encoding="utf-8") as file:
        json.dump(serializable, file, indent=2)


def get_or_create_user_id(users, user_name):
    for user_id, saved_name in users.items():
        if saved_name.casefold() == user_name.casefold():
            return user_id
    return max(users.keys(), default=0) + 1


def next_sample_number(user_dir, user_id):
    sample_numbers = []
    pattern = f"User.{user_id}."
    for image_path in user_dir.glob(f"{pattern}*.jpg"):
        try:
            sample_numbers.append(int(image_path.stem.split(".")[2]))
        except (IndexError, ValueError):
            continue
    return max(sample_numbers, default=0) + 1


def parse_args():
    parser = argparse.ArgumentParser(description="Capture face samples for one user.")
    parser.add_argument("--name", help="Name of the user to enroll.")
    parser.add_argument(
        "--samples",
        type=int,
        default=SAMPLE_COUNT,
        help=f"Number of samples to capture. Default: {SAMPLE_COUNT}.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    user_name = clean_user_name(args.name or input("Enter user name: "))
    sample_count = max(1, args.samples)

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    users = load_users()
    user_id = get_or_create_user_id(users, user_name)
    users[user_id] = user_name

    user_dir = DATASET_DIR / safe_folder_name(user_name)
    user_dir.mkdir(parents=True, exist_ok=True)
    sample_number = next_sample_number(user_dir, user_id)

    face_cascade = cv2.CascadeClassifier(resolve_frontal_face_cascade())
    if face_cascade.empty():
        raise RuntimeError("Could not load OpenCV Haar cascade.")

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        raise RuntimeError("Cannot open camera.")

    cam.set(3, 640)
    cam.set(4, 480)

    count = 0
    print(f"\n[INFO] Starting face capture for {user_name} (user ID: {user_id})")
    print(f"[INFO] Saving samples to: {user_dir}")
    print(f"[INFO] Look at the camera. Capturing {sample_count} samples...")
    print("[INFO] Press ESC to quit early.\n")

    while True:
        ret, frame = cam.read()
        if not ret:
            print("[ERROR] Cannot read from camera.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(30, 30))

        for (x, y, w, h) in faces:
            count += 1
            sample_path = user_dir / f"User.{user_id}.{sample_number}.jpg"
            sample_number += 1
            cv2.imwrite(str(sample_path), gray[y:y + h, x:x + w])

            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 180, 255), 2)
            cv2.putText(
                frame,
                f"{user_name} {count}/{sample_count}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 180, 255),
                2,
            )

            if count >= sample_count:
                break

        progress = min(frame.shape[1] - 40, int((count / sample_count) * (frame.shape[1] - 40)))
        cv2.rectangle(frame, (20, frame.shape[0] - 30), (20 + progress, frame.shape[0] - 15), (0, 180, 255), -1)
        cv2.rectangle(frame, (20, frame.shape[0] - 30), (frame.shape[1] - 20, frame.shape[0] - 15), (50, 50, 50), 1)

        cv2.putText(frame, "KABIR - FACE CAPTURE", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 180, 255), 2)
        cv2.imshow("Face Capture - Press ESC to quit", frame)

        key = cv2.waitKey(1)
        if key == 27 or count >= sample_count:
            break

    cam.release()
    cv2.destroyAllWindows()

    if count:
        save_users(users)

    if count >= sample_count:
        print(f"\n[OK] Dataset complete! {count} samples saved to: {user_dir}")
        print("[NEXT] Run: python engine/auth/trainer.py")
    else:
        print(f"\n[WARN] Captured only {count} samples.")
        if count:
            print("[NEXT] Re-run this script for more samples, then run: python engine/auth/trainer.py")


if __name__ == "__main__":
    main()
