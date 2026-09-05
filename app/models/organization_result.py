"""Outcome data for one move-and-XMP operation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OrganizationResult:
    source_path: Path
    destination_path: Path | None
    xmp_path: Path | None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.destination_path is not None and self.xmp_path is not None and self.error is None
