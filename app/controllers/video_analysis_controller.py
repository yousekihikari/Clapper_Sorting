"""Lifetime management for the threaded video QR analysis workflow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Slot
from PySide6.QtWidgets import QMessageBox

from app.models.analysis_result import AnalysisResult
from app.models.ocr_device import OcrDeviceMode
from app.models.organization_result import OrganizationResult
from app.views.video_analysis_tab import VideoAnalysisTab
from app.workers.organization_worker import OrganizationWorker
from app.workers.video_analysis_worker import VideoAnalysisWorker


class VideoAnalysisController(QObject):
    """Connect a video-analysis tab to one short-lived QThread per batch."""

    def __init__(self, view: VideoAnalysisTab, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._view = view
        self._thread: QThread | None = None
        self._worker: QObject | None = None
        self._view.analysis_requested.connect(self.start_analysis)
        self._view.finalize_requested.connect(self.start_organization)

    @Slot(object, object, object)
    def start_analysis(self, input_folder: Path, _output_folder: Path, device_mode: OcrDeviceMode) -> None:
        """Create, connect, and start the worker after view-side validation."""
        if self._thread is not None:
            return

        thread = QThread(self)
        worker = VideoAnalysisWorker(input_folder, device_mode)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._view.set_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._thread = thread
        self._worker = worker
        self._view.set_analysis_running(True)
        self._view.status_message.emit("動画の冒頭QRコードを解析しています。", 0)
        thread.start()

    @Slot(object)
    def _on_completed(self, results: list[AnalysisResult]) -> None:
        self._view.populate_results(results)
        self._view.set_progress(len(results), len(results), "解析が完了しました")
        if results:
            self._view.status_message.emit(f"{len(results)} 件の解析が完了しました。", 5000)
        else:
            QMessageBox.information(self._view, "対象動画なし", "入力フォルダ内に対応する動画ファイルがありません。")
            self._view.status_message.emit("対応する動画ファイルが見つかりませんでした。", 5000)

    @Slot(object, object)
    def start_organization(self, output_folder: Path, results: list[AnalysisResult]) -> None:
        """Move reviewed videos and create sidecars in a separate worker thread."""
        if self._thread is not None:
            return

        thread = QThread(self)
        worker = OrganizationWorker(output_folder, results)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._view.set_progress)
        worker.completed.connect(self._on_organization_completed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._thread = thread
        self._worker = worker
        self._view.set_analysis_running(True)
        self._view.status_message.emit("動画を移動し、XMPサイドカーを作成しています。", 0)
        thread.start()

    @Slot(object)
    def _on_organization_completed(self, outcomes: list[OrganizationResult]) -> None:
        self._view.apply_organization_results(outcomes)
        succeeded = sum(outcome.succeeded for outcome in outcomes)
        failed = len(outcomes) - succeeded
        self._view.set_progress(len(outcomes), len(outcomes), "振り分け・XMP作成が完了しました")
        if failed:
            QMessageBox.warning(
                self._view,
                "一部の処理が失敗",
                f"{succeeded} 件を移動してXMPを作成しました。{failed} 件は結果表のステータスを確認してください。",
            )
        else:
            QMessageBox.information(self._view, "完了", f"{succeeded} 件を移動してXMPを作成しました。")
        self._view.status_message.emit(f"振り分け完了: 成功 {succeeded} 件、失敗 {failed} 件", 8000)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        QMessageBox.critical(self._view, "解析エラー", message)
        self._view.status_message.emit(message, 8000)

    @Slot()
    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._view.set_analysis_running(False)
