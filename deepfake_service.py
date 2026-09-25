# ============================================================
# AI-GENERATED / DEEPFAKE IMAGE INDICATOR SERVICE
# ============================================================
#
# IMPORTANT — WHAT THIS IS AND ISN'T:
#
# This module does NOT run a trained deepfake-detection neural
# network (e.g. a CNN classifier fine-tuned on real-vs-GAN
# datasets). Building and validating one needs a labelled
# dataset and GPU training time this environment does not have.
#
# Instead it computes classic, explainable forensic signals that
# commonly differ between camera photos and AI-generated /
# heavily synthetic faces:
#
#   1. Frequency-domain regularity  — GAN/diffusion output often
#      leaves periodic artifacts (upsampling checkerboards) that
#      show up as unusually concentrated energy in the FFT
#      spectrum. Real camera sensor noise is closer to broadband.
#
#   2. Noise-residual consistency   — real photos have fairly
#      uniform sensor noise across the frame; many synthetic
#      faces show patches that are implausibly smooth next to
#      patches with leftover generator texture.
#
#   3. Local sharpness uniformity   — a real photo blurs
#      consistently with depth/focus; some generated faces mix
#      sharp and artificially smoothed regions.
#
# Treat the output as an INDICATOR to route for human review,
# not a verdict. Frame this to users/juries as "heuristic
# analysis", never as a trained deepfake classifier.
# ============================================================

import cv2
import numpy as np


def _to_gray(image_bgr):
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)


def _fft_high_freq_ratio(gray):
    """
    Returns the fraction of spectral energy sitting in the
    outer (high-frequency) ring of the FFT magnitude spectrum.
    Unusually low OR unusually spiky ratios can both indicate
    synthetic upsampling artifacts.
    """

    f = np.fft.fft2(gray.astype(np.float32))
    fshift = np.fft.fftshift(f)
    magnitude = np.abs(fshift)

    h, w = gray.shape
    cy, cx = h // 2, w // 2
    radius = min(cy, cx)

    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)

    low_mask = dist <= radius * 0.15
    high_mask = dist > radius * 0.5

    low_energy = magnitude[low_mask].sum()
    high_energy = magnitude[high_mask].sum()
    total = magnitude.sum() + 1e-6

    return float(high_energy / total), float(low_energy / total)


def _noise_residual_consistency(gray):
    """
    Splits the image into a grid, computes a high-pass "noise
    residual" per cell (original - blurred), and returns the
    coefficient of variation of residual energy across cells.
    Real camera noise tends to be fairly even; a large spread
    suggests inconsistent synthetic texture.
    """

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    residual = cv2.absdiff(gray, blurred).astype(np.float32)

    h, w = residual.shape
    grid = 4
    cell_h, cell_w = max(h // grid, 1), max(w // grid, 1)

    energies = []

    for i in range(grid):
        for j in range(grid):
            cell = residual[
                i * cell_h: (i + 1) * cell_h,
                j * cell_w: (j + 1) * cell_w,
            ]
            if cell.size == 0:
                continue
            energies.append(float(cell.mean()))

    if len(energies) < 2:
        return 0.0

    mean_e = np.mean(energies)
    std_e = np.std(energies)

    if mean_e < 1e-6:
        return 1.0

    return float(std_e / mean_e)


def _local_sharpness_uniformity(gray):
    """
    Coefficient of variation of Laplacian variance across a
    grid — measures how uniformly "in focus" the image is.
    """

    h, w = gray.shape
    grid = 4
    cell_h, cell_w = max(h // grid, 1), max(w // grid, 1)

    variances = []

    for i in range(grid):
        for j in range(grid):
            cell = gray[
                i * cell_h: (i + 1) * cell_h,
                j * cell_w: (j + 1) * cell_w,
            ]
            if cell.size == 0:
                continue
            variances.append(float(cv2.Laplacian(cell, cv2.CV_64F).var()))

    if len(variances) < 2:
        return 0.0

    mean_v = np.mean(variances)
    std_v = np.std(variances)

    if mean_v < 1e-6:
        return 0.0

    return float(std_v / mean_v)


def analyze_deepfake_indicators(image):
    """
    image: a BGR numpy array (e.g. the decoded live selfie) OR
    a filesystem path to an image.

    Returns a dict with a 0-100 heuristic risk score, individual
    signal values, and plain-language flags. This is explicitly
    a heuristic indicator, not a trained classifier verdict.
    """

    if isinstance(image, str):
        loaded = cv2.imread(image)
        if loaded is None:
            return {
                "status": "ERROR",
                "risk_score": 40.0,
                "flags": ["Image could not be loaded for AI-image analysis."],
            }
        image = loaded

    if image is None or image.size == 0:
        return {
            "status": "ERROR",
            "risk_score": 40.0,
            "flags": ["No image supplied for AI-image analysis."],
        }

    gray = _to_gray(image)

    high_freq_ratio, low_freq_ratio = _fft_high_freq_ratio(gray)
    noise_cv = _noise_residual_consistency(gray)
    sharpness_cv = _local_sharpness_uniformity(gray)

    flags = []
    risk = 0.0

    # Very low high-frequency energy relative to the rest of the
    # spectrum can indicate over-smoothed, generator-typical
    # texture (real sensor photos usually retain broadband noise).
    if high_freq_ratio < 0.015:
        risk += 30.0
        flags.append(
            "Very little high-frequency detail was found in the "
            "image, which can indicate over-smoothed, synthetic "
            "texture rather than natural sensor noise."
        )

    # A very uneven noise residual across the frame — some
    # patches nearly noise-free next to patches with texture —
    # is a common generator artifact.
    if noise_cv > 1.2:
        risk += 25.0
        flags.append(
            "Noise texture is inconsistent across different "
            "regions of the image."
        )

    # Similarly for local sharpness.
    if sharpness_cv > 1.5:
        risk += 20.0
        flags.append(
            "Sharpness is inconsistent across the image in a way "
            "not explained by normal depth-of-field blur."
        )

    risk = round(min(100.0, risk), 2)

    if risk <= 20:
        status = "LOW RISK"
    elif risk <= 50:
        status = "MEDIUM RISK"
    else:
        status = "HIGH RISK"

    if not flags:
        flags.append(
            "No strong heuristic indicators of AI-generated "
            "imagery were found."
        )

    return {
        "status": status,
        "risk_score": risk,
        "flags": flags,
        "signals": {
            "high_freq_ratio": round(high_freq_ratio, 5),
            "low_freq_ratio": round(low_freq_ratio, 5),
            "noise_consistency_cv": round(noise_cv, 3),
            "sharpness_consistency_cv": round(sharpness_cv, 3),
        },
        "method": "heuristic-frequency-and-noise-analysis",
        "disclaimer": (
            "Heuristic forensic indicator, not a trained deepfake "
            "classifier. Use as a signal for manual review."
        ),
    }
