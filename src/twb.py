"""Minimal Tableau workbook (.twb / .twbx) writer.

Builds workbooks from CSV files so the dashboards are reproducible from code:
data sources, calculated fields, parameters, worksheets (bar, line, square, Gantt,
text marks) and a dashboard. Each CSV is converted to a Tableau Hyper extract with the
Tableau Hyper API, because Tableau Public only opens extract-based workbooks. The
packaged .twbx bundles the extracts, so it opens on any machine with Tableau Desktop
or Tableau Public.
"""
from __future__ import annotations

import io
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from datetime import datetime

VERSION = "18.1"


def _uid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


@dataclass
class Column:
    name: str
    datatype: str            # string | integer | real | date
    role: str                # dimension | measure
    type: str                # nominal | ordinal | quantitative
    caption: str | None = None
    fmt: str | None = None   # Tableau number format, e.g. p0.0% or c"$"#,##0
    semantic_role: str | None = None   # e.g. [Geographical].[Latitude] / [Geographical].[Longitude]


@dataclass
class Calc(Column):
    formula: str = ""


@dataclass
class Parameter:
    name: str                # e.g. "Parameter 1"
    caption: str
    value: float
    minimum: float
    maximum: float
    step: float
    datatype: str = "real"
    fmt: str | None = None


@dataclass
class DataSource:
    key: str                 # short id, e.g. "effects"
    caption: str
    csv: Path                # path of the CSV on disk (packaged under Data/ in the .twbx)
    columns: list[Column] = field(default_factory=list)
    calcs: list[Calc] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"federated.{self.key}"

    @classmethod
    def from_csv(cls, key: str, caption: str, csv: Path, dims: tuple[str, ...] = (),
                 captions: dict[str, str] | None = None, calcs: list[Calc] | None = None,
                 formats: dict[str, str] | None = None, roles: dict[str, str] | None = None) -> "DataSource":
        """Infer Tableau column types from the CSV; names in `dims` are forced to dimensions.

        ISO dates (YYYY-MM-DD) become date dimensions; `roles` sets geographic roles such as
        {"lat": "[Geographical].[Latitude]", "lon": "[Geographical].[Longitude]"}.
        """
        frame = pd.read_csv(csv, nrows=500)
        captions = captions or {}
        roles = roles or {}
        cols = []
        for col, dtype in frame.dtypes.items():
            is_date = (dtype == object and frame[col].notna().any()
                       and frame[col].dropna().astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all())
            if is_date:
                cols.append(Column(col, "date", "dimension", "ordinal", captions.get(col), (formats or {}).get(col)))
                continue
            if pd.api.types.is_integer_dtype(dtype):
                datatype = "integer"
            elif pd.api.types.is_float_dtype(dtype):
                datatype = "real"
            elif pd.api.types.is_bool_dtype(dtype):
                datatype = "boolean"
            else:
                datatype = "string"
            if col in dims or datatype in ("string", "boolean"):
                role, kind = "dimension", ("ordinal" if datatype == "integer" else "nominal")
            else:
                role, kind = "measure", "quantitative"
            cols.append(Column(col, datatype, role, kind, captions.get(col), (formats or {}).get(col),
                               roles.get(col)))
        return cls(key, caption, Path(csv), cols, calcs or [])

    def column(self, name: str) -> Column:
        for col in [*self.columns, *self.calcs]:
            if col.name == name:
                return col
        raise KeyError(f"{name} not in data source {self.key}")


@dataclass
class Field:
    """A field placed on a shelf or mark card."""
    name: str
    agg: str = "none"        # none | sum | avg | min | max | usr
    kind: str | None = None  # nk (discrete nominal), ok (discrete ordinal), qk (continuous)

    def instance(self, col: Column) -> tuple[str, str, str]:
        kind = self.kind or ("qk" if self.agg != "none" else ("ok" if col.type == "ordinal" else "nk"))
        derivation = {"none": "None", "sum": "Sum", "avg": "Avg", "min": "Min", "max": "Max",
                      "usr": "User"}[self.agg]
        itype = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[kind]
        return f"[{self.agg}:{self.name}:{kind}]", derivation, itype


@dataclass
class Worksheet:
    name: str
    source: DataSource
    rows: list[Field] = field(default_factory=list)
    cols: list[Field] = field(default_factory=list)
    mark: str = "Automatic"  # Bar | Line | Square | Circle | GanttBar | Text | Area
    color: Field | None = None
    size: Field | None = None
    text: Field | None = None
    tooltip: list[Field] = field(default_factory=list)
    detail: list[Field] = field(default_factory=list)
    title: str | None = None
    formats: dict[str, str] = field(default_factory=dict)   # field name -> Tableau number format
    show_labels: bool = False


@dataclass
class Zone:
    """Dashboard zone: a worksheet, a parameter control, or a text block (absolute pixels)."""
    x: int
    y: int
    w: int
    h: int
    sheet: str | None = None
    parameter: str | None = None
    text: str | None = None
    font_size: int = 12
    bold: bool = False
    legend_sheet: str | None = None   # color legend: worksheet name ...
    legend_field: str | None = None   # ... and the field reference, e.g. [federated.x].[none:arm:nk]


@dataclass
class Dashboard:
    name: str
    width: int
    height: int
    zones: list[Zone]


def _column_el(parent, col: Column):
    attrs = {"datatype": col.datatype, "name": f"[{col.name}]", "role": col.role, "type": col.type}
    if col.semantic_role:
        attrs["semantic-role"] = col.semantic_role
    if col.fmt:
        attrs = {"default-format": col.fmt, **attrs}
    if col.caption:
        attrs = {"caption": col.caption, **attrs}
    el = ET.SubElement(parent, "column", attrs)
    if isinstance(col, Calc):
        ET.SubElement(el, "calculation", {"class": "tableau", "formula": col.formula})
    return el


def _param_el(parent, p: Parameter):
    attrs = {"caption": p.caption, "datatype": p.datatype, "name": f"[{p.name}]", "param-domain-type": "range",
             "role": "measure", "type": "quantitative", "value": repr(p.value)}
    if p.fmt:
        attrs = {"caption": p.caption, "datatype": p.datatype, "default-format": p.fmt,
                 **{k: v for k, v in attrs.items() if k not in ("caption", "datatype")}}
    el = ET.SubElement(parent, "column", attrs)
    ET.SubElement(el, "calculation", {"class": "tableau", "formula": repr(p.value)})
    ET.SubElement(el, "range", {"granularity": repr(p.step), "max": repr(p.maximum), "min": repr(p.minimum)})
    return el


def _datasource_el(parent, ds: DataSource, packaged: bool):
    root = ET.SubElement(parent, "datasource", {"caption": ds.caption, "inline": "true", "name": ds.name,
                                                "version": VERSION})
    conn = ET.SubElement(root, "connection", {"class": "federated"})
    named = ET.SubElement(ET.SubElement(conn, "named-connections"), "named-connection",
                          {"caption": ds.csv.stem, "name": f"textscan.{ds.key}"})
    directory = "Data/Sources" if packaged else ds.csv.parent.resolve().as_posix()
    ET.SubElement(named, "connection", {"class": "textscan", "directory": directory, "filename": ds.csv.name,
                                        "password": "", "server": ""})
    rel = ET.SubElement(conn, "relation", {"connection": f"textscan.{ds.key}", "name": ds.csv.name,
                                           "table": f"[{ds.csv.stem}#csv]", "type": "table"})
    cols = ET.SubElement(rel, "columns", {"character-set": "UTF-8", "header": "yes", "locale": "en_US",
                                          "separator": ","})
    for i, col in enumerate(ds.columns):
        ET.SubElement(cols, "column", {"datatype": col.datatype, "name": col.name, "ordinal": str(i)})
    ET.SubElement(root, "aliases", {"enabled": "yes"})
    for col in [*ds.columns, *ds.calcs]:
        _column_el(root, col)
    # schema order: ... column*, extract?, layout? ...
    if packaged:
        ext = ET.SubElement(root, "extract", {"count": "-1", "enabled": "true", "units": "records"})
        econn = ET.SubElement(ext, "connection", {
            "access_mode": "readonly", "authentication": "auth-none", "author-locale": "en_US",
            "class": "hyper", "dbname": f"Data/Extracts/{ds.csv.stem}.hyper", "default-settings": "hyper",
            "schema": "Extract", "sslmode": "", "tablename": "Extract",
            "update-time": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"), "username": "tableau_internal_user"})
        ET.SubElement(econn, "relation", {"name": "Extract", "table": "[Extract].[Extract]", "type": "table"})
    ET.SubElement(root, "layout", {"dim-ordering": "alphabetic", "dim-percentage": "0.5",
                                   "measure-ordering": "alphabetic", "measure-percentage": "0.4",
                                   "show-structure": "true"})


def _shelf(ds: DataSource, fields: list[Field]) -> str:
    refs = [f"[{ds.name}].{f.instance(ds.column(f.name))[0]}" for f in fields]
    if not refs:
        return ""
    return refs[0] if len(refs) == 1 else "(" + " / ".join(refs) + ")"


def _worksheet_el(parent, ws: Worksheet, params: list[Parameter]):
    ds = ws.source
    sheet = ET.SubElement(parent, "worksheet", {"name": ws.name})
    if ws.title:
        layout = ET.SubElement(ET.SubElement(sheet, "layout-options"), "title")
        run = ET.SubElement(ET.SubElement(layout, "formatted-text"), "run", {"bold": "true", "fontsize": "12"})
        run.text = ws.title
    table = ET.SubElement(sheet, "table")
    view = ET.SubElement(table, "view")
    dss = ET.SubElement(view, "datasources")
    ET.SubElement(dss, "datasource", {"caption": ds.caption, "name": ds.name})
    used = [*ws.rows, *ws.cols, *(f for f in (ws.color, ws.size, ws.text) if f), *ws.tooltip, *ws.detail]
    uses_params = any("[Parameters]" in ds.column(f.name).formula for f in used
                      if isinstance(ds.column(f.name), Calc))
    if uses_params and params:
        ET.SubElement(dss, "datasource", {"name": "Parameters"})
    if any(ds.column(f.name).semantic_role for f in (*ws.rows, *ws.cols)):
        ET.SubElement(ET.SubElement(view, "mapsources"), "mapsource", {"name": "Tableau"})
    deps = ET.SubElement(view, "datasource-dependencies", {"datasource": ds.name})
    seen_cols, seen_inst = set(), set()
    for f in used:
        col = ds.column(f.name)
        if col.name not in seen_cols:
            _column_el(deps, col)
            seen_cols.add(col.name)
    for f in used:
        col = ds.column(f.name)
        name, derivation, itype = f.instance(col)
        if name not in seen_inst:
            ET.SubElement(deps, "column-instance", {"column": f"[{col.name}]", "derivation": derivation,
                                                    "name": name, "pivot": "key", "type": itype})
            seen_inst.add(name)
    if uses_params and params:
        pdeps = ET.SubElement(view, "datasource-dependencies", {"datasource": "Parameters"})
        for p in params:
            _param_el(pdeps, p)
    ET.SubElement(view, "aggregation", {"value": "true"})
    style = ET.SubElement(table, "style")
    if ws.formats:
        rule = ET.SubElement(style, "style-rule", {"element": "cell"})
        for fname, fmt in ws.formats.items():
            match = next(f for f in used if f.name == fname)
            ref = f"[{ds.name}].{match.instance(ds.column(fname))[0]}"
            ET.SubElement(rule, "format", {"attr": "text-format", "field": ref, "value": fmt})
    panes = ET.SubElement(table, "panes")
    pane = ET.SubElement(panes, "pane", {"selection-relaxation-option": "selection-relaxation-allow"})
    ET.SubElement(ET.SubElement(pane, "view"), "breakdown", {"value": "auto"})
    ET.SubElement(pane, "mark", {"class": ws.mark})
    enc = ET.SubElement(pane, "encodings")

    def ref(f: Field) -> str:
        return f"[{ds.name}].{f.instance(ds.column(f.name))[0]}"

    if ws.color:
        ET.SubElement(enc, "color", {"column": ref(ws.color)})
    if ws.size:
        ET.SubElement(enc, "size", {"column": ref(ws.size)})
    if ws.text:
        ET.SubElement(enc, "text", {"column": ref(ws.text)})
    for f in ws.tooltip:
        ET.SubElement(enc, "tooltip", {"column": ref(f)})
    for f in ws.detail:
        ET.SubElement(enc, "lod", {"column": ref(f)})
    if ws.show_labels:
        pstyle = ET.SubElement(pane, "style")
        rule = ET.SubElement(pstyle, "style-rule", {"element": "mark"})
        ET.SubElement(rule, "format", {"attr": "mark-labels-show", "value": "true"})
    ET.SubElement(table, "rows").text = _shelf(ds, ws.rows)
    ET.SubElement(table, "cols").text = _shelf(ds, ws.cols)


def _dashboard_el(parent, db: Dashboard, params: list[Parameter]):
    el = ET.SubElement(parent, "dashboard", {"name": db.name})
    ET.SubElement(el, "style")
    ET.SubElement(el, "size", {"maxheight": str(db.height), "maxwidth": str(db.width),
                               "minheight": str(db.height), "minwidth": str(db.width)})
    dss = ET.SubElement(el, "datasources")
    used = [p for p in params if any(z.parameter == p.name for z in db.zones)]
    if used:
        ET.SubElement(dss, "datasource", {"name": "Parameters"})
        deps = ET.SubElement(el, "datasource-dependencies", {"datasource": "Parameters"})
        for p in used:
            _param_el(deps, p)
    zones = ET.SubElement(el, "zones")
    ET.SubElement(zones, "zone", {"h": "100000", "id": "1", "type-v2": "layout-basic", "w": "100000",
                                  "x": "0", "y": "0"})
    sx, sy = 100000 / db.width, 100000 / db.height
    # Floating zones sit directly under <zones>, after the (empty) tiled root container.
    for i, z in enumerate(db.zones, start=2):
        attrs = {"h": str(round(z.h * sy)), "id": str(i), "w": str(round(z.w * sx)),
                 "x": str(round(z.x * sx)), "y": str(round(z.y * sy))}
        if z.sheet:
            zone = ET.SubElement(zones, "zone", {**attrs, "name": z.sheet})
        elif z.legend_sheet:
            zone = ET.SubElement(zones, "zone", {**attrs, "name": z.legend_sheet, "param": z.legend_field,
                                                 "type-v2": "color"})
        elif z.parameter:
            zone = ET.SubElement(zones, "zone", {**attrs, "mode": "slider", "param": f"[Parameters].[{z.parameter}]",
                                                 "type-v2": "paramctrl"})
        else:
            zone = ET.SubElement(zones, "zone", {**attrs, "type-v2": "text"})
            run = ET.SubElement(ET.SubElement(zone, "formatted-text"), "run",
                                {"fontsize": str(z.font_size), **({"bold": "true"} if z.bold else {})})
            run.text = z.text


def build_workbook(sources: list[DataSource], worksheets: list[Worksheet], dashboards: list[Dashboard],
                   params: list[Parameter] | None = None, packaged: bool = False) -> str:
    params = params or []
    wb = ET.Element("workbook", {"original-version": VERSION, "source-build": "2026.3.1",
                                 "source-platform": "mac", "version": VERSION,
                                 "xmlns:user": "http://www.tableausoftware.com/xml/user"})
    prefs = ET.SubElement(wb, "preferences")
    ET.SubElement(prefs, "preference", {"name": "ui.encoding.shelf.height", "value": "24"})
    ET.SubElement(prefs, "preference", {"name": "ui.shelf.height", "value": "26"})
    dss = ET.SubElement(wb, "datasources")
    if params:
        pds = ET.SubElement(dss, "datasource", {"hasconnection": "false", "inline": "true", "name": "Parameters",
                                                "version": VERSION})
        ET.SubElement(pds, "aliases", {"enabled": "yes"})
        for p in params:
            _param_el(pds, p)
    for ds in sources:
        _datasource_el(dss, ds, packaged)
    if any(c.semantic_role for ds in sources for c in ds.columns):
        # Latitude/longitude roles only draw on a background map when the workbook names a map source.
        ET.SubElement(ET.SubElement(wb, "mapsources"), "mapsource", {"name": "Tableau"})
    sheets = ET.SubElement(wb, "worksheets")
    for ws in worksheets:
        _worksheet_el(sheets, ws, params)
    dbs = ET.SubElement(wb, "dashboards")
    for db in dashboards:
        _dashboard_el(dbs, db, params)
    windows = ET.SubElement(wb, "windows", {"source-height": "30"})
    for ws in worksheets:
        win = ET.SubElement(windows, "window", {"class": "worksheet", "name": ws.name})
        cards = ET.SubElement(win, "cards")
        left = ET.SubElement(ET.SubElement(cards, "edge", {"name": "left"}), "strip", {"size": "160"})
        for card in ("pages", "filters", "marks"):
            ET.SubElement(left, "card", {"type": card})
        top = ET.SubElement(cards, "edge", {"name": "top"})
        for card, size in (("columns", "2147483647"), ("rows", "2147483647"), ("title", "31")):
            ET.SubElement(ET.SubElement(top, "strip", {"size": size}), "card", {"type": card})
    for db in dashboards:
        win = ET.SubElement(windows, "window", {"class": "dashboard", "maximized": "true", "name": db.name})
        vps = ET.SubElement(win, "viewpoints")
        for z in db.zones:
            if z.sheet:  # fit every view to its zone so dashboards have no scrollbars
                vp = ET.SubElement(vps, "viewpoint", {"name": z.sheet})
                ET.SubElement(vp, "zoom", {"type": "entire-view"})
        ET.SubElement(win, "active", {"id": "-1"})
        ET.SubElement(win, "device-preview", {"visible": "false"})
    ET.indent(wb, space="  ")
    return "<?xml version='1.0' encoding='utf-8' ?>\n" + ET.tostring(wb, encoding="unicode")


def write_hyper(ds: DataSource, path: Path) -> Path:
    """Write ds.csv to a Hyper extract with table Extract.Extract (the layout Tableau expects)."""
    from tableauhyperapi import (Connection, CreateMode, HyperProcess, Inserter, SqlType, TableDefinition,
                                 TableName, Telemetry)
    sql_types = {"string": SqlType.text(), "integer": SqlType.big_int(), "real": SqlType.double(),
                 "boolean": SqlType.bool(), "date": SqlType.date()}
    frame = pd.read_csv(ds.csv)
    table = TableDefinition(TableName("Extract", "Extract"),
                            [TableDefinition.Column(c.name, sql_types[c.datatype]) for c in ds.columns])
    rows = []
    for rec in frame[[c.name for c in ds.columns]].itertuples(index=False):
        row = []
        for value, col in zip(rec, ds.columns):
            if pd.isna(value):
                row.append(None)
            elif col.datatype == "integer":
                row.append(int(value))
            elif col.datatype == "real":
                row.append(float(value))
            elif col.datatype == "boolean":
                row.append(bool(value))
            elif col.datatype == "date":
                row.append(pd.Timestamp(value).date())
            else:
                row.append(str(value))
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Hyper writes hyperd.log to its log_dir (the working directory by default); keep it out of the project.
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU,
                      parameters={"log_dir": tempfile.gettempdir()}) as hyper:
        with Connection(hyper.endpoint, str(path), CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(table)
            with Inserter(conn, table) as inserter:
                inserter.add_rows(rows)
                inserter.execute()
    return path


def save(path_twbx: Path, sources: list[DataSource], worksheets: list[Worksheet], dashboards: list[Dashboard],
         params: list[Parameter] | None = None) -> Path:
    """Write a portable packaged workbook (.twbx) with Hyper extracts and the source CSVs."""
    path_twbx = path_twbx.with_suffix(".twbx")
    path_twbx.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(path_twbx.with_suffix(".twb").name,
                    build_workbook(sources, worksheets, dashboards, params, packaged=True))
        for ds in sources:
            hyper = write_hyper(ds, Path(tmp) / f"{ds.csv.stem}.hyper")
            zf.write(hyper, f"Data/Extracts/{hyper.name}")
            zf.write(ds.csv, f"Data/Sources/{ds.csv.name}")
    path_twbx.write_bytes(buffer.getvalue())
    return path_twbx
