from io import BytesIO

from pypdf import PdfReader

from src.auction_pool import normalize_player_name
from src.depth_chart_pdf import build_depth_chart_pdf

_COLUMNS = ("Team", "QB", "WR1", "WR2", "TE", "RB1", "K")


def _rows(count: int):
    return [
        {
            "Team": "T{0}".format(index),
            "QB": "Quarterback {0} (#{0})".format(index + 1),
            "WR1": "Receiver {0} (#{0})".format(index + 1),
            "RB1": "Runner {0} (#{0})".format(index + 1),
        }
        for index in range(count)
    ]


def test_build_depth_chart_pdf_returns_valid_single_page_pdf():
    pdf_bytes = build_depth_chart_pdf(
        columns=_COLUMNS,
        rows=_rows(5),
        taken_keys={normalize_player_name("Runner 1")},
        unavailable_keys={normalize_player_name("Receiver 2")},
        normalize=normalize_player_name,
    )

    assert pdf_bytes[:4] == b"%PDF"
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 1


def test_build_depth_chart_pdf_paginates_large_tables():
    pdf_bytes = build_depth_chart_pdf(
        columns=_COLUMNS,
        rows=_rows(60),
        taken_keys=set(),
        unavailable_keys=set(),
        normalize=normalize_player_name,
    )

    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2


def test_build_depth_chart_pdf_handles_empty_table():
    pdf_bytes = build_depth_chart_pdf(
        columns=_COLUMNS,
        rows=[],
        taken_keys=set(),
        unavailable_keys=set(),
        normalize=normalize_player_name,
    )

    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 1
