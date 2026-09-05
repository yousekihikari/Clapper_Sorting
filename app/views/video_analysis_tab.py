"""View for selecting, reviewing, and sorting source video files.

Only presentation and user input live here.  The QR analysis controller and
QThread worker perform video decoding outside the GUI thread.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QComboBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.analysis_result import AnalysisResult
from app.models.ocr_device import OcrDeviceMode
from app.models.organization_result import OrganizationResult


class VideoAnalysisTab(QWidget):
    """First tab: batch video analysis and result confirmation."""

    analysis_requested = Signal(object, object, object)
    finalize_requested = Signal(object, object)
    status_message = Signal(str, int)

    _TABLE_COLUMNS = ("ファイル名", "冒頭サムネイル", "検出シーン名 (QR)", "検出カット数 (OCR)", "ステータス")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_finalized = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        root_layout.addWidget(self._build_path_group())
        root_layout.addWidget(self._build_execution_group())
        root_layout.addWidget(self._build_results_group(), 1)
        root_layout.addLayout(self._build_finalize_area())

    def _build_path_group(self) -> QGroupBox:
        group = QGroupBox("入出力設定")
        layout = QFormLayout(group)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setPlaceholderText("解析対象の動画が入ったフォルダを選択")
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setPlaceholderText("振り分け先フォルダを選択")

        layout.addRow("入力フォルダ:", self._path_picker(self.input_folder_edit, "入力フォルダを選択"))
        layout.addRow("出力フォルダ:", self._path_picker(self.output_folder_edit, "出力フォルダを選択"))
        return group

    def _path_picker(self, line_edit: QLineEdit, dialog_title: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)

        button = QPushButton("参照...")
        button.clicked.connect(lambda: self._choose_directory(line_edit, dialog_title))
        layout.addWidget(button)
        return container

    def _build_execution_group(self) -> QGroupBox:
        group = QGroupBox("解析実行")
        layout = QHBoxLayout(group)

        self.start_analysis_button = QPushButton("解析開始")
        self.start_analysis_button.setMinimumHeight(36)
        self.start_analysis_button.setToolTip("QRコードと手書きカット数の解析を開始します")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("待機中: %p%")

        self.progress_label = QLabel("入力・出力フォルダを指定してください。")
        self.progress_label.setMinimumWidth(280)

        self.ocr_device_combo = QComboBox()
        self.ocr_device_combo.addItem("自動（CUDA優先）", OcrDeviceMode.AUTO)
        self.ocr_device_combo.addItem("CUDA", OcrDeviceMode.CUDA)
        self.ocr_device_combo.addItem("CPU", OcrDeviceMode.CPU)
        self.ocr_device_combo.setToolTip("EasyOCRを実行するデバイスを選択します")

        layout.addWidget(self.start_analysis_button)
        layout.addWidget(QLabel("OCR実行:") )
        layout.addWidget(self.ocr_device_combo)
        layout.addWidget(self.progress_bar, 1)
        layout.addWidget(self.progress_label)
        return group

    def _build_results_group(self) -> QGroupBox:
        group = QGroupBox("結果確認・修正")
        layout = QVBoxLayout(group)

        description = QLabel(
            "QRのシーン名とOCRのカット数は、表内で直接修正できます。"
            "解析実装後、ここに検出結果が追加されます。"
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.results_table = QTableWidget(0, len(self._TABLE_COLUMNS))
        self.results_table.setHorizontalHeaderLabels(self._TABLE_COLUMNS)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setWordWrap(False)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setDefaultSectionSize(100)

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.results_table, 1)
        return group

    def _build_finalize_area(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.result_count_label = QLabel("解析結果: 0 件")
        self.finalize_button = QPushButton("振り分け＆メタデータ作成")
        self.finalize_button.setMinimumHeight(40)
        self.finalize_button.setToolTip("確認・修正済みの内容で動画を振り分け、XMPを作成します")

        layout.addWidget(self.result_count_label)
        layout.addStretch(1)
        layout.addWidget(self.finalize_button)
        return layout

    def _connect_signals(self) -> None:
        self.start_analysis_button.clicked.connect(self._request_analysis)
        self.finalize_button.clicked.connect(self._request_finalize)

    def _choose_directory(self, target: QLineEdit, title: str) -> None:
        initial_directory = target.text() or str(Path.home())
        selected_directory = QFileDialog.getExistingDirectory(self, title, initial_directory)
        if selected_directory:
            target.setText(selected_directory)

    def _request_analysis(self) -> None:
        input_folder = Path(self.input_folder_edit.text().strip())
        output_folder = Path(self.output_folder_edit.text().strip())
        if not self._validate_paths(input_folder, output_folder):
            return

        device_mode = self.ocr_device_combo.currentData()
        self.analysis_requested.emit(input_folder, output_folder, device_mode)
        self.progress_label.setText("解析を開始しています...")

    def _request_finalize(self) -> None:
        output_folder = Path(self.output_folder_edit.text().strip())
        if not output_folder:
            QMessageBox.warning(self, "出力フォルダ未指定", "出力フォルダを指定してください。")
            return
        if self.results_table.rowCount() == 0:
            QMessageBox.information(self, "解析結果なし", "先に動画の解析を実行してください。")
            return

        # ``collect_results`` reads edits made by the operator immediately before
        # a future file-operation service begins its work.
        self.finalize_requested.emit(output_folder, self.collect_results())
        self.status_message.emit("振り分け・XMP作成サービスは次のモジュールで接続します。", 5000)

    def _validate_paths(self, input_folder: Path, output_folder: Path) -> bool:
        if not self.input_folder_edit.text().strip() or not input_folder.is_dir():
            QMessageBox.warning(self, "入力フォルダ", "存在する入力フォルダを指定してください。")
            return False
        if not self.output_folder_edit.text().strip():
            QMessageBox.warning(self, "出力フォルダ", "出力フォルダを指定してください。")
            return False
        return True

    def set_analysis_running(self, running: bool) -> None:
        """Set the UI state used by the future asynchronous analysis worker."""
        self.start_analysis_button.setEnabled(not running)
        self.finalize_button.setEnabled(not running and not self._is_finalized)
        self.input_folder_edit.setEnabled(not running)
        self.output_folder_edit.setEnabled(not running)
        self.ocr_device_combo.setEnabled(not running)
        if running:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("解析中...")
            self.progress_label.setText("動画を解析しています。しばらくお待ちください。")
        else:
            self.progress_bar.setRange(0, 100)

    def set_progress(self, current: int, total: int, message: str = "") -> None:
        """Receive incremental progress from the future QThread worker."""
        percentage = int(current / total * 100) if total else 0
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{current} / {total} 件 (%p%)")
        self.progress_label.setText(message or f"{current} / {total} 件を解析済み")

    def populate_results(self, results: list[AnalysisResult]) -> None:
        """Replace table rows with a completed analysis batch.

        This public boundary is deliberately limited to view data; the view
        never accesses OpenCV, EasyOCR, or the filesystem other than directory
        selection.
        """
        self._is_finalized = False
        self.results_table.setRowCount(0)
        for result in results:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            file_item = QTableWidgetItem(result.video_path.name)
            file_item.setData(Qt.ItemDataRole.UserRole, str(result.video_path))
            file_item.setFlags(file_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results_table.setItem(row, 0, file_item)

            self.results_table.setCellWidget(row, 1, self._make_thumbnail(result.thumbnail_bytes))

            scene_item = QTableWidgetItem(result.scene_name)
            self.results_table.setItem(row, 2, scene_item)

            cut_item = QTableWidgetItem(result.cut_count)
            self.results_table.setItem(row, 3, cut_item)

            status_item = QTableWidgetItem(result.status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results_table.setItem(row, 4, status_item)

        self.result_count_label.setText(f"解析結果: {len(results)} 件")

    def _make_thumbnail(self, thumbnail_bytes: bytes | None) -> QLabel:
        label = QLabel("サムネイル待機中")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(150, 84)
        label.setFrameShape(QFrame.Shape.StyledPanel)
        if thumbnail_bytes:
            image = QPixmap()
            image.loadFromData(thumbnail_bytes, "JPG")
            if not image.isNull():
                label.setPixmap(
                    image.scaled(
                        label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        return label

    def collect_results(self) -> list[AnalysisResult]:
        """Return all rows, including operator changes to scene and cut count."""
        results: list[AnalysisResult] = []
        for row in range(self.results_table.rowCount()):
            file_item = self.results_table.item(row, 0)
            scene_item = self.results_table.item(row, 2)
            cut_item = self.results_table.item(row, 3)
            status_item = self.results_table.item(row, 4)
            if file_item is None:
                continue
            results.append(
                AnalysisResult(
                    video_path=Path(file_item.data(Qt.ItemDataRole.UserRole)),
                    scene_name=scene_item.text().strip() if scene_item else "未分類",
                    cut_count=cut_item.text().strip() if cut_item else "",
                    status=status_item.text() if status_item else "待機中",
                )
            )
        return results

    def apply_organization_results(self, outcomes: list[OrganizationResult]) -> None:
        """Reflect final move/XMP outcomes and keep rows safe from re-execution."""
        by_source = {str(outcome.source_path): outcome for outcome in outcomes}
        for row in range(self.results_table.rowCount()):
            file_item = self.results_table.item(row, 0)
            status_item = self.results_table.item(row, 4)
            if file_item is None or status_item is None:
                continue
            outcome = by_source.get(str(file_item.data(Qt.ItemDataRole.UserRole)))
            if outcome is None:
                continue
            if outcome.destination_path:
                file_item.setText(outcome.destination_path.name)
                file_item.setData(Qt.ItemDataRole.UserRole, str(outcome.destination_path))
                status_item.setText("移動・XMP作成済み" if outcome.succeeded else f"XMP作成エラー: {outcome.error}")
            else:
                status_item.setText(f"処理エラー: {outcome.error}")
        # A finalization attempt is never automatically rerun: repeating a
        # move after a partial failure could relocate an already moved video.
        self._is_finalized = True
        self.finalize_button.setEnabled(not self._is_finalized)
