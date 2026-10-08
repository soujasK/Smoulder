import json

from conftest import ROOT

from pipeline.common.models import Snapshot

SNAP_PATH = ROOT / "web" / "public" / "data" / "snapshot.json"
SCHEMA_PATH = ROOT / "web" / "src" / "types" / "snapshot.schema.json"


def test_snapshot_validates_against_pydantic():
    snap = json.loads(SNAP_PATH.read_text(encoding="utf-8"))
    Snapshot.model_validate(snap)
    assert snap["pipeline_run_id"] and snap["generated_at"] and snap["sources"]


def test_json_schema_for_web_is_current():
    """web/src/types/snapshot.schema.json is generated from the Pydantic model; the web test validates the snapshot with it."""
    current = Snapshot.model_json_schema()
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8")) == current, "run: python -m pipeline.common.schema"


def test_no_zero_filled_years_hidden():
    """Years without detections stay as 0 in data; the UI renders them as 'no detections' (see web DOM test)."""
    snap = json.loads(SNAP_PATH.read_text(encoding="utf-8"))
    for s in snap["sites"]:
        assert all(isinstance(v, int) for v in s["stats"]["fire_days_by_year"].values())
