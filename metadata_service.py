# ============================================================
# METADATA ANALYSIS SERVICE
# ============================================================
#
# Examines EXIF metadata embedded in an uploaded image:
#   - Capture device (make / model)
#   - Original timestamp vs. modification timestamp
#   - Editing software signatures (Photoshop, GIMP, Snapseed,
#     PicsArt, Lightroom, remini, etc.)
#   - Presence / absence of EXIF entirely
#
# NOTE ON LIMITS:
# Metadata is easy for a motivated attacker to strip or forge,
# so this is one signal among several (OCR, tampering/ELA, face
# match) rather than a standalone verdict. A missing or edited
# EXIF block raises risk; it never certifies a document as real.
# ============================================================

import os
from PIL import Image, ExifTags

# ------------------------------------------------------------
# Known editing / re-touching software signatures that should
# raise suspicion when found in the Software / ProcessingSoftware
# EXIF tag of an identity document photo.
# ------------------------------------------------------------

EDITING_SOFTWARE_SIGNATURES = [
    "photoshop",
    "gimp",
    "snapseed",
    "picsart",
    "lightroom",
    "affinity photo",
    "canva",
    "remini",
    "facetune",
    "pixlr",
    "paint.net",
    "photoscape",
    "polarr",
]

TAG_NAME_LOOKUP = {v: k for k, v in ExifTags.TAGS.items()}


def _get_exif_dict(image):
    """
    Returns a {tag_name: value} dict from a PIL Image's EXIF
    block, or an empty dict if none is present / readable.
    """

    try:
        raw = image.getexif()
    except Exception:
        return {}

    if not raw:
        return {}

    exif = {}

    for tag_id, value in raw.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        exif[tag_name] = value

    return exif


def _decode(value):
    if isinstance(value, bytes):
        try:
            return value.decode(errors="ignore").strip("\x00").strip()
        except Exception:
            return str(value)
    return str(value).strip()


def analyze_metadata(image_path):
    """
    Main entry point. Returns a dict describing what was found
    plus a 0-100 risk score and human-readable flags.
    """

    flags = []
    risk = 0.0

    if not image_path or not os.path.exists(image_path):
        return {
            "status": "ERROR",
            "error": "File not found for metadata analysis.",
            "risk_score": 50.0,
            "flags": ["Could not analyze metadata (file missing)."],
        }

    extension = os.path.splitext(image_path)[1].lower()

    # PDFs and non-image uploads are out of scope for EXIF analysis.
    if extension not in [".jpg", ".jpeg", ".png", ".webp", ".tiff"]:
        return {
            "status": "SKIPPED",
            "risk_score": 0.0,
            "flags": [],
            "message": "Metadata analysis only applies to image uploads.",
        }

    try:
        image = Image.open(image_path)
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "risk_score": 50.0,
            "flags": ["Image could not be opened for metadata analysis."],
        }

    exif = _get_exif_dict(image)

    file_size = os.path.getsize(image_path)

    has_exif = bool(exif)

    camera_make = _decode(exif.get("Make", "")) if has_exif else ""
    camera_model = _decode(exif.get("Model", "")) if has_exif else ""
    software = _decode(exif.get("Software", "")) if has_exif else ""
    processing_software = (
        _decode(exif.get("ProcessingSoftware", "")) if has_exif else ""
    )
    datetime_original = (
        _decode(exif.get("DateTimeOriginal", "")) if has_exif else ""
    )
    datetime_modified = _decode(exif.get("DateTime", "")) if has_exif else ""
    gps_present = "GPSInfo" in exif if has_exif else False

    software_combined = f"{software} {processing_software}".lower()

    # --------------------------------------------------------
    # RULE 1: No EXIF at all.
    #
    # Many phone/camera photos carry EXIF by default. PNG
    # screenshots, re-saved / re-compressed, or scrubbed images
    # commonly show none. This alone is weak evidence, so it
    # gets a moderate weight.
    # --------------------------------------------------------

    if not has_exif:
        risk += 25.0
        flags.append(
            "No EXIF metadata found in the image "
            "(common for screenshots or re-saved/stripped files)."
        )

    else:
        # ----------------------------------------------------
        # RULE 2: Known editing software signature present.
        # ----------------------------------------------------

        matched_editor = next(
            (
                sig
                for sig in EDITING_SOFTWARE_SIGNATURES
                if sig in software_combined
            ),
            None,
        )

        if matched_editor:
            risk += 40.0
            flags.append(
                f"Image metadata indicates it was processed with "
                f"editing software ('{matched_editor.title()}')."
            )

        # ----------------------------------------------------
        # RULE 3: Original vs. modified timestamp mismatch.
        # ----------------------------------------------------

        if datetime_original and datetime_modified:
            if datetime_original != datetime_modified:
                risk += 15.0
                flags.append(
                    "Original capture time and last-modified time "
                    "in the metadata do not match, suggesting the "
                    "file was edited after capture."
                )

        # ----------------------------------------------------
        # RULE 4: No capture-device information at all, despite
        # having an EXIF block (common when metadata was
        # partially rebuilt by editing tools).
        # ----------------------------------------------------

        if not camera_make and not camera_model:
            risk += 10.0
            flags.append(
                "EXIF block is present but contains no camera "
                "make/model information."
            )

    risk = round(min(100.0, risk), 2)

    if risk <= 20:
        status = "LOW RISK"
    elif risk <= 50:
        status = "MEDIUM RISK"
    else:
        status = "HIGH RISK"

    if not flags:
        flags.append("No suspicious metadata indicators were found.")

    return {
        "status": status,
        "risk_score": risk,
        "flags": flags,
        "has_exif": has_exif,
        "camera_make": camera_make or None,
        "camera_model": camera_model or None,
        "software": (software or processing_software) or None,
        "datetime_original": datetime_original or None,
        "datetime_modified": datetime_modified or None,
        "gps_present": gps_present,
        "file_size_bytes": file_size,
    }
