"""QThread worker for final move-and-XMP batch operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.models.analysis_result import AnalysisResult
from app.models.organization_result import OrganizationResult
from app.services.file_organizer import move_video_and_create_xmp


class OrganizationWorker(QObject):
    progress = Signal(int, int, str)
    completed = Signal(object)
    finished = Signal()

    def __init__(self, output_folder: Path, results: list[AnalysisResult]) -> None:
        super().__init__()
        self._output_folder = output_folder
        self._results = results

    @Slot()
    def run(self) -> None:
        try:
            outcomes: list[OrganizationResult] = []
            total = len(self._results)
            for current, result in enumerate(self._results, start=1):
                self.progress.emit(current - 1, total, f"移動・XMP作成中: {result.video_path.name}")
                try:
                    outcomes.append(move_video_and_create_xmp(result, self._output_folder))
                except Exception as error:  # noqa: BLE001 - preserve the rest of the batch.
                    outcomes.append(OrganizationResult(result.video_path, None, None, str(error)))
                self.progress.emit(current, total, f"処理済み: {result.video_path.name}")
            self.completed.emit(outcomes)
        finally:
            self.finished.emit()
