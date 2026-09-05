"""Premiere-compatible XMP sidecar generation without video re-encoding."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


X_NS = "adobe:ns:meta/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
DC_NS = "http://purl.org/dc/elements/1.1/"

ET.register_namespace("x", X_NS)
ET.register_namespace("rdf", RDF_NS)
ET.register_namespace("dc", DC_NS)


def write_xmp_sidecar(video_path: Path, scene_name: str, cut_count: str) -> Path:
    """Write a same-name ``.xmp`` sidecar beside a moved video file."""
    xmp_path = video_path.with_suffix(".xmp")
    root = ET.Element(f"{{{X_NS}}}xmpmeta")
    rdf = ET.SubElement(root, f"{{{RDF_NS}}}RDF")
    description = ET.SubElement(rdf, f"{{{RDF_NS}}}Description", {f"{{{RDF_NS}}}about": ""})

    _add_localized_value(description, "title", scene_name)
    metadata_description = f"シーン名: {scene_name}\nカット数: {cut_count or '未検出'}"
    _add_localized_value(description, "description", metadata_description)

    ET.indent(root, space="  ")
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    xmp_path.write_text(
        "<?xpacket begin='\ufeff' id='W5M0MpCehiHzreSzNTczkc9d'?>\n"
        f"{xml}\n"
        "<?xpacket end='w'?>\n",
        encoding="utf-8",
    )
    return xmp_path


def _add_localized_value(description: ET.Element, name: str, value: str) -> None:
    field = ET.SubElement(description, f"{{{DC_NS}}}{name}")
    alternative = ET.SubElement(field, f"{{{RDF_NS}}}Alt")
    item = ET.SubElement(alternative, f"{{{RDF_NS}}}li", {"{http://www.w3.org/XML/1998/namespace}lang": "x-default"})
    item.text = value
