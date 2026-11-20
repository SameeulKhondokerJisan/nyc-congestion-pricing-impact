"""Build excel/trip_unit_economics.xlsx: per-trip economics before and after the toll, and toll scenarios.

Every calculated cell is a formula over the Inputs and Data sheets. Colour code: blue = typed input or
pasted analysis result, black = formula, green = link to another sheet, yellow fill = assumption to review.
"""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from src import config

ARIAL = "Arial"
BLUE, BLACK, GREEN, WHITE = "0000FF", "000000", "008000", "FFFFFF"
HEADER = PatternFill("solid", fgColor="1F3864")
YELLOW = PatternFill("solid", fgColor="FFFF00")
LIGHT = PatternFill("solid", fgColor="EAF1FB")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
USD = '"$"#,##0;("$"#,##0);"-"'
USD2 = '"$"#,##0.00;("$"#,##0.00);"-"'
PCT = '0.0%;(0.0%);"-"'
NUM = '#,##0;(#,##0);"-"'
SRC = "Source: reports/results.json (src/run_pipeline.py), NYC TLC trip records Oct-Mar 2023-24 and 2024-25"
COMPONENTS = [("trips_per_day", "Trips per day", NUM), ("base_fare", "Base fare ($)", USD2),
              ("tolls", "Bridge and tunnel tolls ($)", USD2), ("ny_surcharge", "NYS congestion surcharge ($)", USD2),
              ("cbd_fee", "Congestion Relief Zone charge ($)", USD2), ("other_fees", "Taxes and other fees ($)", USD2),
              ("tips", "Tips ($)", USD2), ("driver_pay", "Driver pay ($)", USD2), ("miles", "Miles", "0.00"),
              ("minutes", "Minutes", "0.0")]


def _c(ws, ref, value, color=BLACK, fmt=None, bold=False, fill=None, note=None, italic=False, size=10):
    cell = ws[ref]
    cell.value = value
    cell.font = Font(name=ARIAL, color=color, bold=bold, italic=italic, size=size)
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = fill
    if note:
        cell.comment = Comment(note, "pipeline")
    return cell


def _head(ws, row, labels, col=1):
    for i, text in enumerate(labels):
        cell = ws.cell(row=row, column=col + i, value=text)
        cell.font = Font(name=ARIAL, color=WHITE, bold=True)
        cell.fill = HEADER
        cell.border = BOX
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _title(ws, text, sub=None):
    _c(ws, "A1", text, bold=True, size=14)
    if sub:
        _c(ws, "A2", sub, italic=True)


def build(results: dict) -> str:
    est = results["estimates"]["Uber/Lyft"]
    unit = {(r["season"], r["service"], bool(r["touches_zone"]), r["period"]): r for r in results["unit_economics"]}
    s1 = config.TOLL_SEASON
    wb = Workbook()

    ws = wb.active
    ws.title = "README"
    _title(ws, "Congestion pricing: trip unit economics", "Uber/Lyft trips in New York City, before and after 5 January 2025")
    for i, text in enumerate([
        "Purpose: show what riders paid, drivers earned and the platform kept per trip, and how a different "
        "zone charge would change trips and revenue.",
        "Inputs: zone charges and the trip response to price (yellow). Data: averages and estimates from the pipeline (blue).",
        "Unit economics: per-trip money for trips touching the Congestion Relief Zone and for other trips, Oct-Dec 2024 "
        "against Jan-Mar 2025.",
        "Toll scenarios: trips per day, zone-charge revenue, driver earnings and platform margin for other charge levels.",
        "Platform margin per trip = base fare - driver pay (tolls, taxes, surcharges and the zone charge pass through).",
        "The trip response is estimated from the difference-in-differences (trips change / rider price change); it also "
        "captures faster trips and other changes after 5 January, so treat scenarios far from $1.50 with care.",
        "Colour code: blue = input or pasted result; black = formula; green = link to another sheet; yellow fill = assumption.",
        SRC,
    ], start=4):
        _c(ws, f"A{i}", text)
    ws.column_dimensions["A"].width = 120

    inp = wb.create_sheet("Inputs")
    _title(inp, "Inputs", "Edit the yellow cells; everything else recalculates.")
    _head(inp, 4, ["Assumption", "Value", "Note"])
    elasticity = est.get("implied_price_elasticity")
    rows = [("Uber/Lyft zone charge per trip ($)", config.SERVICES["Uber/Lyft"], USD2, True, "MTA Per-Trip Charge Plan"),
            ("Taxi zone charge per trip ($)", config.SERVICES["Yellow taxi"], USD2, True, "MTA Per-Trip Charge Plan"),
            ("Trip response to rider price (elasticity)", elasticity if elasticity is not None else 0.0, "0.00", True,
             "Measured: trips effect / rider price effect from the difference-in-differences (see Data)"),
            ("Days per year", 365, "0", False, "")]
    for i, (label, value, fmt, editable, note) in enumerate(rows, start=5):
        _c(inp, f"A{i}", label)
        _c(inp, f"B{i}", value, BLUE, fmt, fill=YELLOW if editable else None)
        _c(inp, f"C{i}", note, italic=True)
    inp.column_dimensions["A"].width, inp.column_dimensions["B"].width, inp.column_dimensions["C"].width = 44, 14, 80

    dat = wb.create_sheet("Data")
    _title(dat, "Data (pasted from the pipeline)", SRC)
    _head(dat, 4, ["Per-trip average, Uber/Lyft", "Touches zone, Oct-Dec 2024", "Touches zone, Jan-Mar 2025",
                   "Other trips, Oct-Dec 2024", "Other trips, Jan-Mar 2025"])
    keys = [(s1, "Uber/Lyft", True, "Before"), (s1, "Uber/Lyft", True, "After"),
            (s1, "Uber/Lyft", False, "Before"), (s1, "Uber/Lyft", False, "After")]
    for i, (col, label, fmt) in enumerate(COMPONENTS, start=5):
        _c(dat, f"A{i}", label)
        for j, k in enumerate(keys):
            _c(dat, f"{'BCDE'[j]}{i}", float(unit[k][col]), BLUE, fmt)
    r0 = 5 + len(COMPONENTS) + 1
    _head(dat, r0, ["Estimate (Uber/Lyft, net of last year)", "Estimate", "95% CI low", "95% CI high", "Unit"])
    m, t, sp = est["money"], est["trips"]["pooled"], est["speed"]
    erows = [("Trips touching the zone", t["effect_pct"], t["effect_pct_low"], t["effect_pct_high"], PCT, "% change"),
             ("Rider price per trip", m["passenger_cost_per_trip"]["coef"], m["passenger_cost_per_trip"]["ci_low"],
              m["passenger_cost_per_trip"]["ci_high"], USD2, "$ per trip"),
             ("Base fare per trip", m["base_fare_per_trip"]["coef"], m["base_fare_per_trip"]["ci_low"],
              m["base_fare_per_trip"]["ci_high"], USD2, "$ per trip"),
             ("Driver pay per trip", m["driver_pay_per_trip"]["coef"], m["driver_pay_per_trip"]["ci_low"],
              m["driver_pay_per_trip"]["ci_high"], USD2, "$ per trip"),
             ("Driver pay per hour on trip", m["driver_pay_per_hour"]["coef"], m["driver_pay_per_hour"]["ci_low"],
              m["driver_pay_per_hour"]["ci_high"], USD2, "$ per hour"),
             ("Speed inside the zone vs upper Manhattan", sp["effect_pct"], sp["effect_pct_low"], sp["effect_pct_high"],
              PCT, "% change")]
    for i, (label, b, lo, hi, fmt, unit_txt) in enumerate(erows, start=r0 + 1):
        _c(dat, f"A{i}", label)
        for col, v in zip("BCD", (b, lo, hi)):
            _c(dat, f"{col}{i}", float(v), BLUE, fmt)
        _c(dat, f"E{i}", unit_txt, italic=True)
    price_pre_row = r0 + 2 + len(erows)
    _c(dat, f"A{price_pre_row}", "Rider price per trip before the toll, trips touching the zone ($)")
    _c(dat, f"B{price_pre_row}", float(m["passenger_cost_per_trip"]["treated_pre_mean_s1"]), BLUE, USD2)
    _c(dat, f"A{price_pre_row + 1}", "Implied elasticity = trips effect (log) / (rider price effect / price before)")
    _c(dat, f"B{price_pre_row + 1}", f"=IFERROR(LN(1+B{r0 + 1})/(B{r0 + 2}/B{price_pre_row}),0)", BLACK, "0.00")
    for col, w in zip("ABCDE", (62, 22, 22, 22, 22)):
        dat.column_dimensions[col].width = w

    ue = wb.create_sheet("Unit economics")
    _title(ue, "Unit economics per Uber/Lyft trip", "Rider total excludes tips; platform margin = base fare - driver pay")
    _head(ue, 4, ["Line", "Touches zone, before", "Touches zone, after", "Change", "Other trips, before",
                  "Other trips, after", "Change", "Change net of other trips"])
    R = {col: 5 + i for i, (col, _, _) in enumerate(COMPONENTS)}

    def link(col, src):
        return f"=Data!{src}{R[col]}"

    lines = [
        ("Trips per day", lambda s: link("trips_per_day", s), NUM),
        ("Base fare", lambda s: link("base_fare", s), USD2),
        ("Tolls, surcharge, taxes and fees", lambda s: f"=Data!{s}{R['tolls']}+Data!{s}{R['ny_surcharge']}"
                                                       f"+Data!{s}{R['other_fees']}", USD2),
        ("Congestion Relief Zone charge", lambda s: link("cbd_fee", s), USD2),
        ("Rider total (excluding tips)", lambda s: None, USD2),
        ("Driver pay", lambda s: link("driver_pay", s), USD2),
        ("Platform margin (base fare - driver pay)", lambda s: None, USD2),
        ("Platform take rate (margin / base fare)", lambda s: None, PCT),
        ("Driver pay per hour on trip", lambda s: f"=Data!{s}{R['driver_pay']}/(Data!{s}{R['minutes']}/60)", USD2),
        ("Minutes per trip", lambda s: link("minutes", s), "0.0"),
    ]
    cols = {"B": "B", "C": "C", "E": "D", "F": "E"}             # Unit economics column -> Data column
    for i, (label, fn, fmt) in enumerate(lines, start=5):
        _c(ue, f"A{i}", label, bold=label.startswith(("Rider total", "Platform margin")))
        for uc, dc in cols.items():
            if label.startswith("Rider total"):
                f = f"={uc}6+{uc}7+{uc}8"
            elif label.startswith("Platform margin"):
                f = f"={uc}6-{uc}10"
            elif label.startswith("Platform take"):
                f = f"=IFERROR({uc}11/{uc}6,0)"
            else:
                f = fn(dc)
            _c(ue, f"{uc}{i}", f, GREEN if f.startswith("=Data!") else BLACK, fmt)
        if label.startswith("Trips per day"):
            _c(ue, f"D{i}", f"=C{i}/B{i}-1", BLACK, PCT)
            _c(ue, f"G{i}", f"=F{i}/E{i}-1", BLACK, PCT)
            _c(ue, f"H{i}", f"=(1+D{i})/(1+G{i})-1", BLACK, PCT)
        else:
            _c(ue, f"D{i}", f"=C{i}-B{i}", BLACK, fmt)
            _c(ue, f"G{i}", f"=F{i}-E{i}", BLACK, fmt)
            _c(ue, f"H{i}", f"=D{i}-G{i}", BLACK, fmt)
    _c(ue, "A16", "Change columns compare Jan-Mar 2025 with Oct-Dec 2024 and include seasonal change; the Data sheet holds "
                  "the estimates net of last year.", italic=True)
    for col, w in zip("ABCDEFGH", (40, 16, 16, 12, 16, 16, 12, 18)):
        ue.column_dimensions[col].width = w

    sc = wb.create_sheet("Toll scenarios")
    _title(sc, "Toll scenarios for Uber/Lyft trips touching the zone",
           "Baseline = Oct-Dec 2024 trips and prices (before the toll); trip response from Inputs")
    _c(sc, "A3", "Rider price before the toll ($)")
    _c(sc, "D3", "='Unit economics'!B9", GREEN, USD2)
    _c(sc, "E3", "Platform margin per trip ($)")
    _c(sc, "H3", "='Unit economics'!B11", GREEN, USD2)
    _head(sc, 5, ["Zone charge per trip ($)", "Rider price ($)", "Price change vs no charge", "Trips per day",
                  "Change in trips", "Zone-charge revenue per day ($)", "Driver pay per day ($)",
                  "Platform margin per day ($)", "Zone-charge revenue per year ($)"])
    for i, charge in enumerate([0.0, 0.75, 1.50, 2.25, 3.00, 4.50], start=6):
        _c(sc, f"A{i}", charge, BLUE, USD2, fill=LIGHT if abs(charge - 1.5) < 1e-9 else None)
        _c(sc, f"B{i}", f"=$D$3+A{i}", BLACK, USD2)
        _c(sc, f"C{i}", f"=A{i}/$D$3", BLACK, PCT)
        _c(sc, f"D{i}", f"='Unit economics'!$B$5*MAX(0,1+Inputs!$B$7*C{i})", BLACK, NUM)
        _c(sc, f"E{i}", f"=D{i}/'Unit economics'!$B$5-1", BLACK, PCT)
        _c(sc, f"F{i}", f"=D{i}*A{i}", BLACK, USD)
        _c(sc, f"G{i}", f"=D{i}*'Unit economics'!$B$10", BLACK, USD)
        _c(sc, f"H{i}", f"=D{i}*$H$3", BLACK, USD)
        _c(sc, f"I{i}", f"=F{i}*Inputs!$B$8", BLACK, USD)
    _c(sc, "A13", "Shaded row = the current $1.50 charge. Trips scale linearly with the price change "
                  "(trips = baseline x (1 + elasticity x price change)).", italic=True)
    for col, w in zip("ABCDEFGHI", (18, 14, 16, 14, 14, 20, 18, 20, 22)):
        sc.column_dimensions[col].width = w

    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines = sheet.title == "Toll scenarios"
    config.EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(config.EXCEL_PATH)
    return str(config.EXCEL_PATH.relative_to(config.ROOT))
