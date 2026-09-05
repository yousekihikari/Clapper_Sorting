"""Background worker for bounded QR analysis of a batch of video files."""

from __future__ import annotations

from pathlib import Path

import cv2
from PySide6.QtCore import QObject, Signal, Slot

from app.models.analysis_result import AnalysisResult
from app.models.ocr_device import OcrDeviceMode
from app.services.cut_count_ocr import DigitReader, create_digit_reader
from app.services.video_qr_analyzer import analyze_video_qr, discover_video_files


class VideoAnalysisWorker(QObject):
    """Run OpenCV QR analysis from a dedicated QThread, never the GUI thread."""

    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, input_folder: Path, ocr_device_mode: OcrDeviceMode) -> None:
        super().__init__()
        self._input_folder = input_folder
        self._ocr_device_mode = ocr_device_mode

    @Slot()
    def run(self) -> None:
        """Analyze all supported videos and always release the QThread caller."""
        try:
            video_files = discover_video_files(self._input_folder)
            if not video_files:
                self.completed.emit([])
                return

            detector = cv2.QRCodeDetector()
            ocr_reader, engine_name = self._initialize_ocr()
            results: list[AnalysisResult] = []
            total = len(video_files)
            for current, video_path in enumerate(video_files, start=1):
                self.progress.emit(current - 1, total, f"{engine_name}で解析中: {video_path.name}")
                try:
                    results.append(analyze_video_qr(video_path, detector, ocr_reader))
                except Exception as error:  # noqa: BLE001 - preserve the remaining batch.
                    results.append(AnalysisResult(video_path=video_path, status=f"解析エラー: {error}"))
                self.progress.emit(current, total, f"解析済み: {video_path.name}")
            self.completed.emit(results)
        except Exception as error:  # noqa: BLE001 - worker must not leave the UI locked.
            self.failed.emit(f"解析の初期化に失敗しました: {error}")
        finally:
            self.finished.emit()

    def _initialize_ocr(self) -> tuple[DigitReader | None, str]:
        """Keep QR analysis available even if EasyOCR cannot initialize."""
        try:
            reader, effective_mode = create_digit_reader(self._ocr_device_mode)
        except Exception as error:  # noqa: BLE001 - QR processing can still proceed.
            return None, f"OCR利用不可 ({error})"
        return reader, "GPU OCR" if effective_mode is OcrDeviceMode.CUDA else "CPU OCR"
