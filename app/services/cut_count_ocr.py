"""Digit-only handwritten cut-count OCR with a bounded bottom-right ROI."""

from __future__ import annotations

from typing import Any, Protocol

import cv2
import numpy as np

from app.models.ocr_device import OcrDeviceMode

# Fallback ratios are used only if a QR position cannot be obtained.  Normal
# processing derives the ROI from the detected QR card geometry instead.
ROI_WIDTH_RATIO = 0.40
ROI_HEIGHT_RATIO = 0.30
OCR_ALLOWLIST = "0123456789"


class DigitReader(Protocol):
    """The small part of EasyOCR's Reader API used by this service."""

    def readtext(self, image: np.ndarray, **kwargs: Any) -> list[tuple[Any, str, float]]: ...


def create_digit_reader(device_mode: OcrDeviceMode = OcrDeviceMode.AUTO) -> tuple[DigitReader, OcrDeviceMode]:
    """Build one reusable EasyOCR reader for the requested device mode.

    ``AUTO`` prefers CUDA and falls back to CPU if unavailable or unusable.
    Explicit ``CUDA`` never silently changes to CPU; it reports an error so the
    operator can intentionally select CPU instead.  Model initialization
    belongs in the analysis worker, so its first-run cost never blocks the GUI.
    """
    import easyocr
    import torch

    if device_mode is OcrDeviceMode.CPU:
        return easyocr.Reader(["en"], gpu=False, verbose=False), OcrDeviceMode.CPU

    cuda_available = bool(torch.cuda.is_available())
    if device_mode is OcrDeviceMode.CUDA:
        if not cuda_available:
            raise RuntimeError("CUDAが利用できません。CPUまたは自動を選択してください。")
        return easyocr.Reader(["en"], gpu=True, verbose=False), OcrDeviceMode.CUDA

    if cuda_available:
        try:
            return easyocr.Reader(["en"], gpu=True, verbose=False), OcrDeviceMode.CUDA
        except Exception:
            pass
    return easyocr.Reader(["en"], gpu=False, verbose=False), OcrDeviceMode.CPU


def recognize_cut_count(
    frame: np.ndarray,
    reader: DigitReader,
    qr_points: np.ndarray | None = None,
) -> tuple[str, str]:
    """Return the most plausible decimal cut count and a user-facing status."""
    try:
        roi = extract_cut_count_roi(frame, qr_points)
        detections = []
        for prepared in preprocess_cut_count_roi(roi):
            detections.extend(
                reader.readtext(
                    prepared,
                    detail=1,
                    paragraph=False,
                    allowlist=OCR_ALLOWLIST,
                    text_threshold=0.25,
                    low_text=0.10,
                    link_threshold=0.10,
                )
            )
    except Exception:  # A failed OCR read must not discard an otherwise valid QR result.
        return "", "OCR解析エラー"

    candidates: list[tuple[str, float]] = []
    for detection in detections:
        if len(detection) < 3:
            continue
        text = str(detection[1])
        digits = "".join(character for character in text if character in OCR_ALLOWLIST)
        if not digits:
            continue
        try:
            confidence = float(detection[2])
        except (TypeError, ValueError):
            confidence = 0.0
        candidates.append((digits, confidence))

    if not candidates:
        return "", "OCR未検出"

    # EasyOCR usually returns one word.  When it returns alternatives, favor
    # high confidence and use a small length tie-breaker for multi-digit cuts.
    cut_count, _ = max(candidates, key=lambda item: (item[1], len(item[0])))
    return cut_count, "OCR検出済み"


def extract_cut_count_roi(frame: np.ndarray, qr_points: np.ndarray | None = None) -> np.ndarray:
    """Crop the cut-count frame below the detected QR, with a legacy fallback.

    In the supplied card layout, the handwritten number is directly beneath
    the QR code—not in the lower-right of the complete video frame.  The QR
    corners let this work regardless of where the card appears in the shot.
    """
    height, width = frame.shape[:2]
    if qr_points is not None:
        points = np.asarray(qr_points, dtype=np.float32).reshape(-1, 2)
        if len(points) >= 4:
            left, top = points.min(axis=0)
            right, bottom = points.max(axis=0)
            qr_width = max(1.0, right - left)
            qr_height = max(1.0, bottom - top)

            # The card's writing box starts just below the QR and is slightly
            # wider.  Crop inside the outer rectangle to remove its heavy
            # black border before passing the handwritten digit to EasyOCR.
            roi_left = max(0, round(left - qr_width * 0.20))
            roi_right = min(width, round(right + qr_width * 0.20))
            roi_top = max(0, round(bottom + qr_height * 0.20))
            roi_bottom = min(height, round(bottom + qr_height * 1.80))
            roi = frame[roi_top:roi_bottom, roi_left:roi_right]
            if roi.size:
                pad_x = max(2, round(roi.shape[1] * 0.07))
                # The top edge of the handwritten-number frame is the most
                # common false-positive source (often read as 7).  Trim more
                # aggressively above than below while preserving digit tails.
                pad_top = max(2, round(roi.shape[0] * 0.22))
                pad_bottom = max(2, round(roi.shape[0] * 0.08))
                inner = roi[pad_top : roi.shape[0] - pad_bottom, pad_x : roi.shape[1] - pad_x]
                if inner.size:
                    return inner

    left = max(0, round(width * (1.0 - ROI_WIDTH_RATIO)))
    top = max(0, round(height * (1.0 - ROI_HEIGHT_RATIO)))
    return frame[top:height, left:width]


def preprocess_cut_count_roi(roi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return contrast and binary variants suitable for handwritten digit OCR."""
    if roi.size == 0:
        raise ValueError("カット数ROIが空です")

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    enlarged = cv2.resize(normalized, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    blurred = cv2.GaussianBlur(enlarged, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        7,
    )
    padding = (32, 32, 32, 32)
    return (
        cv2.copyMakeBorder(enlarged, *padding, cv2.BORDER_CONSTANT, value=255),
        cv2.copyMakeBorder(binary, *padding, cv2.BORDER_CONSTANT, value=255),
    )
