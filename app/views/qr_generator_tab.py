"""View for single and batch QR-card preparation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QCheckBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)


class QrGeneratorTab(QWidget):
    """Second tab: UTF-8 QR preview, image output, bulk output, and printing."""

    preview_requested = Signal(str, bool)
    save_requested = Signal(str, str, bool)
    batch_save_requested = Signal(object, object, bool)
    print_requested = Signal(str, bool)
    status_message = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(self._build_single_group())
        layout.addWidget(self._build_batch_group())
        layout.addWidget(self._build_preview_group(), 1)
        layout.addLayout(self._build_actions())

    def _build_single_group(self) -> QGroupBox:
        group = QGroupBox("現在のQRコード")
        form = QFormLayout(group)
        self.scene_name_edit = QLineEdit()
        self.scene_name_edit.setPlaceholderText("例: シーン01_玄関")
        self.scene_name_edit.setClearButtonEnabled(True)
        self.cut_frame_check = QCheckBox("カット数を書き込む枠付きカードとしてプレビュー・印刷する")
        form.addRow("シーン名:", self.scene_name_edit)
        form.addRow("レイアウト:", self.cut_frame_check)
        return group

    def _build_batch_group(self) -> QGroupBox:
        group = QGroupBox("一括QRコード生成")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("シーン名を1行に1件ずつ入力してください（日本語可）。"))
        self.batch_scene_edit = QPlainTextEdit()
        self.batch_scene_edit.setPlaceholderText("シーン01_玄関\nシーン02_リビング\nシーン03_キッチン")
        self.batch_scene_edit.setMaximumHeight(100)
        layout.addWidget(self.batch_scene_edit)
        self.batch_progress = QProgressBar()
        self.batch_progress.setVisible(False)
        layout.addWidget(self.batch_progress)
        return group

    def _build_preview_group(self) -> QGroupBox:
        group = QGroupBox("QRコードプレビュー")
        layout = QVBoxLayout(group)
        self.preview_label = QLabel("シーン名を入力すると、ここにQRコードを表示します。")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(320, 320)
        self.preview_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)
        return group

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.save_button = QPushButton("QRコード画像を保存")
        self.batch_save_button = QPushButton("QRコードを一括保存")
        self.batch_card_save_button = QPushButton("カット数枠付きで一括保存")
        self.print_button = QPushButton("現在のプレビューを印刷")
        for button in (self.save_button, self.batch_save_button, self.batch_card_save_button, self.print_button):
            button.setMinimumHeight(38)
            layout.addWidget(button)
        return layout

    def _connect_signals(self) -> None:
        self.scene_name_edit.textChanged.connect(self._request_preview)
        self.cut_frame_check.toggled.connect(self._request_preview)
        self.save_button.clicked.connect(self._request_save)
        self.batch_save_button.clicked.connect(lambda: self._request_batch_save(False))
        self.batch_card_save_button.clicked.connect(lambda: self._request_batch_save(True))
        self.print_button.clicked.connect(self._request_print)

    def _scene_name(self) -> str:
        return self.scene_name_edit.text().strip()

    def _request_preview(self) -> None:
        scene_name = self._scene_name()
        if not scene_name:
            self.preview_label.setText("シーン名を入力すると、ここにQRコードを表示します。")
            self.preview_label.setPixmap(QPixmap())
            return
        self.preview_requested.emit(scene_name, self.cut_frame_check.isChecked())

    def _request_save(self) -> None:
        scene_name = self._require_scene_name()
        if scene_name is None:
            return
        destination, _ = QFileDialog.getSaveFileName(self, "QRコード画像を保存", f"{scene_name}.png", "PNG画像 (*.png)")
        if destination:
            self.save_requested.emit(scene_name, destination, self.cut_frame_check.isChecked())

    def _request_batch_save(self, include_cut_count_frame: bool) -> None:
        scene_names = [line.strip() for line in self.batch_scene_edit.toPlainText().splitlines() if line.strip()]
        if not scene_names:
            QMessageBox.warning(self, "シーン名未入力", "一括作成するシーン名を1行に1件ずつ入力してください。")
            return
        directory = QFileDialog.getExistingDirectory(self, "一括保存先フォルダを選択", str(Path.home()))
        if directory:
            self.batch_save_requested.emit(scene_names, Path(directory), include_cut_count_frame)

    def _request_print(self) -> None:
        scene_name = self._require_scene_name()
        if scene_name is not None:
            self.print_requested.emit(scene_name, self.cut_frame_check.isChecked())

    def _require_scene_name(self) -> str | None:
        scene_name = self._scene_name()
        if scene_name:
            return scene_name
        QMessageBox.warning(self, "シーン名未入力", "QRコードに記録するシーン名を入力してください。")
        return None

    def set_preview_image(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        self.preview_label.setPixmap(pixmap.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def set_batch_running(self, running: bool) -> None:
        self.batch_save_button.setEnabled(not running)
        self.batch_card_save_button.setEnabled(not running)
        self.batch_scene_edit.setEnabled(not running)
        self.batch_progress.setVisible(running)
        if running:
            self.batch_progress.setRange(0, 0)

    def set_batch_progress(self, current: int, total: int, message: str) -> None:
        self.batch_progress.setRange(0, total)
        self.batch_progress.setValue(current)
        self.batch_progress.setFormat(f"{message} ({current} / {total})")
