"""
STEP 2 - Train the face recognizer after adding users.

Usage:
    python engine/auth/trainer.py

Reads images from engine/auth/dataset/. Supports both:
    dataset/User.1.1.jpg
    dataset/Aalok/User.1.1.jpg
    dataset/1_Aalok/User.1.1.jpg

The trained model is saved to engine/auth/trainer/trainer.yml.
"""

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from engine.auth.cascade import resolve_frontal_face_cascade


BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
TRAINER_DIR = BASE_DIR / "trainer"
TRAINER_FILE = TRAINER_DIR / "trainer.yml"
USERS_FILE = DATASET_DIR / "users.json"

TRAINER_DIR.mkdir(parents=True, exist_ok=True)


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


def infer_user_name(image_path, user_id):
    parent = image_path.parent.name
    prefix = f"{user_id}_"
    if parent.startswith(prefix):
        return parent[len(prefix):].replace("_", " ") or f"User {user_id}"
    if image_path.parent != DATASET_DIR:
        return parent.replace("_", " ") or f"User {user_id}"
    return f"User {user_id}"


def iter_image_paths(dataset_path):
    if not dataset_path.exists():
        return []
    return sorted(path for path in dataset_path.rglob("*.jpg") if path.is_file())


def get_images_and_labels(dataset_path):
    face_samples = []
    ids = []
    users = load_users()

    face_cascade = cv2.CascadeClassifier(resolve_frontal_face_cascade())

    for image_path in iter_image_paths(dataset_path):
        filename = image_path.name
        try:
            user_id = int(filename.split(".")[1])
        except (IndexError, ValueError):
            continue

        users.setdefault(user_id, infer_user_name(image_path, user_id))

        pil_img = Image.open(image_path).convert("L")
        img_array = np.array(pil_img, dtype="uint8")

        faces = face_cascade.detectMultiScale(img_array, scaleFactor=1.3, minNeighbors=5)
        if len(faces) == 0:
            face_samples.append(img_array)
            ids.append(user_id)
            continue

        for (x, y, w, h) in faces:
            face_samples.append(img_array[y:y + h, x:x + w])
            ids.append(user_id)

    save_users(users)
    return face_samples, ids, users


print("\n[INFO] Loading dataset...")
faces, ids, users = get_images_and_labels(DATASET_DIR)

if not faces:
    print("[ERROR] No faces found in dataset. Run dataset_gen.py first.")
    raise SystemExit(1)

unique_ids = sorted(set(ids))
names = ", ".join(f"{user_id}:{users.get(user_id, f'User {user_id}')}" for user_id in unique_ids)

print(f"[INFO] Training on {len(faces)} face samples for {len(unique_ids)} user(s): {names}")
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.train(faces, np.array(ids))
recognizer.write(str(TRAINER_FILE))

print(f"\n[OK] Model trained and saved to: {TRAINER_FILE}")
print("[NEXT] Run phoenix.py to start Kabir.")
