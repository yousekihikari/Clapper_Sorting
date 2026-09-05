"""Data model for one video-analysis result row."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AnalysisResult:
    """Mutable review data shown in the human-in-the-loop results table.

    ``thumbnail_bytes`` contains a compact JPEG preview generated in the
    background worker.  Keeping the preview as bytes avoids creating GUI
    objects outside the main Qt thread.
    """

    video_path: Path
    scene_name: str = "未分類"
    cut_count: str = ""
    status: str = "待機中"
    thumbnail_bytes: bytes | None = None
