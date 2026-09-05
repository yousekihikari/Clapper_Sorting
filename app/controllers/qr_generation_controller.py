"""Controller for QR preview, PNG output, batch output, and native printing."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Slot
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QMessageBox

from app.services.qr_generator_service import generate_cut_count_card, generate_qr_image, pil_image_to_qimage, save_qr_image
from app.views.qr_generator_tab import QrGeneratorTab
from app.workers.qr_batch_worker import QrBatchWorker


class QrGenerationController(QObject):
    def __init__(self, view: QrGeneratorTab, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._view = view
        self._thread: QThread | None = None
        self._worker: QrBatchWorker | None = None
        view.preview_requested.connect(self.update_preview)
        view.save_requested.connect(self.save_single)
        view.batch_save_requested.connect(self.save_batch)
        view.print_requested.connect(self.print_current)

    @Slot(str, bool)
    def update_preview(self, scene_name: str, include_cut_count_frame: bool) -> None:
        image = generate_cut_count_card(scene_name) if include_cut_count_frame else generate_qr_image(scene_name)
        self._view.set_preview_image(pil_image_to_qimage(image))

    @Slot(str, str, bool)
    def save_single(self, scene_name: str, destination: str, include_cut_count_frame: bool) -> None:
        try:
            saved_path = save_qr_image(scene_name, Path(destination), include_cut_count_frame)
        except OSError as error:
            QMessageBox.critical(self._view, "保存エラー", str(error))
            return
        self._view.status_message.emit(f"保存しました: {saved_path.name}", 5000)

    @Slot(object, object, bool)
    def save_batch(self, scene_names: list[str], output_folder: Path, include_cut_count_frame: bool) -> None:
        if self._thread is not None:
            return
        thread = QThread(self)
        worker = QrBatchWorker(scene_names, output_folder, include_cut_count_frame)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._view.set_batch_progress)
        worker.completed.connect(self._on_batch_completed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_batch_finished)
        self._thread, self._worker = thread, worker
        self._view.set_batch_running(True)
        thread.start()

    @Slot(object)
    def _on_batch_completed(self, saved_paths: list[Path]) -> None:
        self._view.status_message.emit(f"{len(saved_paths)} 件のQR画像を保存しました。", 8000)
        QMessageBox.information(self._view, "一括保存完了", f"{len(saved_paths)} 件の画像を保存しました。")

    @Slot()
    def _on_batch_finished(self) -> None:
        self._thread, self._worker = None, None
        self._view.set_batch_running(False)

    @Slot(str, bool)
    def print_current(self, scene_name: str, include_cut_count_frame: bool) -> None:
        image = generate_cut_count_card(scene_name) if include_cut_count_frame else generate_qr_image(scene_name)
        qimage = pil_image_to_qimage(image)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        if QPrintDialog(printer, self._view).exec() != QPrintDialog.DialogCode.Accepted:
            return
        painter = QPainter(printer)
        try:
            target = painter.viewport()
            scaled = qimage.scaled(target.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(target.x() + (target.width() - scaled.width()) // 2, target.y() + (target.height() - scaled.height()) // 2, scaled)
        finally:
            painter.end()
