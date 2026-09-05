"""Bounded, non-GUI video analysis helpers for the QR recognition workflow."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import cv2
import numpy as np

from app.models.analysis_result import AnalysisResult
from app.services.cut_count_ocr import DigitReader, recognize_cut_count


# Limiting both the count and the scope keeps H.265/4K videos from causing an
# unbounded scan when a clapper QR code is absent or illegible.
MAX_INITIAL_FRAMES = 90
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".m2ts"})
THUMBNAIL_MAX_WIDTH = 320
THUMBNAIL_MAX_HEIGHT = 180


def discover_video_files(input_folder: Path) -> list[Path]:
    """Return direct child videos in a deterministic order.

    Deliberately do not recurse: an output folder placed under the input folder
    must never become a new analysis target in the same batch.
    """
    return sorted(
        (path for path in input_folder.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda path: path.name.casefold(),
    )


def analyze_video_qr(
    video_path: Path,
    detector: cv2.QRCodeDetector | None = None,
    ocr_reader: DigitReader | None = None,
) -> AnalysisResult:
    """Decode a QR code from at most the first 90 frames of ``video_path``.

    OpenCV is the primary decoder.  Its decoded value is already a Python
    Unicode string, so Japanese UTF-8 QR payloads remain intact.  If it cannot
    find a code, pyzbar is attempted as an optional native-decoder fallback.
    """
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return AnalysisResult(video_path=video_path, status="動画を開けません")

    qr_detector = detector or cv2.QRCodeDetector()
    thumbnail_bytes: bytes | None = None
    scene_name: str | None = None
    cut_count = ""
    ocr_status = "OCR利用不可" if ocr_reader is None else "OCR未検出"

    try:
        for _ in range(MAX_INITIAL_FRAMES):
            ok, frame = capture.read()
            if not ok or frame is None:
                break

            if thumbnail_bytes is None:
                thumbnail_bytes = make_thumbnail_bytes(frame)

            scene_name, qr_points = detect_qr_from_frame(frame, qr_detector)
            if scene_name:
                if ocr_reader is not None:
                    cut_count, ocr_status = recognize_cut_count(frame, ocr_reader, qr_points)
                break
    except cv2.error as error:
        return AnalysisResult(
            video_path=video_path,
            status=f"映像解析エラー: {error.code}",
            thumbnail_bytes=thumbnail_bytes,
            cut_count=cut_count,
        )
    finally:
        capture.release()

    if scene_name:
        return AnalysisResult(
            video_path=video_path,
            scene_name=scene_name,
            cut_count=cut_count,
            status=f"QR検出済み・{ocr_status}",
            thumbnail_bytes=thumbnail_bytes,
        )
    return AnalysisResult(
        video_path=video_path,
        scene_name="未分類",
        cut_count=cut_count,
        status=f"QR未検出・{ocr_status}",
        thumbnail_bytes=thumbnail_bytes,
    )


def decode_qr_from_frame(frame: np.ndarray, detector: cv2.QRCodeDetector) -> str | None:
    """Return a non-empty UTF-8 QR payload from an OpenCV BGR frame."""
    return detect_qr_from_frame(frame, detector)[0]


def detect_qr_from_frame(frame: np.ndarray, detector: cv2.QRCodeDetector) -> tuple[str | None, np.ndarray | None]:
    """Return the QR payload and its corners for downstream card localization."""
    try:
        decoded_text, points, _ = detector.detectAndDecode(frame)
    except cv2.error:
        decoded_text, points = "", None

    normalized = _normalize_payload(decoded_text)
    if normalized:
        return normalized, points
    return _decode_with_pyzbar(frame)


def make_thumbnail_bytes(frame: np.ndarray) -> bytes | None:
    """Create a small JPEG without writing any temporary files."""
    height, width = frame.shape[:2]
    if not height or not width:
        return None
    scale = min(THUMBNAIL_MAX_WIDTH / width, THUMBNAIL_MAX_HEIGHT / height, 1.0)
    resized = cv2.resize(frame, (round(width * scale), round(height * scale))) if scale < 1.0 else frame
    success, encoded = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return encoded.tobytes() if success else None


def _decode_with_pyzbar(frame: np.ndarray) -> tuple[str | None, np.ndarray | None]:
    """Use pyzbar only when it and its Windows zbar DLL are available."""
    try:
        from pyzbar.pyzbar import ZBarSymbol, decode

        symbols: Iterable[object] = decode(frame, symbols=[ZBarSymbol.QRCODE])
    except (ImportError, OSError):
        return None, None

    for symbol in symbols:
        data = getattr(symbol, "data", b"")
        try:
            payload = data.decode("utf-8")
        except UnicodeDecodeError:
            # A non-UTF-8 payload cannot be a valid scene name for this app.
            continue
        normalized = _normalize_payload(payload)
        if normalized:
            rect = getattr(symbol, "rect", None)
            if rect is None:
                return normalized, None
            left, top = rect.left, rect.top
            right, bottom = left + rect.width, top + rect.height
            points = np.array([[[left, top], [right, top], [right, bottom], [left, bottom]]], dtype=np.float32)
            return normalized, points
    return None, None


def _normalize_payload(payload: str) -> str | None:
    """Accept Unicode scene labels while rejecting empty/whitespace payloads."""
    text = payload.strip()
    return text or None
