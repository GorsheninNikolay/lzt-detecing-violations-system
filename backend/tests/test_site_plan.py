from pathlib import Path
from uuid import uuid4

import pytest

from app.application.site import WORKBOOK, SiteError, _cells, _entry


def test_catalog_keeps_every_source_row_and_raw_date_codes():
    source_hash, sources = _cells(WORKBOOK)
    works = sources[0]["works"]
    assert len(source_hash) == 64
    assert len(works) == 377
    assert [work["source_row"] for work in works] == list(range(4, 381))
    assert len({work["id"] for work in works}) == 377
    assert len([work for work in works if work["raw_code"] is None]) == 250
    assert len([work for work in works if work["raw_code_type"] == "n"
                and work["raw_code_format"] == r"d\.m\."]) == 19
    assert works[1]["code"] == "10.1."
    assert works[1]["raw_code"] == "45667"
    assert works[1]["code_cell"] == "A5"
    assert works[39]["code"] == "12"
    assert works[42]["code"] == "12.3."
    assert works[42]["raw_code"] == "45728"
    assert works[42]["parent_source_row"] == 43
    assert all(len(work["applicability"]) == 9 for work in works)
    assert works[1]["applicability_cells"]["Жильё"] == {"cell": "C5", "raw": "˅"}
    assert sum(sum(work["applicability"].values()) for work in works) == 2482
    assert len({work["title"] for work in works}) < 377


def test_plan_entry_preserves_parallel_operations_and_rejects_unusable_dates():
    work = str(uuid4())
    first = _entry({"catalog_work_id": work, "start_at": "2026-09-25T08:00:00+03:00",
                    "end_at": "2026-09-25T18:00:00+03:00",
                    "expected_equipment": ["экскаватор", "экскаватор"]})
    second = _entry({"catalog_work_id": work, "start_at": "2026-09-25T08:00:00+03:00",
                     "end_at": "2026-09-25T18:00:00+03:00",
                     "allowed_equipment": ["самосвал"]})
    assert first["starts_at"] == second["starts_at"]
    assert first["expected_equipment"] == ["экскаватор"]
    with pytest.raises(SiteError, match="invalid_plan_period"):
        _entry({"catalog_work_id": work, "start_at": "2026-09-25T08:00:00",
                "end_at": "2026-09-25T18:00:00"})
    with pytest.raises(SiteError, match="conflicting_plan_equipment"):
        _entry({"catalog_work_id": work, "start_at": "2026-09-25T08:00:00+03:00",
                "end_at": "2026-09-25T18:00:00+03:00",
                "expected_equipment": ["экскаватор"], "excluded_equipment": ["экскаватор"]})



def test_catalog_suggestions_require_exact_source_row_title_and_hash():
    from app.domain.construction_stages import CATALOG_STAGE_SUGGESTIONS, STAGES, catalog_suggestion
    source_hash, sources = _cells(WORKBOOK)
    works = {work["source_row"]: work for work in sources[0]["works"]}
    assert {stage for _, stage in CATALOG_STAGE_SUGGESTIONS.values()} == set(STAGES)
    for number, (title, stage) in CATALOG_STAGE_SUGGESTIONS.items():
        assert works[number]["title"] == title
        suggestion = catalog_suggestion(source_hash, number, title)
        assert suggestion["suggested_stage"] == stage
        assert suggestion["requires_manual_confirmation"] is True
        assert catalog_suggestion("changed", number, title)["suggested_stage"] is None
        assert catalog_suggestion(source_hash, number, title + " changed")["suggested_stage"] is None
    assert catalog_suggestion(source_hash, 99, works[99]["title"])["suggested_stage"] is None



@pytest.mark.parametrize("stage", [[], {}, 1, False])
def test_invalid_plan_stage_type_is_stable_validation_error(stage):
    with pytest.raises(SiteError, match="invalid_plan_stage"):
        _entry({"catalog_work_id": str(uuid4()), "start_at": "2030-01-01T00:00:00Z",
                "end_at": "2030-01-02T00:00:00Z", "stage_key": stage})
