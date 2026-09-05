"""OCR execution-device choices exposed in the GUI."""

from __future__ import annotations

from enum import Enum


class OcrDeviceMode(str, Enum):
    """Requested EasyOCR device policy."""

    AUTO = "auto"
    CUDA = "cuda"
    CPU = "cpu"
