import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    jsonify,
    session
)

import sqlite3
import os
import base64
import numpy as np
import cv2

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename

from ocr_service import process_document
from validation_service import validate_document
from tampering_service import analyze_tampering
from face_service import prepare_document_face
from blockchain_service import register_document


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "dev-secret-change-in-production"
)

DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# OVERALL RISK SCORING
# ============================================================
#
# All scoring logic lives in risk_scoring_service.py (previously
# this file had its own copy-pasted duplicate of the same
# functions, which was dead weight and a maintenance risk -
# consolidated here to a single source of truth).
# ============================================================

from risk_scoring_service import (
    calculate_overall_risk as _calculate_overall_risk,
    get_risk_level as _get_risk_level,
)
from metadata_service import analyze_metadata
from liveness_service import check_liveness
from deepfake_service import analyze_deepfake_indicators


def calculate_overall_risk(
    result,
    validation,
    tampering,
    face_result=None,
    face_verification=None,
    metadata=None,
    liveness=None,
    deepfake=None
):
    return _calculate_overall_risk(
        result,
        validation,
        tampering,
        face_result=face_result,
        face_verification=face_verification,
        metadata=metadata,
        liveness=liveness,
        deepfake=deepfake
    )


def _print_overall_risk(overall_risk):

    print()
    print("=" * 50)
    print("             OVERALL RISK ASSESSMENT")
    print("=" * 50)

    print(
        f"Fake Risk Score : "
        f"{overall_risk['risk_score']:.2f}%"
    )

    print(
        f"Risk Level      : "
        f"{overall_risk['risk_level']}"
    )

    print("-" * 50)

    components = overall_risk.get("components", {})

    for label, key in [
        ("OCR Risk", "ocr"),
        ("Validation Risk", "validation"),
        ("Tampering Risk", "tampering"),
        ("Face Risk", "face"),
        ("Metadata Risk", "metadata"),
        ("Liveness Risk", "liveness"),
        ("Deepfake Risk", "deepfake"),
    ]:
        value = components.get(key)
        if value is None:
            continue
        print(f"{label:<16}: {value:.2f}%")

    print(
        f"Face Verified   : "
        f"{overall_risk.get('face_verified', False)}"
    )

    print("-" * 50)

    print(
        "Comment         : "
        + overall_risk["comment"]
    )

    print("=" * 50)


# ============================================================
# DATABASE
# ============================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# CREATE TABLE
# ============================================================

def create_table():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            mobile TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            organization TEXT NOT NULL,

            password TEXT NOT NULL

        )
    """)

    conn.commit()

    conn.close()
create_table()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return redirect(
        url_for("login")
    )


# ============================================================
# SIGNUP
# ============================================================

@app.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    if request.method == "POST":

        name = request.form["name"]

        mobile = request.form["mobile"]

        email = request.form["email"]

        organization = request.form["organization"]

        password = request.form["password"]

        hashed_password = generate_password_hash(
            password
        )

        try:

            conn = get_db()

            conn.execute(
                """
                INSERT INTO users
                (
                    name,
                    mobile,
                    email,
                    organization,
                    password
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    mobile,
                    email,
                    organization,
                    hashed_password
                )
            )

            conn.commit()

            conn.close()

            return redirect(
                url_for("login")
            )

        except sqlite3.IntegrityError:

            return "Email already registered!"

    return render_template(
        "signup.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            return redirect(
                url_for("dashboard")
            )

        return "Invalid Email or Password!"

    return render_template(
        "login.html"
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    return render_template(
        "dashboard.html",
        result={},
        validation={},
        tampering={},
        face_result={},
        overall_risk=None,
        document_filename=""
    )


# ============================================================
# UPLOADED FILES
# ============================================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ============================================================
# UPLOAD + OCR + VALIDATION + TAMPERING + FACE
# ============================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    file = request.files.get(
        "document"
    )

    # --------------------------------------------------------
    # CHECK FILE
    # --------------------------------------------------------

    if not file:

        return "No document selected!"

    if file.filename == "":

        return "No document selected!"

    # --------------------------------------------------------
    # CREATE UPLOAD FOLDER
    # --------------------------------------------------------

    upload_folder = UPLOAD_FOLDER


    # --------------------------------------------------------
    # SECURE FILE NAME
    # --------------------------------------------------------

    filename = secure_filename(
        file.filename
    )

    filepath = os.path.join(
        upload_folder,
        filename
    )

    # --------------------------------------------------------
    # SAVE FILE
    # --------------------------------------------------------

    file.save(
        filepath
    )

    # ========================================================
    # PREPARE DOCUMENT FACE
    # ========================================================

    face_result = None

    image_extensions = [
        ".jpg",
        ".jpeg",
        ".png"
    ]

    extension = os.path.splitext(
        filepath
    )[1].lower()

    if extension in image_extensions:

        try:

            face_result = prepare_document_face(
                filepath
            )

        except Exception as e:

            print(
                "Face detection failed:",
                e
            )

            face_result = {
                "success": False,
                "error": str(e)
            }

    # ========================================================
    # OCR
    # ========================================================

    try:

        result = process_document(
            filepath
        )

        print()
        print(
            "========== OCR RESULT FROM process_document =========="
        )
        print(result)
        print(
            "======================================================"
        )

    except Exception as e:

        return (
            "OCR processing failed: "
            + str(e)
        )

    blockchain_result = None
    # ========================================================
    # VALIDATION
    # ========================================================

    try:

        validation_result = validate_document(
            result
        )

    except Exception as e:

        return (
            "Document validation failed: "
            + str(e)
        )

    # ========================================================
    # TAMPERING DETECTION
    # ========================================================

    tampering_result = None

    if extension in image_extensions:

        try:

            tampering_result = analyze_tampering(
                filepath
            )

        except Exception as e:

            print(
                "Tampering detection failed:",
                e
            )

            tampering_result = {
                "status": "ERROR",
                "error": str(e)
            }

    # ========================================================
    # METADATA / EXIF FORENSICS
    # ========================================================

    metadata_result = None

    if extension in image_extensions:

        try:

            metadata_result = analyze_metadata(
                filepath
            )

        except Exception as e:

            print(
                "Metadata analysis failed:",
                e
            )

            metadata_result = {
                "status": "ERROR",
                "error": str(e),
                "risk_score": 50.0,
                "flags": ["Metadata analysis failed to run."]
            }

    # ========================================================
    # INITIAL OVERALL RISK SCORE
    # ========================================================

    # No live face verification, liveness check, or deepfake
    # heuristic has run yet (those need the live camera capture
    # from the verify-face step). Weights are dynamically
    # renormalized across whichever signals are available, so
    # this initial score is still fair using OCR + validation +
    # tampering + metadata only.
    overall_risk = calculate_overall_risk(
        result=result,
        validation=validation_result,
        tampering=tampering_result,
        face_result=face_result,
        face_verification=None,
        metadata=metadata_result
    )

    _print_overall_risk(
        overall_risk
    )

    # --------------------------------------------------------
    # Store only the small JSON-safe component values required
    # to recalculate the overall score after live verification.
    # --------------------------------------------------------

    session["risk_base"] = {
    "ocr": overall_risk["components"]["ocr"],
    "validation": overall_risk["components"]["validation"],
    "tampering": overall_risk["components"]["tampering"],
    "metadata": overall_risk["components"]["metadata"],
    "metadata_flags": (metadata_result or {}).get("flags", []),
    "filename": filename,

    "document_type": (
        result.get("document_type")
        or result.get("doc_type")
        or "UNKNOWN"
    )
}

    # Explicitly clear any old verification state from a
    # previous document.
    session.pop(
        "face_verification",
        None
    )

    # ========================================================
    # SEND RESULTS TO DASHBOARD
    # ========================================================

    return render_template(
    "dashboard.html",
    result=result,
    validation=validation_result,
    tampering=tampering_result,
    face_result=face_result,
    overall_risk=overall_risk,
    document_filename=filename,
    blockchain=blockchain_result
)


# ============================================================
# FACE VERIFICATION
# ============================================================

@app.route(
    "/verify-face",
    methods=["POST"]
)
def verify_face():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "error": "No image received."
        })

    image_data = data.get(
        "image"
    )

    if not image_data:

        return jsonify({
            "success": False,
            "error": "Camera image missing."
        })

    # --------------------------------------------------------
    # Remove base64 header
    # --------------------------------------------------------

    try:

        if "," in image_data:

            image_data = (
                image_data.split(
                    ",",
                    1
                )[1]
            )

        image_bytes = base64.b64decode(
            image_data
        )

    except Exception:

        return jsonify({
            "success": False,
            "error": "Invalid camera image."
        })

    # --------------------------------------------------------
    # Convert bytes -> OpenCV image
    # --------------------------------------------------------

    try:

        np_array = np.frombuffer(
            image_bytes,
            np.uint8
        )

        live_image = cv2.imdecode(
            np_array,
            cv2.IMREAD_COLOR
        )

    except Exception:

        return jsonify({
            "success": False,
            "error": "Could not process camera image."
        })

    if live_image is None:

        return jsonify({
            "success": False,
            "error": "Camera image could not be decoded."
        })

    # --------------------------------------------------------
    # Get document filename
    # --------------------------------------------------------

    document_filename = data.get(
        "document_filename"
    )

    if not document_filename:

        return jsonify({
            "success": False,
            "error": "Document reference missing."
        })

    document_filename = secure_filename(
        document_filename
    )

    document_path = os.path.join(
        "uploads",
        document_filename
    )

    if not os.path.exists(
        document_path
    ):

        return jsonify({
            "success": False,
            "error": "Uploaded document not found."
        })

    # --------------------------------------------------------
    # Extract document face
    # --------------------------------------------------------

    try:

        document_result = prepare_document_face(
            document_path
        )

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })

    if not document_result.get(
        "success"
    ):

        return jsonify({
            "success": False,
            "error": document_result.get(
                "error",
                "Document face not detected."
            )
        })

    document_embedding = (
        document_result["embedding"]
    )

    # --------------------------------------------------------
    # Verify live face
    # --------------------------------------------------------

    try:

        from face_service import verify_live_face

        verification = verify_live_face(
            document_embedding,
            live_image
        )

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })

    # --------------------------------------------------------
    # Terminal output
    # --------------------------------------------------------

    print()
    print("=" * 40)
    print("       FACE VERIFICATION RESULT")
    print("=" * 40)

    print(
        f"Document Face     : "
        f"{verification.get('document_face', 'Not Detected')}"
    )

    print(
        f"Live Face         : "
        f"{verification.get('live_face', 'Not Detected')}"
    )

    print(
        f"Similarity Score  : "
        f"{verification.get('similarity', 0):.2f}"
    )

    print(
        f"Threshold         : "
        f"{verification.get('threshold', 0.40):.2f}"
    )

    print(
        f"Result            : "
        f"{verification.get('result', 'NO MATCH')}"
    )

    print(
        f"Identity Status   : "
        f"{verification.get('identity_status', 'UNVERIFIED')}"
    )

    print("=" * 40)

    # ========================================================
    # RECALCULATE OVERALL RISK USING THE REAL LIVE FACE RESULT
    # ========================================================

    risk_base = session.get(
        "risk_base",
        {}
    )

    if not risk_base:

        return jsonify({
            **verification,
            "overall_risk": None,
            "warning": (
                "Face verification completed, but the base "
                "document risk data is unavailable. Please "
                "upload the document again."
            )
        })

    # --------------------------------------------------------
    # Recover the component scores calculated at upload.
    # --------------------------------------------------------

    ocr_risk = risk_base.get("ocr")
    validation_risk = risk_base.get("validation")
    tampering_risk = risk_base.get("tampering")
    metadata_risk_stored = risk_base.get("metadata")

    # Rebuild a metadata-shaped dict from what was stored in the
    # session (only the small JSON-safe pieces are kept there).
    metadata_result = (
        {
            "risk_score": metadata_risk_stored,
            "flags": risk_base.get("metadata_flags", []),
            "status": "STORED"
        }
        if metadata_risk_stored is not None
        else None
    )

    # --------------------------------------------------------
    # NEW: liveness + deepfake heuristic on the just-captured
    # live selfie.
    # --------------------------------------------------------

    try:
        liveness_result = check_liveness(live_image)
    except Exception as e:
        print("Liveness check failed:", e)
        liveness_result = {
            "status": "ERROR",
            "risk_score": 60.0,
            "flags": ["Liveness check failed to run."]
        }

    try:
        deepfake_result = analyze_deepfake_indicators(live_image)
    except Exception as e:
        print("Deepfake heuristic check failed:", e)
        deepfake_result = {
            "status": "ERROR",
            "risk_score": 40.0,
            "flags": ["AI-image heuristic check failed to run."]
        }

    # --------------------------------------------------------
    # Calculate final weighted score using every available
    # signal (OCR/validation/tampering/metadata from upload,
    # face/liveness/deepfake from this live verification).
    # --------------------------------------------------------

    from risk_scoring_service import (
        calculate_face_risk as _face_risk_fn,
        calculate_metadata_risk as _metadata_risk_fn,
        calculate_liveness_risk as _liveness_risk_fn,
        calculate_deepfake_risk as _deepfake_risk_fn,
        generate_comment as _generate_comment_fn,
        _BASE_WEIGHTS,
    )

    face_risk = _face_risk_fn(face_verification=verification)
    metadata_risk = _metadata_risk_fn(metadata_result)
    liveness_risk = _liveness_risk_fn(liveness_result)
    deepfake_risk = _deepfake_risk_fn(deepfake_result)

    component_values = {
        "ocr": ocr_risk,
        "validation": validation_risk,
        "tampering": tampering_risk,
        "face": face_risk,
        "metadata": metadata_risk,
        "liveness": liveness_risk,
        "deepfake": deepfake_risk,
    }

    active = {
        name: value
        for name, value in component_values.items()
        if value is not None
    }

    total_weight = sum(_BASE_WEIGHTS[name] for name in active) or 1.0

    overall_score = round(
        max(
            0.0,
            min(
                100.0,
                sum(
                    value * (_BASE_WEIGHTS[name] / total_weight)
                    for name, value in active.items()
                )
            )
        ),
        2
    )

    # Same critical-failure floor as calculate_overall_risk():
    # a hard face-verification failure (no live face detected,
    # or a clear no-match) must not be diluted into a low score
    # just because unrelated document checks happen to be clean.
    critical_face_failure = face_risk >= 80.0

    if critical_face_failure:

        overall_score = round(
            max(overall_score, 70.0),
            2
        )

    face_verified = (
        str(
            verification.get(
                "identity_status",
                ""
            )
        ).upper().strip()
        in (
            "VERIFIED",
            "MATCHED",
            "IDENTITY VERIFIED"
        )
    )

    comment = _generate_comment_fn(
        overall_score,
        ocr_risk or 0.0,
        validation_risk or 0.0,
        tampering_risk or 0.0,
        face_risk,
        face_verified,
        metadata_risk=metadata_risk,
        liveness_risk=liveness_risk,
        deepfake_risk=deepfake_risk
    )

    if critical_face_failure:

        comment = (
            "Face identity verification failed critically "
            "(no live face detected or no match) — treated as "
            "a hard identity-verification failure regardless "
            "of other checks. "
            + comment
        )

    overall_risk = {
        "risk_score": overall_score,

        "risk_level": _get_risk_level(
            overall_score
        ),

        "comment": comment,

        "components": {
            "ocr": round(ocr_risk, 2) if ocr_risk is not None else None,
            "validation": (
                round(validation_risk, 2)
                if validation_risk is not None else None
            ),
            "tampering": (
                round(tampering_risk, 2)
                if tampering_risk is not None else None
            ),
            "face": round(face_risk, 2),
            "metadata": (
                round(metadata_risk, 2)
                if metadata_risk is not None else None
            ),
            "liveness": round(liveness_risk, 2),
            "deepfake": round(deepfake_risk, 2),
        },

        "liveness_flags": liveness_result.get("flags", []),
        "deepfake_flags": deepfake_result.get("flags", []),

        "face_verified": face_verified
    }

    # Store the latest verification state so the server knows
    # the current risk is based on an actual live-face result.
    session["face_verification"] = {
        "identity_status": verification.get(
            "identity_status",
            ""
        ),
        "result": verification.get(
            "result",
            ""
        ),
        "similarity": float(
            verification.get(
                "similarity",
                0
            ) or 0.0
        ),
        "threshold": float(
            verification.get(
                "threshold",
                0.40
            ) or 0.40
        )
    }

    _print_overall_risk(
        overall_risk
    )

    # ============================================================
    # BLOCKCHAIN REGISTRATION
    # ============================================================

    blockchain_result = None

    final_status = overall_risk["risk_level"]

    try:

        # Get document information saved during upload
        document_type = (
            risk_base.get("document_type")
            or "UNKNOWN"
        )

        document_filename = risk_base.get(
            "filename"
        )

        if not document_filename:
            raise ValueError(
                "Uploaded document filename is missing."
            )

        document_path = os.path.join(
            "uploads",
            secure_filename(document_filename)
        )

        if not os.path.exists(document_path):
            raise FileNotFoundError(
                "Uploaded document not found."
            )

        # --------------------------------------------------------
        # REGISTER DOCUMENT ON BLOCKCHAIN
        # --------------------------------------------------------

        blockchain_result = register_document(
            document_path,
            document_type
        )

        # Add document type to returned result
        blockchain_result["document_type"] = document_type

        # --------------------------------------------------------
        # TERMINAL OUTPUT
        # --------------------------------------------------------

        print()
        print("=" * 50)
        print("       FINAL BLOCKCHAIN REGISTRATION")
        print("=" * 50)

        print(
            f"Document Type   : "
            f"{document_type}"
        )

        print(
            f"Verification ID : "
            f"{blockchain_result.get('verification_id', 'N/A')}"
        )

        print(
            f"Document Hash   : "
            f"{blockchain_result.get('document_hash', 'N/A')}"
        )

        print(
            f"Transaction     : "
            f"{blockchain_result.get('transaction_hash', 'N/A')}"
        )

        print(
            f"Block Number    : "
            f"{blockchain_result.get('block_number', 'N/A')}"
        )

        print(
            f"Status          : "
            f"{blockchain_result.get('status', 'N/A')}"
        )

        print("=" * 50)

    except Exception as e:

        print(
            "Blockchain registration failed:",
            repr(e)
        )

        blockchain_result = {
            "status": "BLOCKCHAIN ERROR",
            "error": str(e),
            "document_type": risk_base.get(
                "document_type",
                "UNKNOWN"
            )
        }

    # ============================================================
    # FINAL RESPONSE
    # ============================================================

    try:

        verification["success"] = True

        verification["overall_risk"] = overall_risk

        if blockchain_result is None:

            blockchain_result = {
                "status": "NOT REGISTERED",
                "message": (
                    "Blockchain registration was not completed."
                )
            }

        verification["blockchain"] = blockchain_result

        verification["final_status"] = final_status

        print()
        print("=" * 60)
        print("FINAL VERIFICATION RESPONSE")
        print("=" * 60)

        print(
            "Overall Risk :",
            overall_risk
        )

        print(
            "Final Status :",
            final_status
        )

        print(
            "Blockchain   :",
            blockchain_result
        )

        print("=" * 60)

        return jsonify(
            verification
        )

    except Exception as e:

        print(
            "FINAL RESPONSE ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": str(e),
            "message": (
                "Error while preparing verification response."
            )
        }), 500

# ============================================================
# FORGOT PASSWORD
# ============================================================

@app.route(
    "/forgot-password"
)
def forgot_password():

    return (
        "Forgot Password feature coming soon."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    create_table()

    # use_reloader=False: the debug auto-reloader watches every
    # imported file, including third-party packages like
    # insightface/onnxruntime. On Windows, a false-positive
    # "file changed" trigger from those packages causes the
    # reloader to restart the server while background threads
    # from those libraries are still running, which crashes the
    # interpreter at shutdown. debug=True still gives you
    # in-browser tracebacks; you just restart manually after
    # editing app.py.
    app.run(
        debug=True,
        use_reloader=False
    )