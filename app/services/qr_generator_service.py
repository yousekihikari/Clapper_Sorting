"""UTF-8 QR image and cut-count-card generation."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtGui import QImage

from app.services.file_organizer import sanitize_scene_name


def generate_qr_image(scene_name: str) -> Image.Image:
    """Create a QR image with UTF-8 payload and a readable scene label below it."""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=4)
    qr.add_data(scene_name.encode("utf-8"))
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    margin = 40
    label_height = 100
    canvas = Image.new("RGB", (qr_image.width + margin * 2, qr_image.height + margin * 2 + label_height), "white")
    canvas.paste(qr_image, (margin, margin))

    draw = ImageDraw.Draw(canvas)
    font = _scene_label_font(canvas.width - margin * 2, scene_name)
    text_box = draw.textbbox((0, 0), scene_name, font=font)
    text_width = text_box[2] - text_box[0]
    text_x = (canvas.width - text_width) // 2
    text_y = margin + qr_image.height + (label_height - (text_box[3] - text_box[1])) // 2 - text_box[1]
    draw.text((text_x, text_y), scene_name, fill="black", font=font)
    return canvas


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


def _scene_label_font(max_width: int, scene_name: str) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Select a Japanese-capable Windows font and shrink long labels to fit."""
    font_candidates = (
        Path(r"C:\Windows\Fonts\meiryo.ttc"),
        Path(r"C:\Windows\Fonts\YuGothM.ttc"),
        Path(r"C:\Windows\Fonts\msgothic.ttc"),
    )
    font_path = next((path for path in font_candidates if path.is_file()), None)
    if font_path is None:
        return ImageFont.load_default()

    for size in range(48, 15, -2):
        font = ImageFont.truetype(str(font_path), size)
        box = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), scene_name, font=font)
        if box[2] - box[0] <= max_width:
            return font
    return ImageFont.truetype(str(font_path), 16)
