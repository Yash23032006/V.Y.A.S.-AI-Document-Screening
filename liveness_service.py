# ============================================================
# LIVENESS DETECTION SERVICE
# ============================================================
#
# Goal: reduce the chance that the "live" selfie captured
# during face verification is actually a printed photo, a
# phone/tablet screen held up to the camera, or a static image.
#
# Built on OpenCV's bundled Haar cascade classifiers (shipped
# inside the opencv-python package already used elsewhere in
# this project) rather than an external landmark model, so it
# needs no extra downloads or GPU.
#
# Two operating modes:
#
#   PASSIVE  (single frame — what the current webcam capture
#             flow sends today):
#       - eyes-detected check (open eyes are far more reliably
#         detected by the eye cascade than closed ones)
#       - smile check (Haar smile cascade)
#       - sharpness check (a screen replay or printed photo
#         often looks softer / shows moire compared to a live
#         camera frame)
#
#   ACTIVE   (multiple frames — used if the frontend is later
#             upgraded to capture a short burst, e.g. for a
#             "blink" or "turn your head" challenge):
#       - blink detection (eyes toggle from detected -> not
#         detected -> detected across frames)
#       - head-movement detection (face bounding-box center
#         shifts across frames)
#
# This is a lightweight, explainable check — not a substitute
# for a certified liveness SDK, but enough to catch the most
# common spoofing attempt (holding up a photo of a photo).
# ============================================================

import cv2

_FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
_EYE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml"
)
_SMILE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_smile.xml"
)

_SHARPNESS_MIN = 40.0  # Laplacian variance floor for "not overly soft"


def _sharpness(gray):
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _largest_face(faces):
    if len(faces) == 0:
        return None
    return max(faces, key=lambda f: f[2] * f[3])


_FACE_ROI_STANDARD_SIZE = 240  # face crop is upscaled/downscaled to this
                                 # many pixels square before running the
                                 # eye/smile cascades, so detection quality
                                 # doesn't depend on the source resolution


def _analyze_single_frame(image_bgr):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    h_img, w_img = gray.shape
    # Faces smaller than ~8% of the shorter image side are treated as
    # noise; this scales with both small test images and full-size
    # webcam frames instead of assuming a fixed pixel size.
    min_face_side = max(30, int(min(h_img, w_img) * 0.08))

    faces = _FACE_CASCADE.detectMultiScale(
        gray,
        scaleFactor=1.05,
        minNeighbors=5,
        minSize=(min_face_side, min_face_side),
    )

    face = _largest_face(faces)

    if face is None:
        return None

    x, y, w, h = face
    face_roi = gray[y: y + h, x: x + w]

    # Normalize the face crop to a standard size so the eye/smile
    # cascades (tuned for a "normal" face resolution) work reliably
    # whether the source frame is a tiny thumbnail or a full webcam
    # capture.
    scaled_roi = cv2.resize(
        face_roi,
        (_FACE_ROI_STANDARD_SIZE, _FACE_ROI_STANDARD_SIZE),
        interpolation=cv2.INTER_CUBIC,
    )

    # Eyes are searched in the upper 65% of the face box.
    upper_roi = scaled_roi[0: int(_FACE_ROI_STANDARD_SIZE * 0.65), :]
    eyes = _EYE_CASCADE.detectMultiScale(
        upper_roi, scaleFactor=1.05, minNeighbors=6, minSize=(24, 24)
    )

    # Smile is searched in the lower 55% of the face box.
    lower_roi = scaled_roi[int(_FACE_ROI_STANDARD_SIZE * 0.45):, :]
    smiles = _SMILE_CASCADE.detectMultiScale(
        lower_roi, scaleFactor=1.6, minNeighbors=20, minSize=(30, 30)
    )

    return {
        "face_box": (int(x), int(y), int(w), int(h)),
        "face_center_x": float(x + w / 2.0),
        "face_width": float(w),
        "eyes_detected": len(eyes) >= 2,
        "eye_count": int(len(eyes)),
        "smiling": len(smiles) > 0,
        "sharpness": _sharpness(face_roi),
    }


def check_liveness(images):
    """
    images: a single BGR numpy image, or a list of BGR numpy
    images (a short burst of frames) for active checks.

    Returns a dict with:
        risk_score   0-100 (higher = more suspicious)
        status       LOW / MEDIUM / HIGH RISK
        mode         "passive" or "active"
        checks       breakdown of individual signals
        flags        human-readable explanations
    """

    if images is None:
        return {
            "status": "ERROR",
            "risk_score": 60.0,
            "flags": ["No image supplied for liveness check."],
        }

    frames = images if isinstance(images, list) else [images]
    frames = [f for f in frames if f is not None]

    if not frames:
        return {
            "status": "ERROR",
            "risk_score": 60.0,
            "flags": ["No usable frame supplied for liveness check."],
        }

    mode = "active" if len(frames) > 1 else "passive"

    flags = []
    risk = 0.0
    checks = {}

    frame_data = [_analyze_single_frame(f) for f in frames]
    valid = [d for d in frame_data if d is not None]

    if not valid:
        return {
            "status": "HIGH RISK",
            "risk_score": 80.0,
            "mode": mode,
            "checks": {},
            "flags": [
                "No face could be detected in the live capture, "
                "so liveness could not be confirmed."
            ],
        }

    latest = valid[-1]

    # --------------------------------------------------------
    # EYES DETECTED (a closed-eye or flat photo held at an odd
    # angle is much less likely to yield two detected eyes)
    # --------------------------------------------------------

    checks["eyes_open"] = latest["eyes_detected"]

    if not latest["eyes_detected"]:
        risk += 15.0
        flags.append(
            "Eyes could not be confidently detected as open in "
            "the captured frame."
        )

    checks["smile_detected"] = latest["smiling"]

    # --------------------------------------------------------
    # SHARPNESS (weak signal against screen replay / printed
    # photo attacks — real, close-up webcam frames are usually
    # sharper than a photo of a photo/screen)
    # --------------------------------------------------------

    sharpness_ok = latest["sharpness"] >= _SHARPNESS_MIN
    checks["sharpness_ok"] = sharpness_ok

    if not sharpness_ok:
        risk += 20.0
        flags.append(
            "Captured frame is unusually soft/blurred, which can "
            "indicate a photo held up to the camera rather than a "
            "live face."
        )

    # --------------------------------------------------------
    # ACTIVE CHECKS (only possible with multiple frames)
    # --------------------------------------------------------

    if mode == "active":

        eye_states = [d["eyes_detected"] for d in valid]
        blink_detected = (
            any(eye_states) and any(not s for s in eye_states)
        )
        checks["blink_detected"] = blink_detected

        if not blink_detected:
            risk += 25.0
            flags.append(
                "No blink was detected across the captured frames."
            )

        centers = [d["face_center_x"] for d in valid]
        widths = [d["face_width"] for d in valid if d["face_width"]]
        avg_width = sum(widths) / len(widths) if widths else 1.0

        movement_ratio = (max(centers) - min(centers)) / (avg_width + 1e-6)
        head_movement_detected = movement_ratio >= 0.08
        checks["head_movement_detected"] = head_movement_detected

        if not head_movement_detected:
            risk += 15.0
            flags.append(
                "No meaningful head movement was detected across "
                "the captured frames."
            )

    else:
        flags.append(
            "Only a single frame was captured, so blink and head-"
            "movement challenges could not be evaluated (passive "
            "checks only)."
        )

    risk = round(min(100.0, risk), 2)

    if risk <= 20:
        status = "LOW RISK"
    elif risk <= 50:
        status = "MEDIUM RISK"
    else:
        status = "HIGH RISK"

    if not flags:
        flags.append("No liveness concerns were detected.")

    return {
        "status": status,
        "risk_score": risk,
        "mode": mode,
        "checks": checks,
        "flags": flags,
    }
