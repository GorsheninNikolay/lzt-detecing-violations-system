"""Source-bound work catalog and manually versioned zone plans."""

from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


router = APIRouter()
XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
WORKBOOK = next((Path(__file__).resolve().parents[3] / "artifacts/dataset").glob("Свод*.xlsx"), None)


class SiteError(ValueError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.status = status


def _cells(path: Path) -> tuple[str, list[dict]]:
    source_hash = sha256(path.read_bytes()).hexdigest()
    with ZipFile(path) as archive:
        strings_xml = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(part.text or "" for part in item.findall(".//x:t", XML_NS))
                   for item in strings_xml.findall("x:si", XML_NS)]
        styles_xml = ET.fromstring(archive.read("xl/styles.xml"))
        formats = {int(item.get("numFmtId")): item.get("formatCode")
                   for item in styles_xml.findall("x:numFmts/x:numFmt", XML_NS)}
        styles = styles_xml.findall("x:cellXfs/x:xf", XML_NS)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet_name = workbook.find("x:sheets/x:sheet", XML_NS).get("name")
        date_1904 = workbook.find("x:workbookPr", XML_NS)
        epoch = datetime(1904, 1, 1) if date_1904 is not None and date_1904.get("date1904") == "1" else datetime(1899, 12, 30)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    def value(cell):
        element = cell.find("x:v", XML_NS)
        if element is None:
            inline = cell.find("x:is", XML_NS)
            raw = "".join(part.text or "" for part in inline.findall(".//x:t", XML_NS)) if inline is not None else None
        else:
            raw = element.text
        if raw is not None and cell.get("t") == "s":
            raw = strings[int(raw)]
        style = styles[int(cell.get("s", "0"))]
        return raw, cell.get("t", "n"), formats.get(int(style.get("numFmtId", "0")))

    raw_rows = {}
    for row in sheet.findall("x:sheetData/x:row", XML_NS):
        raw_rows[int(row.get("r"))] = {re.match(r"[A-Z]+", cell.get("r")).group():
                                         (cell.get("r"), *value(cell))
                                         for cell in row.findall("x:c", XML_NS)}
    labels = {letter: raw_rows[3][letter][1] for letter in "CDEFGHIJK"}
    works = []
    coded_rows = {}
    latest_code_row = None
    for row_number in range(4, 381):
        row = raw_rows[row_number]
        title = row["B"][1]
        raw_code = row.get("A")
        if raw_code and raw_code[1] is None:
            raw_code = None
        code = raw_code[1] if raw_code else None
        if code and raw_code[2] == "n" and raw_code[3] == r"d\.m\.":
            day = epoch + timedelta(days=int(code))
            code = f"{day.day}.{day.month}."
        if code:
            parts = code.strip(".").split(".")
            parent = next((coded_rows[".".join(parts[:size])]
                           for size in range(len(parts) - 1, 0, -1)
                           if ".".join(parts[:size]) in coded_rows), None)
            coded_rows[code.strip(".")] = row_number
            latest_code_row = row_number
        else:
            parent = latest_code_row
        works.append({"id": uuid5(NAMESPACE_URL, f"{source_hash}/{sheet_name}/{row_number}"),
                      "source_row": row_number, "title": title, "code": code,
                      "raw_code": raw_code[1] if raw_code else None,
                      "raw_code_type": raw_code[2] if raw_code else None,
                      "raw_code_format": raw_code[3] if raw_code else None,
                      "code_cell": f"A{row_number}", "title_cell": f"B{row_number}",
                      "parent_source_row": parent,
                      "applicability": {label: row.get(letter, (None, None))[1] == "˅"
                                        for letter, label in labels.items()},
                      "applicability_cells": {label: {"cell": f"{letter}{row_number}",
                                                      "raw": row.get(letter, (None, None))[1]}
                                              for letter, label in labels.items()}})
    if len(works) != 377 or any(not work["title"] for work in works):
        raise SiteError("catalog_source_invalid", 503)
    return source_hash, [{"sheet_name": sheet_name, "filename": path.name, "works": works}]


def ensure_catalog(engine) -> str:
    if WORKBOOK is None:
        raise SiteError("catalog_source_missing", 503)
    source_hash, sources = _cells(WORKBOOK)
    source = sources[0]
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(804298270114)"))
        if not connection.execute(text("SELECT 1 FROM catalog_sources WHERE sha256=:hash"), {"hash": source_hash}).first():
            connection.execute(text("""INSERT INTO catalog_sources (sha256,filename,sheet_name,row_count)
                VALUES (:hash,:filename,:sheet,377)"""),
                {"hash": source_hash, "filename": source["filename"], "sheet": source["sheet_name"]})
            for work in source["works"]:
                connection.execute(text("""INSERT INTO catalog_works
                    (id,source_sha256,source_row,title,code,raw_code,raw_code_type,raw_code_format,
                     code_cell,title_cell,parent_source_row,applicability,applicability_cells)
                    VALUES (:id,:hash,:row,:title,:code,:raw_code,:raw_type,:raw_format,
                            :code_cell,:title_cell,:parent,CAST(:applicability AS jsonb),
                            CAST(:applicability_cells AS jsonb))"""),
                    {"id": work["id"], "hash": source_hash, "row": work["source_row"],
                     "title": work["title"], "code": work["code"],
                     "raw_code": work["raw_code"], "raw_type": work["raw_code_type"],
                     "raw_format": work["raw_code_format"], "code_cell": work["code_cell"],
                     "title_cell": work["title_cell"], "parent": work["parent_source_row"],
                     "applicability": json.dumps(work["applicability"], ensure_ascii=False),
                     "applicability_cells": json.dumps(work["applicability_cells"], ensure_ascii=False)})
        count = connection.execute(text("SELECT count(*) FROM catalog_works WHERE source_sha256=:hash"),
                                   {"hash": source_hash}).scalar_one()
        if count != 377:
            raise SiteError("catalog_import_incomplete", 503)
    return source_hash


def _engine(request: Request):
    if not request.app.state.readiness.ready.is_set():
        raise SiteError("service_not_ready", 503)
    return request.app.state.store.engine


def _response(error: SiteError) -> JSONResponse:
    return JSONResponse({"code": str(error)}, status_code=error.status)


@router.get("/catalog/works")
def list_catalog(request: Request):
    try:
        engine = _engine(request)
        source_hash = ensure_catalog(engine)
        with engine.connect() as connection:
            rows = connection.execute(text("""SELECT id, source_row, title, code, raw_code,
                raw_code_type, raw_code_format, code_cell, title_cell, parent_source_row,
                applicability, applicability_cells
                FROM catalog_works WHERE source_sha256=:hash ORDER BY source_row"""),
                {"hash": source_hash}).mappings().all()
        return {"source_sha256": source_hash, "total": len(rows),
                "works": [{**dict(row), "id": str(row["id"])} for row in rows]}
    except SiteError as error:
        return _response(error)


@router.post("/projects", status_code=201)
def create_project(request: Request, body: dict):
    try:
        engine = _engine(request)
        name = body.get("name")
        tz = body.get("timezone")
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or not isinstance(tz, str):
            raise SiteError("invalid_project")
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise SiteError("invalid_timezone") from None
        project_id = uuid4()
        zone_id = uuid4()
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO site_projects (id,name,timezone) VALUES (:id,:name,:timezone)"),
                               {"id": project_id, "name": name.strip(), "timezone": tz})
            connection.execute(text("INSERT INTO site_zones (id,project_id,name) VALUES (:id,:project,'Основной участок')"),
                               {"id": zone_id, "project": project_id})
        return {"id": str(project_id), "name": name.strip(), "timezone": tz, "default_zone_id": str(zone_id)}
    except SiteError as error:
        return _response(error)


@router.get("/projects")
def list_projects(request: Request):
    try:
        with _engine(request).connect() as connection:
            rows = connection.execute(text("SELECT id,name,timezone FROM site_projects ORDER BY created_at,id")).all()
        return {"projects": [{"id": str(row.id), "name": row.name, "timezone": row.timezone} for row in rows]}
    except SiteError as error:
        return _response(error)


@router.post("/projects/{project_id}/zones", status_code=201)
def create_zone(project_id: UUID, request: Request, body: dict):
    try:
        engine = _engine(request)
        name = body.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise SiteError("invalid_zone")
        zone_id = uuid4()
        with engine.begin() as connection:
            if not connection.execute(text("SELECT 1 FROM site_projects WHERE id=:id"), {"id": project_id}).first():
                raise SiteError("project_not_found", 404)
            try:
                connection.execute(text("INSERT INTO site_zones (id,project_id,name) VALUES (:id,:project,:name)"),
                                   {"id": zone_id, "project": project_id, "name": name.strip()})
            except IntegrityError:
                raise SiteError("zone_name_exists", 409) from None
        return {"id": str(zone_id), "project_id": str(project_id), "name": name.strip()}
    except SiteError as error:
        return _response(error)


@router.get("/projects/{project_id}/zones")
def list_zones(project_id: UUID, request: Request):
    try:
        with _engine(request).connect() as connection:
            if not connection.execute(text("SELECT 1 FROM site_projects WHERE id=:id"), {"id": project_id}).first():
                raise SiteError("project_not_found", 404)
            rows = connection.execute(text("SELECT id,name FROM site_zones WHERE project_id=:id ORDER BY created_at,id"),
                                      {"id": project_id}).all()
        return {"zones": [{"id": str(row.id), "name": row.name} for row in rows]}
    except SiteError as error:
        return _response(error)


def _entry(value: dict) -> dict:
    if not isinstance(value, dict):
        raise SiteError("invalid_plan_entry")
    try:
        work_id = UUID(value["catalog_work_id"])
        start = datetime.fromisoformat(value["start_at"])
        end = datetime.fromisoformat(value["end_at"])
    except (KeyError, TypeError, ValueError):
        raise SiteError("invalid_plan_entry") from None
    if start.utcoffset() is None or end.utcoffset() is None or start > end:
        raise SiteError("invalid_plan_period")
    state = value.get("state", "planned")
    if state not in ("planned", "active", "completed"):
        raise SiteError("invalid_plan_state")
    stage_key = value.get("stage_key")
    if stage_key not in (None, "excavation", "concreting", "roadwork"):
        raise SiteError("invalid_plan_stage")
    equipment = {}
    for field in ("expected_equipment", "allowed_equipment", "excluded_equipment"):
        items = value.get(field, [])
        if not isinstance(items, list) or any(not isinstance(item, str) or not item.strip() for item in items):
            raise SiteError("invalid_plan_equipment")
        equipment[field] = sorted(set(items))
    if set(equipment["excluded_equipment"]) & (set(equipment["expected_equipment"]) | set(equipment["allowed_equipment"])):
        raise SiteError("conflicting_plan_equipment")
    return {"catalog_work_id": work_id, "starts_at": start, "ends_at": end,
            "state": state, "stage_key": stage_key, **equipment}


@router.put("/zones/{zone_id}/plan")
def replace_zone_plan(zone_id: UUID, request: Request, body: dict):
    try:
        engine = _engine(request)
        ensure_catalog(engine)
        expected = body.get("expected_revision")
        values = body.get("entries")
        if type(expected) is not int or expected < 0 or not isinstance(values, list):
            raise SiteError("invalid_plan")
        entries = [_entry(item) for item in values]
        with engine.begin() as connection:
            if not connection.execute(text("SELECT 1 FROM site_zones WHERE id=:id FOR UPDATE"),
                                      {"id": zone_id}).first():
                raise SiteError("zone_not_found", 404)
            current = connection.execute(text("SELECT coalesce(max(revision_number),0) FROM zone_plan_revisions WHERE zone_id=:id"),
                                         {"id": zone_id}).scalar_one()
            if current != expected:
                raise SiteError("plan_revision_conflict", 409)
            ids = {entry["catalog_work_id"] for entry in entries}
            if ids:
                known = {row.id for row in connection.execute(text("SELECT id FROM catalog_works WHERE id=ANY(:ids)"),
                                                               {"ids": list(ids)}).all()}
                if known != ids:
                    raise SiteError("catalog_work_not_found", 404)
            revision_id = uuid4()
            connection.execute(text("INSERT INTO zone_plan_revisions (id,zone_id,revision_number) VALUES (:id,:zone,:number)"),
                               {"id": revision_id, "zone": zone_id, "number": current + 1})
            for entry in entries:
                connection.execute(text("""INSERT INTO zone_plan_entries
                    (id,revision_id,catalog_work_id,starts_at,ends_at,state,stage_key,
                     expected_equipment,allowed_equipment,excluded_equipment)
                    VALUES (:id,:revision,:work,:starts,:ends,:state,:stage_key,
                            CAST(:expected AS jsonb),CAST(:allowed AS jsonb),CAST(:excluded AS jsonb))"""),
                    {"id": uuid4(), "revision": revision_id, "work": entry["catalog_work_id"],
                     "starts": entry["starts_at"], "ends": entry["ends_at"], "state": entry["state"],
                     "stage_key": entry["stage_key"],
                     "expected": json.dumps(entry["expected_equipment"]),
                     "allowed": json.dumps(entry["allowed_equipment"]),
                     "excluded": json.dumps(entry["excluded_equipment"])})
        return {"revision_id": str(revision_id), "revision_number": current + 1, "entry_count": len(entries)}
    except SiteError as error:
        return _response(error)


@router.get("/zones/{zone_id}/plan")
def read_zone_plan(zone_id: UUID, request: Request, revision: int | None = None):
    try:
        with _engine(request).connect() as connection:
            if not connection.execute(text("SELECT 1 FROM site_zones WHERE id=:id"), {"id": zone_id}).first():
                raise SiteError("zone_not_found", 404)
            row = connection.execute(text("""SELECT id,revision_number,created_at FROM zone_plan_revisions
                WHERE zone_id=:zone AND (CAST(:revision AS integer) IS NULL OR revision_number=:revision)
                ORDER BY revision_number DESC LIMIT 1"""), {"zone": zone_id, "revision": revision}).first()
            if row is None:
                if revision is not None:
                    raise SiteError("plan_revision_not_found", 404)
                return {"zone_id": str(zone_id), "revision_number": 0, "entries": []}
            entries = connection.execute(text("""SELECT id,catalog_work_id,starts_at,ends_at,state,stage_key,
                expected_equipment,allowed_equipment,excluded_equipment FROM zone_plan_entries
                WHERE revision_id=:id ORDER BY starts_at,id"""), {"id": row.id}).mappings().all()
        return {"zone_id": str(zone_id), "revision_id": str(row.id), "revision_number": row.revision_number,
                "created_at": row.created_at.isoformat(),
                "entries": [{**dict(entry), "id": str(entry["id"]),
                             "catalog_work_id": str(entry["catalog_work_id"]),
                             "starts_at": entry["starts_at"].isoformat(),
                             "ends_at": entry["ends_at"].isoformat()} for entry in entries]}
    except SiteError as error:
        return _response(error)
