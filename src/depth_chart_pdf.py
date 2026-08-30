"""Render the NFL Depth Charts matrix to a printable PDF.

Uses Pillow only (already a dependency) -- the table is drawn onto one or
more page images and saved as a multi-page PDF, so the blue "unavailable"
and red "taken" cell shading carry straight over to the export.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont

# Cell shading -- kept in step with src/views/depth_charts.py.
_UNAVAILABLE_FILL = (207, 226, 255)
_TAKEN_FILL = (248, 215, 218)
_MINE_FILL = (194, 232, 209)
_HEADER_FILL = (233, 236, 239)
_GRID = (170, 170, 170)
_TEXT = (33, 37, 41)
_MUTED = (108, 117, 125)

_FONT_SIZE = 17
_TITLE_SIZE = 22
_PAD_X = 10
_PAD_Y = 7
_ROWS_PER_PAGE = 24
_MAX_COL_WIDTH = 320
_MARGIN = 28


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _category(
    value: str,
    normalize,
    taken_keys,
    unavailable_keys,
    mine_keys=frozenset(),
) -> str:
    text = str(value or "")
    if text.endswith(")") and " (#" in text:
        text = text[: text.rfind(" (#")]
    key = normalize(text)
    if key and key in unavailable_keys:
        return "unavailable"
    if key and key in mine_keys:
        return "mine"
    if key and key in taken_keys:
        return "taken"
    return ""


def build_depth_chart_pdf(
    *,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    taken_keys: set,
    unavailable_keys: set,
    normalize,
    mine_keys: set = frozenset(),
    title: str = "NFL Depth Charts",
) -> bytes:
    """Return PDF bytes for the depth-chart matrix.

    ``columns`` is the ordered header list (including the leading "Team"
    column); ``rows`` is one mapping per team of column -> display string
    (already carrying the ``(#x)`` positional rank). ``taken_keys`` /
    ``unavailable_keys`` are sets of normalized player names and
    ``normalize`` is the name normalizer used to match cells against them.
    """

    measure_img = Image.new("RGB", (10, 10), "white")
    measure = ImageDraw.Draw(measure_img)
    body_font = _font(_FONT_SIZE)
    title_font = _font(_TITLE_SIZE)

    columns = list(columns)
    col_width = []
    for column in columns:
        widest = _text_width(measure, str(column), body_font)
        for row in rows:
            widest = max(
                widest, _text_width(measure, str(row.get(column, "")), body_font)
            )
        col_width.append(min(widest + 2 * _PAD_X, _MAX_COL_WIDTH))

    line_height = (
        measure.textbbox((0, 0), "Ag", font=body_font)[3]
        - measure.textbbox((0, 0), "Ag", font=body_font)[1]
    )
    row_height = line_height + 2 * _PAD_Y
    table_width = sum(col_width)
    title_band = _TITLE_SIZE + 24

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    page_row_groups = [
        rows[start : start + _ROWS_PER_PAGE]
        for start in range(0, max(len(rows), 1), _ROWS_PER_PAGE)
    ] or [[]]

    pages = []
    for page_rows in page_row_groups:
        page_height = (
            2 * _MARGIN
            + title_band
            + row_height * (len(page_rows) + 1)
        )
        page_width = 2 * _MARGIN + table_width
        page = Image.new("RGB", (page_width, page_height), "white")
        draw = ImageDraw.Draw(page)

        draw.text((_MARGIN, _MARGIN), title, fill=_TEXT, font=title_font)
        draw.text(
            (_MARGIN, _MARGIN + _TITLE_SIZE + 4),
            "Generated {0}".format(generated),
            fill=_MUTED,
            font=body_font,
        )

        top = _MARGIN + title_band
        left0 = _MARGIN

        # Header row.
        x = left0
        for index, column in enumerate(columns):
            draw.rectangle(
                [x, top, x + col_width[index], top + row_height],
                fill=_HEADER_FILL,
                outline=_GRID,
            )
            draw.text(
                (x + _PAD_X, top + _PAD_Y),
                str(column),
                fill=_TEXT,
                font=body_font,
            )
            x += col_width[index]

        # Body rows.
        for row_index, row in enumerate(page_rows, start=1):
            y = top + row_height * row_index
            x = left0
            for index, column in enumerate(columns):
                value = str(row.get(column, ""))
                fill = "white"
                if index > 0 and value:
                    category = _category(
                        value, normalize, taken_keys, unavailable_keys, mine_keys
                    )
                    if category == "unavailable":
                        fill = _UNAVAILABLE_FILL
                    elif category == "mine":
                        fill = _MINE_FILL
                    elif category == "taken":
                        fill = _TAKEN_FILL
                cell_box = [x, y, x + col_width[index], y + row_height]
                draw.rectangle(cell_box, fill=fill, outline=_GRID)
                draw.text(
                    (x + _PAD_X, y + _PAD_Y), value, fill=_TEXT, font=body_font
                )
                if fill == _TAKEN_FILL:
                    strike_y = y + row_height // 2
                    text_w = _text_width(draw, value, body_font)
                    draw.line(
                        [
                            x + _PAD_X,
                            strike_y,
                            x + _PAD_X + text_w,
                            strike_y,
                        ],
                        fill=_TEXT,
                        width=1,
                    )
                x += col_width[index]

        pages.append(page)

    buffer = BytesIO()
    pages[0].save(
        buffer,
        format="PDF",
        resolution=150.0,
        save_all=True,
        append_images=pages[1:],
    )
    return buffer.getvalue()
