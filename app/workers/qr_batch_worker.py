"""Background worker for saving many QR images without freezing the UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.services.qr_generator_service import make_batch_destination, save_qr_image


class QrBatchWorker(QObject):
    progress = Signal(int, int, str)
    completed = Signal(object)
    finished = Signal()

    def __init__(self, scene_names: list[str], output_folder: Path, include_cut_count_frame: bool) -> None:
        super().__init__()
        self._scene_names = scene_names
        self._output_folder = output_folder
        self._include_cut_count_frame = include_cut_count_frame

    @Slot()
    def run(self) -> None:
        saved_paths: list[Path] = []
        total = len(self._scene_names)
        try:
            for current, scene_name in enumerate(self._scene_names, start=1):
                self.progress.emit(current - 1, total, f"生成中: {scene_name}")
                destination = make_batch_destination(self._output_folder, scene_name, self._include_cut_count_frame)
                saved_paths.append(save_qr_image(scene_name, destination, self._include_cut_count_frame))
                self.progress.emit(current, total, f"保存済み: {destination.name}")
            self.completed.emit(saved_paths)
        finally:
            self.finished.emit()
