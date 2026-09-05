"""UTF-8 QR image and cut-count-card generation."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw
from PySide6.QtGui import QImage

from app.services.file_organizer import sanitize_scene_name


def generate_qr_image(scene_name: str) -> Image.Image:
    """Create a high-contrast QR image with an explicit UTF-8 payload."""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=4)
    qr.add_data(scene_name.encode("utf-8"))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def generate_cut_count_card(scene_name: str) -> Image.Image:
    """Create a printable QR card with a large blank cut-count writing frame."""
    qr_image = generate_qr_image(scene_name)
    margin, frame_height = 80, 360
    width = qr_image.width + margin * 2
    height = qr_image.height + margin * 3 + frame_height
    card = Image.new("RGB", (width, height), "white")
    card.paste(qr_image, (margin, margin))
    top = qr_image.height + margin * 2
    ImageDraw.Draw(card).rectangle((margin, top, width - margin, height - margin), outline="black", width=10)
    return card


def save_qr_image(scene_name: str, destination: Path, include_cut_count_frame: bool = False) -> Path:
    image = generate_cut_count_card(scene_name) if include_cut_count_frame else generate_qr_image(scene_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG")
    return destination


def make_batch_destination(output_folder: Path, scene_name: str, include_cut_count_frame: bool) -> Path:
    suffix = "_カット数枠付き" if include_cut_count_frame else ""
    stem = f"{sanitize_scene_name(scene_name)}{suffix}"
    destination = output_folder / f"{stem}.png"
    index = 1
    while destination.exists():
        destination = output_folder / f"{stem} ({index}).png"
        index += 1
    return destination


def pil_image_to_qimage(image: Image.Image) -> QImage:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return QImage.fromData(buffer.getvalue(), "PNG")
