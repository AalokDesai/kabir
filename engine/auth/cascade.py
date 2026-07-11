from pathlib import Path

import cv2


CASCADE_FILENAME = "haarcascade_frontalface_default.xml"


def resolve_frontal_face_cascade():
    candidates = []

    cv2_data = getattr(cv2, "data", None)
    haarcascades = getattr(cv2_data, "haarcascades", "") if cv2_data else ""
    if haarcascades:
        candidates.append(Path(haarcascades) / CASCADE_FILENAME)

    cv2_file = getattr(cv2, "__file__", "")
    if cv2_file:
        cv2_dir = Path(cv2_file).resolve().parent
        candidates.extend([
            cv2_dir / "data" / CASCADE_FILENAME,
            cv2_dir.parent / "cv2" / "data" / CASCADE_FILENAME,
        ])

    local_dir = Path(__file__).resolve().parent
    candidates.extend([
        local_dir / CASCADE_FILENAME,
        local_dir / "data" / CASCADE_FILENAME,
    ])

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    checked = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"{CASCADE_FILENAME} was not found. Reinstall OpenCV with: "
        "python -m pip install --force-reinstall opencv-contrib-python==4.10.0.84. "
        f"Checked: {checked}"
    )

