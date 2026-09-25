# ============================================================
# OVERALL RISK SCORING SERVICE
#
# Combines:
#   OCR
#   Validation
#   Tampering Detection
#   Face Detection / Verification
#
# Output:
#   Fake Risk Percentage
#   Risk Level
#   Comment
# ============================================================


def calculate_ocr_risk(result):
    """
    Calculate OCR-related risk.

    Lower risk = OCR successfully extracted expected fields.
    Higher risk = important fields are missing.
    """

    if not result:
        return 100.0

    document_type = str(
        result.get("document_type", "")
    ).upper().strip()

    if document_type == "PAN":

        fields = [
            result.get("name"),
            result.get("dob"),
            result.get("gender"),
            result.get("pan_number")
        ]

    elif document_type == "AADHAAR":

        fields = [
            result.get("name"),
            result.get("dob"),
            result.get("gender"),
            result.get("aadhaar_number")
        ]

    elif document_type == "PASSPORT":

        fields = [
            result.get("passport_number"),
            result.get("surname"),
            result.get("given_name"),
            result.get("nationality"),
            result.get("dob"),
            result.get("sex"),
            result.get("place_of_birth"),
            result.get("place_of_issue"),
            result.get("date_of_issue"),
            result.get("date_of_expiry")
        ]

    elif document_type == "DRIVING LICENSE":

        fields = [
            result.get("name"),
            result.get("dob"),
            result.get("gender"),
            result.get("driving_license_number")
        ]

    else:
        return 80.0

    total = len(fields)

    if total == 0:
        return 100.0

    detected = sum(
        1 for field in fields
        if field is not None
        and str(field).strip() != ""
    )

    completeness = detected / total

    # Missing OCR fields create risk.
    risk = (1.0 - completeness) * 100.0

    return round(risk, 2)


def calculate_validation_risk(validation):
    """
    Convert validation results into a 0-100 risk score.

    NOTE: validate_document()'s per-field "checks" dict uses the
    literal statuses "MATCH" / "MISMATCH" / "NOT DETECTED" /
    "NOT AVAILABLE IN DATASET" (see validation_service.py) — it
    never produces the string "PASS". Comparing against "PASS"
    here meant every single document scored 100% validation
    risk regardless of whether its fields actually matched,
    which silently broke the validation signal. Fixed to
    recognize the actual status strings, and to treat "NOT
    DETECTED" / "NOT AVAILABLE IN DATASET" as neutral (as the
    comments in validation_service.py already say they should
    be) rather than counting them as failures.
    """

    if not validation:
        return 100.0

    checks = validation.get("checks", {})

    if not checks:
        return 100.0

    PASS_VALUES = {"PASS", "MATCH"}
    FAIL_VALUES = {"FAIL", "MISMATCH"}
    NEUTRAL_VALUES = {"NOT DETECTED", "NOT AVAILABLE IN DATASET"}

    determinate_total = 0
    failed = 0

    for status in checks.values():
        normalized = str(status).upper().strip()

        if normalized in NEUTRAL_VALUES:
            continue

        determinate_total += 1

        if normalized in FAIL_VALUES:
            failed += 1
        elif normalized not in PASS_VALUES:
            # Unrecognized status string — treat conservatively
            # as a failure rather than silently ignoring it.
            failed += 1

    if determinate_total == 0:
        # Nothing could actually be checked either way (e.g. no
        # dataset record, or every field was undetected) —
        # that's genuinely uncertain, not a clean pass.
        return 50.0

    risk = (failed / determinate_total) * 100.0

    return round(risk, 2)


def calculate_tampering_risk(tampering):
    """
    Tampering service already produces a risk_score.
    """

    if not tampering:
        return 50.0

    if tampering.get("status") == "ERROR":
        return 60.0

    try:
        risk = float(
            tampering.get("risk_score", 0)
        )
    except (TypeError, ValueError):
        risk = 50.0

    return max(0.0, min(100.0, risk))


def calculate_face_risk(
    face_result=None,
    face_verification=None
):
    """
    Face risk.

    Before live verification:
        Face detected     -> low risk
        Face not detected -> high risk

    After live verification:
        VERIFIED          -> 0 risk
        NO MATCH          -> 100 risk
    """

    # --------------------------------------------------------
    # LIVE VERIFICATION RESULT EXISTS
    # --------------------------------------------------------

    if face_verification:

        identity_status = str(
            face_verification.get(
                "identity_status",
                ""
            )
        ).upper().strip()

        result = str(
            face_verification.get(
                "result",
                ""
            )
        ).upper().strip()

        if identity_status == "VERIFIED":
            return 0.0

        if result in [
            "NO MATCH",
            "NOT MATCHED",
            "MISMATCH"
        ]:
            return 100.0

        if identity_status in [
            "SUSPICIOUS",
            "UNVERIFIED",
            "FAILED"
        ]:
            return 80.0

        # If similarity is available,
        # convert it into a risk value.
        try:
            similarity = float(
                face_verification.get(
                    "similarity",
                    0
                )
            )

            threshold = float(
                face_verification.get(
                    "threshold",
                    0.40
                )
            )

            if threshold > 0:

                ratio = similarity / threshold

                if ratio >= 1:
                    return 0.0

                risk = (1.0 - ratio) * 100.0

                return round(
                    max(0.0, min(100.0, risk)),
                    2
                )

        except (
            TypeError,
            ValueError,
            ZeroDivisionError
        ):
            pass

        return 60.0

    # --------------------------------------------------------
    # DOCUMENT FACE DETECTION ONLY
    #
    # IMPORTANT: this branch only runs when no live verification
    # has happened yet (face_verification is None/empty) — i.e.
    # right after document upload, before the user has scanned
    # their live face at all. `face_result.get("success")` only
    # means a face was detected in the uploaded DOCUMENT photo;
    # it does NOT mean identity has been verified. Previously
    # this returned 5.0 (very low risk) in that case, which made
    # the dashboard look like identity was basically confirmed
    # before any live scan had even happened. Treat "not yet
    # verified" as a neutral/pending risk instead — only an
    # actual completed live match should score low.
    # --------------------------------------------------------

    if not face_result:
        return 50.0

    if face_result.get("success"):
        # Document has a usable face and is ready for live
        # verification, but that verification hasn't happened
        # yet — this is a pending, not a low-risk, state.
        return 50.0

    # Document doesn't even have a detectable face, so live
    # verification can't be set up later either — worse than
    # merely "pending".
    return 80.0

    # --------------------------------------------------------
    # LIVE VERIFICATION RESULT EXISTS
    # --------------------------------------------------------

    if face_verification:

        identity_status = str(
            face_verification.get(
                "identity_status",
                ""
            )
        ).upper().strip()

        result = str(
            face_verification.get(
                "result",
                ""
            )
        ).upper().strip()

        if identity_status == "VERIFIED":
            return 0.0

        if result in [
            "NO MATCH",
            "NOT MATCHED",
            "MISMATCH"
        ]:
            return 100.0

        if identity_status in [
            "SUSPICIOUS",
            "UNVERIFIED",
            "FAILED"
        ]:
            return 80.0

        # If similarity is available,
        # convert it into a risk value.
        try:
            similarity = float(
                face_verification.get(
                    "similarity",
                    0
                )
            )

            threshold = float(
                face_verification.get(
                    "threshold",
                    0.40
                )
            )

            if threshold > 0:

                ratio = similarity / threshold

                if ratio >= 1:
                    return 0.0

                risk = (1.0 - ratio) * 100.0

                return round(
                    max(0.0, min(100.0, risk)),
                    2
                )

        except (
            TypeError,
            ValueError,
            ZeroDivisionError
        ):
            pass

        return 60.0

    # --------------------------------------------------------
    # DOCUMENT FACE DETECTION ONLY
    # --------------------------------------------------------

    if not face_result:
        return 50.0

    if face_result.get("success"):
        return 5.0

    return 80.0


def calculate_metadata_risk(metadata):
    """
    Metadata service already produces a 0-100 risk_score.
    """

    if not metadata:
        return None

    if metadata.get("status") == "SKIPPED":
        return None

    if metadata.get("status") == "ERROR":
        return 50.0

    try:
        risk = float(metadata.get("risk_score", 0))
    except (TypeError, ValueError):
        risk = 25.0

    return max(0.0, min(100.0, risk))


def calculate_liveness_risk(liveness):
    """
    Liveness service already produces a 0-100 risk_score.
    """

    if not liveness:
        return None

    if liveness.get("status") == "ERROR":
        return 60.0

    try:
        risk = float(liveness.get("risk_score", 0))
    except (TypeError, ValueError):
        risk = 40.0

    return max(0.0, min(100.0, risk))


def calculate_deepfake_risk(deepfake):
    """
    Deepfake heuristic service already produces a 0-100
    risk_score. This is an explainable heuristic indicator,
    not a trained classifier verdict.
    """

    if not deepfake:
        return None

    if deepfake.get("status") == "ERROR":
        return 40.0

    try:
        risk = float(deepfake.get("risk_score", 0))
    except (TypeError, ValueError):
        risk = 20.0

    return max(0.0, min(100.0, risk))


def get_risk_level(score):

    if score <= 20:
        return "LOW RISK"

    if score <= 50:
        return "MEDIUM RISK"

    if score <= 75:
        return "HIGH RISK"

    return "VERY HIGH RISK"


def generate_comment(
    score,
    ocr_risk,
    validation_risk,
    tampering_risk,
    face_risk,
    face_verified=False,
    metadata_risk=None,
    liveness_risk=None,
    deepfake_risk=None
):
    """
    Generate an explanation based on the strongest
    risk indicators.
    """

    reasons = []

    if ocr_risk >= 50:
        reasons.append(
            "OCR extraction detected missing or incomplete document information"
        )

    elif ocr_risk >= 20:
        reasons.append(
            "some document information could not be confidently extracted"
        )

    if validation_risk >= 50:
        reasons.append(
            "document validation checks failed"
        )

    elif validation_risk > 0:
        reasons.append(
            "some document validation checks require attention"
        )

    if tampering_risk >= 75:
        reasons.append(
            "strong indicators of possible document tampering were detected"
        )

    elif tampering_risk >= 40:
        reasons.append(
            "some suspicious document regions were detected"
        )

    if face_verified:
        pass

    elif face_risk >= 75:
        reasons.append(
            "the document face could not be successfully verified"
        )

    elif face_risk >= 30:
        reasons.append(
            "face verification is incomplete or requires attention"
        )

    if metadata_risk is not None:

        if metadata_risk >= 50:
            reasons.append(
                "the uploaded image's metadata shows signs of editing "
                "or missing capture information"
            )

        elif metadata_risk >= 20:
            reasons.append(
                "the uploaded image's metadata has minor inconsistencies"
            )

    if liveness_risk is not None:

        if liveness_risk >= 50:
            reasons.append(
                "the live camera capture did not clearly pass liveness "
                "checks (eyes open / sharpness / motion)"
            )

        elif liveness_risk >= 20:
            reasons.append(
                "some liveness signals in the live capture were inconclusive"
            )

    if deepfake_risk is not None:

        if deepfake_risk >= 50:
            reasons.append(
                "heuristic analysis of the live capture found indicators "
                "consistent with AI-generated or heavily synthetic imagery"
            )

        elif deepfake_risk >= 20:
            reasons.append(
                "heuristic analysis of the live capture found minor "
                "irregularities worth a manual look"
            )

    # --------------------------------------------------------
    # LOW RISK
    # --------------------------------------------------------

    if score <= 20:

        return (
            "Document appears genuine with no significant "
            "inconsistencies found."
        )

    # --------------------------------------------------------
    # MEDIUM RISK
    # --------------------------------------------------------

    if score <= 50:

        if reasons:

            return (
                "Document shows some suspicious indicators. "
                + "; ".join(reasons)
                + ". Further verification is recommended."
            )

        return (
            "Document contains some inconsistencies. "
            "Further verification is recommended."
        )

    # --------------------------------------------------------
    # HIGH RISK
    # --------------------------------------------------------

    if score <= 75:

        if reasons:

            return (
                "Document requires further verification because "
                + "; ".join(reasons)
                + "."
            )

        return (
            "Several screening indicators are suspicious. "
            "Further verification is strongly recommended."
        )

    # --------------------------------------------------------
    # VERY HIGH RISK
    # --------------------------------------------------------

    if reasons:

        return (
            "Multiple verification checks indicate a high "
            "possibility of document or identity irregularities: "
            + "; ".join(reasons)
            + "."
        )

    return (
        "Multiple screening checks produced strong risk indicators. "
        "The document should undergo manual verification."
    )



# ============================================================
# BASE WEIGHTS
#
# Only components that are actually available for a given
# call are used — their weights are renormalized to sum to 1
# so that, for example, the initial document-upload score
# (no live face/liveness/deepfake data yet) is still a fair
# 0-100 score using OCR + validation + tampering + metadata
# only, and the post-verification score folds in face,
# liveness and the deepfake heuristic as well.
# ============================================================

_BASE_WEIGHTS = {
    "ocr": 0.15,
    "validation": 0.20,
    "tampering": 0.20,
    "face": 0.20,
    "metadata": 0.10,
    "liveness": 0.10,
    "deepfake": 0.05,
}


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
    """
    Main overall risk calculation.

    Always-on signals: OCR, validation, tampering, face.
    Optional signals (folded in only when data is supplied):
    metadata (EXIF forensics), liveness (blink/eyes/motion
    checks on the live capture), deepfake (heuristic AI-image
    indicator on the live capture).

    Weights are renormalized across whichever signals are
    present for this call, so partial calls (e.g. right after
    upload, before live verification) still produce a fair
    0-100 score.
    """

    ocr_risk = calculate_ocr_risk(
        result
    )

    validation_risk = calculate_validation_risk(
        validation
    )

    tampering_risk = calculate_tampering_risk(
        tampering
    )

    face_risk = calculate_face_risk(
        face_result,
        face_verification
    )

    metadata_risk = calculate_metadata_risk(metadata)
    liveness_risk = calculate_liveness_risk(liveness)
    deepfake_risk = calculate_deepfake_risk(deepfake)

    # --------------------------------------------------------
    # DYNAMIC WEIGHTED SCORE
    # --------------------------------------------------------

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

    overall_score = sum(
        value * (_BASE_WEIGHTS[name] / total_weight)
        for name, value in active.items()
    )

    overall_score = round(
        max(
            0.0,
            min(100.0, overall_score)
        ),
        2
    )

    # --------------------------------------------------------
    # CRITICAL-FAILURE FLOOR
    #
    # Face identity verification is a trust boundary, not just
    # another signal to average in. If a live verification was
    # actually attempted and it failed hard (no live face
    # detected at all, or a clear NO MATCH), the weighted
    # average can still look deceptively low when the other
    # document-side checks (OCR/validation/tampering) happen to
    # be clean — e.g. a genuine document photographed by someone
    # who isn't its owner. In that case the overall score is
    # floored to a minimum so the dashboard can't understate a
    # failed identity check.
    # --------------------------------------------------------

    critical_face_failure = (
        face_verification is not None
        and face_risk >= 80.0
    )

    if critical_face_failure:

        overall_score = round(
            max(overall_score, 70.0),
            2
        )

    risk_level = get_risk_level(
        overall_score
    )

    face_verified = False

    if face_verification:

        face_verified = (
            str(
                face_verification.get(
                    "identity_status",
                    ""
                )
            ).upper()
            == "VERIFIED"
        )

    comment = generate_comment(
        overall_score,
        ocr_risk,
        validation_risk,
        tampering_risk,
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

    # --------------------------------------------------------
    # EXPLAINABLE AI: itemized, per-signal breakdown so the
    # dashboard can show WHY a score landed where it did, not
    # just the final number.
    # --------------------------------------------------------

    explanation = []

    def _add_explanation(name, label, risk_value, source):
        if risk_value is None:
            return
        explanation.append({
            "signal": label,
            "risk_score": round(risk_value, 2),
            "weight_used": round(_BASE_WEIGHTS[name] / total_weight, 3),
            "flags": source,
        })

    _add_explanation(
        "ocr", "Document OCR completeness", ocr_risk, []
    )
    _add_explanation(
        "validation", "Dataset validation", validation_risk, []
    )
    _add_explanation(
        "tampering", "Tampering / ELA analysis", tampering_risk, []
    )
    _add_explanation(
        "face", "Face match", face_risk, []
    )
    _add_explanation(
        "metadata", "Image metadata forensics", metadata_risk,
        (metadata or {}).get("flags", [])
    )
    _add_explanation(
        "liveness", "Liveness check", liveness_risk,
        (liveness or {}).get("flags", [])
    )
    _add_explanation(
        "deepfake", "AI-image heuristic", deepfake_risk,
        (deepfake or {}).get("flags", [])
    )

    return {
        "risk_score": overall_score,
        "risk_level": risk_level,
        "comment": comment,
        "explanation": explanation,

        "components": {
            "ocr": round(ocr_risk, 2),
            "validation": round(
                validation_risk,
                2
            ),
            "tampering": round(
                tampering_risk,
                2
            ),
            "face": round(
                face_risk,
                2
            ),
            "metadata": (
                round(metadata_risk, 2)
                if metadata_risk is not None else None
            ),
            "liveness": (
                round(liveness_risk, 2)
                if liveness_risk is not None else None
            ),
            "deepfake": (
                round(deepfake_risk, 2)
                if deepfake_risk is not None else None
            ),
        }
    }