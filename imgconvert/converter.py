from __future__ import annotations

import base64
from io import BytesIO
import mimetypes
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize
from PySide6.QtGui import QImage, QImageReader, QImageWriter, QColor, QPainter
from PySide6.QtSvg import QSvgRenderer


SUPPORTED_FORMATS = ("svg", "jpg", "png", "webp")
SUPPORTED_FORMATS = ("svg", "jpg", "png", "webp", "ico")


@dataclass(frozen=True)
class ConvertResult:
    ok: bool
    message: str
    output_path: Optional[Path] = None


def _norm_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext == "jpeg":
        return "jpg"
    return ext


def detect_input_format(path: Path) -> Optional[str]:
    ext = _norm_ext(path.suffix)
    if ext in SUPPORTED_FORMATS:
        return ext
    return None


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _svg_default_size(svg_bytes: bytes) -> Optional[Tuple[int, int]]:
    """Best-effort: read width/height or viewBox from SVG."""
    try:
        # ElementTree can choke on some SVGs; keep it defensive.
        root = ET.fromstring(svg_bytes)
    except Exception:
        return None

    def _parse_len(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        # strip units: px, pt, etc. Keep only the leading number.
        m = re.match(r"^\s*([0-9]*\.?[0-9]+)", value)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

    w = _parse_len(root.get("width"))
    h = _parse_len(root.get("height"))
    if w and h and w > 0 and h > 0:
        return int(round(w)), int(round(h))

    view_box = root.get("viewBox") or root.get("viewbox")
    if view_box:
        parts = re.split(r"[ ,]+", view_box.strip())
        if len(parts) == 4:
            try:
                vb_w = float(parts[2])
                vb_h = float(parts[3])
                if vb_w > 0 and vb_h > 0:
                    return int(round(vb_w)), int(round(vb_h))
            except Exception:
                pass

    return None


def _render_svg_to_image(svg_bytes: bytes) -> Tuple[Optional[QImage], str]:
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    if not renderer.isValid():
        return None, "SVG 文件无法解析/渲染"

    default_size = renderer.defaultSize()
    if default_size.isEmpty():
        parsed = _svg_default_size(svg_bytes)
        if parsed:
            default_size = QSize(parsed[0], parsed[1])

    if default_size.isEmpty():
        default_size = QSize(512, 512)

    image = QImage(default_size, QImage.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()

    if image.isNull():
        return None, "SVG 渲染失败"

    return image, ""


def _read_raster(path: Path) -> Tuple[Optional[QImage], str]:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        err = reader.errorString() or "未知错误"
        return None, f"读取图片失败：{err}"
    return image, ""


def _write_raster(image: QImage, out_path: Path, out_fmt: str) -> Tuple[bool, str]:
    out_fmt = _norm_ext(out_fmt)

    if out_fmt == "ico":
        return _write_ico(image, out_path)

    writer = QImageWriter(str(out_path), out_fmt.encode("ascii"))

    # JPG 不支持透明：统一铺白底
    if out_fmt in ("jpg", "jpeg") and image.hasAlphaChannel():
        composed = QImage(image.size(), QImage.Format_RGB32)
        composed.fill(QColor("white"))
        painter = QPainter(composed)
        try:
            painter.drawImage(0, 0, image)
        finally:
            painter.end()
        image = composed

    ok = writer.write(image)
    if not ok:
        err = writer.errorString() or "未知错误"
        return False, f"写出失败：{err}"
    return True, ""


def _write_ico(image: QImage, out_path: Path) -> Tuple[bool, str]:
    try:
        from PIL import Image
    except Exception:
        return False, "写出 ICO 需要 Pillow：请安装 pip install Pillow"

    png_bytes = _qimage_to_png_bytes(image)
    try:
        src = Image.open(BytesIO(png_bytes)).convert("RGBA")
    except Exception as exc:
        return False, f"ICO 编码失败：{exc}"

    src_w, src_h = src.size
    if src_w <= 0 or src_h <= 0:
        return False, "ICO 编码失败：输入图像尺寸无效"

    side = max(src_w, src_h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    paste_x = (side - src_w) // 2
    paste_y = (side - src_h) // 2
    canvas.paste(src, (paste_x, paste_y), src)

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    try:
        canvas.save(str(out_path), format="ICO", sizes=sizes)
    except Exception as exc:
        return False, f"写出 ICO 失败：{exc}"

    return True, ""


def _qimage_to_png_bytes(image: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def _raster_to_svg_embed(image: QImage) -> str:
    png_bytes = _qimage_to_png_bytes(image)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    w = max(1, image.width())
    h = max(1, image.height())

    # use href with xlink fallback for older viewers
    data_uri = f"data:image/png;base64,{b64}"
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>\n"
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" "
        f"width=\"{w}\" height=\"{h}\" viewBox=\"0 0 {w} {h}\">\n"
        f"  <image x=\"0\" y=\"0\" width=\"{w}\" height=\"{h}\" href=\"{data_uri}\" xlink:href=\"{data_uri}\"/>\n"
        "</svg>\n"
    )


def convert_file(input_path: Path, output_path: Path, output_format: str) -> ConvertResult:
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    output_format = _norm_ext(output_format)

    if not input_path.exists():
        return ConvertResult(False, "输入文件不存在")

    in_fmt = detect_input_format(input_path)
    if not in_fmt:
        return ConvertResult(False, f"不支持的输入格式：{input_path.suffix}")

    if output_format not in SUPPORTED_FORMATS:
        return ConvertResult(False, f"不支持的输出格式：{output_format}")

    if input_path == output_path:
        return ConvertResult(False, "输出路径不能与输入路径相同")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # SVG -> SVG: direct copy
    if in_fmt == "svg" and output_format == "svg":
        output_path.write_bytes(_read_bytes(input_path))
        return ConvertResult(True, "转换完成", output_path)

    # Raster -> Raster
    if in_fmt in ("jpg", "png", "webp", "ico") and output_format in ("jpg", "png", "webp", "ico"):
        image, err = _read_raster(input_path)
        if not image:
            return ConvertResult(False, err)
        ok, werr = _write_raster(image, output_path, output_format)
        if not ok:
            return ConvertResult(False, werr)
        return ConvertResult(True, "转换完成", output_path)

    # SVG -> Raster
    if in_fmt == "svg" and output_format in ("jpg", "png", "webp", "ico"):
        svg_bytes = _read_bytes(input_path)
        image, err = _render_svg_to_image(svg_bytes)
        if not image:
            return ConvertResult(False, err)
        ok, werr = _write_raster(image, output_path, output_format)
        if not ok:
            return ConvertResult(False, werr)
        return ConvertResult(True, "转换完成", output_path)

    # Raster -> SVG (embed)
    if in_fmt in ("jpg", "png", "webp", "ico") and output_format == "svg":
        image, err = _read_raster(input_path)
        if not image:
            return ConvertResult(False, err)
        svg_text = _raster_to_svg_embed(image)
        output_path.write_text(svg_text, encoding="utf-8")
        return ConvertResult(True, "转换完成（位图已嵌入 SVG，不做矢量化）", output_path)

    # Should not reach
    return ConvertResult(False, "未覆盖的转换路径")
