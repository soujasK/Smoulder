import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures"

from shapely.geometry import box, mapping  # noqa: E402

from pipeline.common.geo import project_point, to_wgs84, utm_epsg  # noqa: E402

# A 1 km x 1 km square site centred near Ghazipur, for synthetic tests.
EPSG = utm_epsg(77.3273, 28.6242)
CX, CY = project_point(77.3273, 28.6242, EPSG)


def square_site(site_id="sq", half_m=500.0):
    poly = to_wgs84(box(CX - half_m, CY - half_m, CX + half_m, CY + half_m), EPSG)
    c = poly.centroid
    return {"site_id": site_id, "name": "Square", "utm_epsg": EPSG, "polygon": mapping(poly), "centroid": [c.x, c.y]}
