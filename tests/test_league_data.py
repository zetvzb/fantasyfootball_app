from openpyxl import Workbook

from src.league_data import LeagueDataLoader


def _write_workbook(path, sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_name, rows in sheets.items():
        sheet = workbook.create_sheet(sheet_name)
        for row in rows:
            sheet.append(row)
    workbook.save(path)


def test_load_historical_sales_reads_player_cost_owner_layout(tmp_path):
    path = tmp_path / "league.xlsx"
    _write_workbook(
        path,
        {
            "25 Draft": [
                ["Player Drafted", "Cost", "Owner"],
                ["Start of Draft", None, None],
                ["Justin Jefferson", 60, "zach"],
                ["Christian McCaffrey", 55, "jaylen"],
            ],
        },
    )
    loader = LeagueDataLoader(path)
    sales = loader.load_historical_sales()

    assert {sale.player_name: sale.price for sale in sales} == {
        "Justin Jefferson": 60,
        "Christian McCaffrey": 55,
    }


def test_load_historical_sales_reads_player_owner_cost_layout(tmp_path):
    # The same data, but with Owner and Cost columns swapped -- some
    # season sheets in real workbooks use this order instead.
    path = tmp_path / "league.xlsx"
    _write_workbook(
        path,
        {
            "24 Draft": [
                ["Player Drafted", "Owner", "Cost"],
                ["Start of Draft", None, None],
                ["Justin Jefferson", "zach", 60],
                ["Christian McCaffrey", "jaylen", 55],
            ],
        },
    )
    loader = LeagueDataLoader(path)
    sales = loader.load_historical_sales()

    assert {sale.player_name: sale.price for sale in sales} == {
        "Justin Jefferson": 60,
        "Christian McCaffrey": 55,
    }


def test_load_historical_sales_falls_back_to_default_columns_without_a_header(tmp_path):
    path = tmp_path / "league.xlsx"
    _write_workbook(
        path,
        {
            "23 Draft": [
                ["Draft Results", None, None],
                ["Start of Draft", None, None],
                ["Justin Jefferson", 60, "zach"],
            ],
        },
    )
    loader = LeagueDataLoader(path)
    sales = loader.load_historical_sales()

    assert {sale.player_name: sale.price for sale in sales} == {
        "Justin Jefferson": 60,
    }
