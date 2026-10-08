"""Write web/src/types/snapshot.schema.json from the Pydantic contract: python -m pipeline.common.schema"""
import json

from pipeline.common.config import ROOT
from pipeline.common.models import Snapshot

if __name__ == "__main__":
    p = ROOT / "web" / "src" / "types" / "snapshot.schema.json"
    p.write_text(json.dumps(Snapshot.model_json_schema(), indent=1), encoding="utf-8")
    print("wrote", p)
