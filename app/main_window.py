"""Top-level window for the Clapper Sorting application."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

from app.controllers.video_analysis_controller import VideoAnalysisController
from app.controllers.qr_generation_controller import QrGenerationController
from app.views.qr_generator_tab import QrGeneratorTab
from app.views.video_analysis_tab import VideoAnalysisTab


class MainWindow(QMainWindow):
    """Application window that owns the two primary work tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Clapper Sorting - 動画振り分け・QR作成")
        self.setMinimumSize(QSize(1080, 720))
        self.resize(1280, 820)

        self.video_analysis_tab = VideoAnalysisTab(self)
        self.qr_generator_tab = QrGeneratorTab(self)
        self.video_analysis_controller = VideoAnalysisController(self.video_analysis_tab, self)
        self.qr_generation_controller = QrGenerationController(self.qr_generator_tab, self)

        tabs = QTabWidget(self)
        tabs.addTab(self.video_analysis_tab, "動画振り分け・解析")
        tabs.addTab(self.qr_generator_tab, "QRコード生成・印刷")
        self.setCentralWidget(tabs)

        status_bar = QStatusBar(self)
        status_bar.showMessage("準備完了")
        self.setStatusBar(status_bar)

        self._connect_status_messages()

    def _connect_status_messages(self) -> None:
        """Keep transient user-facing messages in the central status bar."""
        self.video_analysis_tab.status_message.connect(self.statusBar().showMessage)
        self.qr_generator_tab.status_message.connect(self.statusBar().showMessage)
