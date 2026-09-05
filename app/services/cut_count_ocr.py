"""Digit-only handwritten cut-count OCR with a bounded bottom-right ROI."""

from __future__ import annotations

from typing import Any, Protocol

import cv2
import numpy as np

from app.models.ocr_device import OcrDeviceMode

# These ratios keep most of a handwritten cut number while excluding the
# scene-name QR normally positioned elsewhere on the clapper/card.
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


def recognize_cut_count(frame: np.ndarray, reader: DigitReader) -> tuple[str, str]:
    """Return the most plausible decimal cut count and a user-facing status."""
    try:
        roi = extract_cut_count_roi(frame)
        prepared = preprocess_cut_count_roi(roi)
        detections = reader.readtext(
            prepared,
            detail=1,
            paragraph=False,
            allowlist=OCR_ALLOWLIST,
            text_threshold=0.35,
            low_text=0.20,
            link_threshold=0.20,
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


def extract_cut_count_roi(frame: np.ndarray) -> np.ndarray:
    """Crop the lower-right region where the handwritten cut count is expected."""
    height, width = frame.shape[:2]
    left = max(0, round(width * (1.0 - ROI_WIDTH_RATIO)))
    top = max(0, round(height * (1.0 - ROI_HEIGHT_RATIO)))
    return frame[top:height, left:width]


def preprocess_cut_count_roi(roi: np.ndarray) -> np.ndarray:
    """Enlarge, denoise, binarize, and pad an ROI for handwritten digit OCR."""
    if roi.size == 0:
        raise ValueError("カット数ROIが空です")

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    blurred = cv2.GaussianBlur(enlarged, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        7,
    )
    return cv2.copyMakeBorder(binary, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
