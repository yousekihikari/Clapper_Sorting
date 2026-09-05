"""Move reviewed videos into scene folders and create XMP sidecars."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.models.analysis_result import AnalysisResult
from app.models.organization_result import OrganizationResult
from app.services.xmp_sidecar import write_xmp_sidecar


_WINDOWS_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)), *(f"LPT{index}" for index in range(1, 10))}


def move_video_and_create_xmp(result: AnalysisResult, output_folder: Path) -> OrganizationResult:
    """Move—not copy—a reviewed source video, then write its XMP sidecar."""
    source_path = result.video_path
    if not source_path.is_file():
        return OrganizationResult(source_path, None, None, "元動画が見つかりません")

    destination_path: Path | None = None
    xmp_path: Path | None = None
    try:
        scene_folder = output_folder / sanitize_scene_name(result.scene_name)
        scene_folder.mkdir(parents=True, exist_ok=True)
        destination_path = _unique_destination(scene_folder, source_path)

        # shutil.move uses an in-volume rename where possible and implements
        # Windows cut/paste semantics across volumes.  No source copy is kept.
        shutil.move(str(source_path), str(destination_path))
        xmp_path = write_xmp_sidecar(destination_path, result.scene_name or "未分類", result.cut_count)
        return OrganizationResult(source_path, destination_path, xmp_path)
    except Exception as error:  # noqa: BLE001 - report partial completion safely.
        return OrganizationResult(source_path, destination_path, xmp_path, str(error))


def sanitize_scene_name(scene_name: str) -> str:
    """Keep Japanese names while preventing invalid Windows paths and traversal."""
    cleaned = _WINDOWS_INVALID_NAME.sub("_", scene_name.strip()).rstrip(". ")
    if not cleaned or cleaned in {".", ".."}:
        return "未分類"
    if cleaned.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        return f"{cleaned}_"
    return cleaned[:120]


def _unique_destination(scene_folder: Path, source_path: Path) -> Path:
    candidate = scene_folder / source_path.name
    index = 1
    while candidate.exists() or candidate.with_suffix(".xmp").exists():
        candidate = scene_folder / f"{source_path.stem} ({index}){source_path.suffix}"
        index += 1
    return candidate
