"""View for preparing scene-name QR codes for filming."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class QrGeneratorTab(QWidget):
    """Second tab: QR preview, export, and print request interface."""

    preview_requested = Signal(str)
    save_requested = Signal(str, str)
    print_requested = Signal(str)
    status_message = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        root_layout.addWidget(self._build_input_group())
        root_layout.addWidget(self._build_preview_group(), 1)
        root_layout.addLayout(self._build_action_area())
        root_layout.addStretch(1)

    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox("QRコード内容")
        layout = QFormLayout(group)

        self.scene_name_edit = QLineEdit()
        self.scene_name_edit.setPlaceholderText("例: シーン01_玄関")
        self.scene_name_edit.setClearButtonEnabled(True)
        self.scene_name_edit.setToolTip("日本語を含むシーン名をUTF-8でQRコードに記録します")
        layout.addRow("シーン名:", self.scene_name_edit)
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

    def _build_action_area(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.save_button = QPushButton("QRコード画像を保存")
        self.print_button = QPushButton("印刷")
        self.save_button.setMinimumHeight(38)
        self.print_button.setMinimumHeight(38)

        layout.addStretch(1)
        layout.addWidget(self.save_button)
        layout.addWidget(self.print_button)
        return layout

    def _connect_signals(self) -> None:
        self.scene_name_edit.textChanged.connect(self._request_preview)
        self.scene_name_edit.returnPressed.connect(self._request_preview)
        self.save_button.clicked.connect(self._request_save)
        self.print_button.clicked.connect(self._request_print)

    def _scene_name(self) -> str:
        return self.scene_name_edit.text().strip()

    def _request_preview(self) -> None:
        scene_name = self._scene_name()
        if not scene_name:
            self.preview_label.setText("シーン名を入力すると、ここにQRコードを表示します。")
            return
        # The QR service will render an image and call set_preview_pixmap.
        self.preview_requested.emit(scene_name)
        self.preview_label.setText(f"「{scene_name}」のQRコードを生成します")

    def _request_save(self) -> None:
        scene_name = self._scene_name()
        if not self._require_scene_name(scene_name):
            return

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "QRコード画像を保存",
            f"{scene_name}.png",
            "PNG画像 (*.png)",
        )
        if destination:
            self.save_requested.emit(scene_name, destination)
            self.status_message.emit("QRコード画像保存サービスは次のモジュールで接続します。", 5000)

    def _request_print(self) -> None:
        scene_name = self._scene_name()
        if not self._require_scene_name(scene_name):
            return
        self.print_requested.emit(scene_name)
        self.status_message.emit("印刷サービスは次のモジュールで接続します。", 5000)

    def _require_scene_name(self, scene_name: str) -> bool:
        if scene_name:
            return True
        QMessageBox.warning(self, "シーン名未入力", "QRコードに記録するシーン名を入力してください。")
        return False

    def set_preview_pixmap(self, pixmap: object) -> None:
        """Set a QR image produced by the upcoming QR service.

        The loose argument type avoids coupling this view to Pillow/qrcode. The
        service will provide a QPixmap in the next module.
        """
        from PySide6.QtGui import QPixmap

        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.preview_label.setPixmap(
                pixmap.scaled(
                    self.preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
