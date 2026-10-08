"""Terrain tiles for the 3D view: Copernicus DEM GLO-30 heightmap + Sentinel-2 L2A true-colour drape.

Grid: a square of side `extent_m` centred on the site centroid, in the site's UTM CRS.
Outputs (web/public/terrain/<id>/): height.png (16-bit grey, linear min..max), drape.webp, meta.json
DEM: s3://copernicus-dem-30m (AWS Open Data, public, no requester-pays), read as COG over HTTPS.
Usage: python -m pipeline.terrain.terrain [site_id ...] [--city]
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date, timedelta

import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds

from pipeline.common.config import ROOT, load
from pipeline.common.geo import project_point
from pipeline.common.sites import load_sites

DEM_URL = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
OUT = ROOT / "web" / "public" / "terrain"


def dem_tiles(w: float, s: float, e: float, n: float) -> list[str]:
    urls = []
    for la in range(math.floor(s), math.floor(n) + 1):
        for lo in range(math.floor(w), math.floor(e) + 1):
            urls.append(DEM_URL.format(ns="N" if la >= 0 else "S", lat=abs(la), ew="E" if lo >= 0 else "W", lon=abs(lo)))
    return urls


def grid(site: dict, extent_m: float, px: int):
    cx, cy = site.get("_centre_utm") or project_point(site["centroid"][0], site["centroid"][1], site["utm_epsg"])
    half = extent_m / 2
    res = extent_m / px
    tr = from_origin(cx - half, cy + half, res, res)
    crs = CRS.from_epsg(site["utm_epsg"])
    bounds = (cx - half, cy - half, cx + half, cy + half)
    return tr, crs, bounds


def build_dem(site: dict, extent_m: float, px: int) -> tuple[np.ndarray, dict]:
    tr, crs, bounds = grid(site, extent_m, px)
    wgs = transform_bounds(crs, CRS.from_epsg(4326), *bounds)
    dst = np.full((px, px), np.nan, dtype="float32")
    for url in dem_tiles(*wgs):
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES"):
            with rasterio.open(url) as src:
                tmp = np.full((px, px), np.nan, dtype="float32")
                reproject(rasterio.band(src, 1), tmp, src_nodata=src.nodata, dst_transform=tr, dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.bilinear)
                dst = np.where(np.isnan(dst), tmp, dst)
    if np.isnan(dst).any():
        dst = np.where(np.isnan(dst), np.nanmin(dst), dst)
    meta = {"crs": f"EPSG:{site['utm_epsg']}", "bounds_utm": [round(b, 1) for b in bounds], "bounds_wgs84": [round(v, 6) for v in wgs], "px": px, "res_m": extent_m / px}
    return dst, meta


def write_height_png(arr: np.ndarray, path) -> tuple[float, float]:
    lo, hi = float(arr.min()), float(arr.max())
    scaled = np.round((arr - lo) / max(hi - lo, 1e-6) * 65535).astype(np.uint16)
    Image.fromarray(scaled).save(path)
    return lo, hi


def find_drape_scene(site: dict, cfg: dict, lookback_days: int = 200) -> dict | None:
    from pystac_client import Client

    lon, lat = site["centroid"]
    end = date.today()
    start = end - timedelta(days=lookback_days)
    cat = Client.open(cfg["stac_url"])
    items = list(
        cat.search(
            collections=[cfg["collection"]],
            intersects={"type": "Point", "coordinates": [lon, lat]},
            datetime=f"{start.isoformat()}/{end.isoformat()}",
            query={"eo:cloud_cover": {"lt": 5}},
            max_items=50,
        ).items()
    )
    if not items:
        return None
    items.sort(key=lambda it: (round(it.properties.get("eo:cloud_cover", 100)), -it.datetime.timestamp()))
    # prefer the most recent among the clearest
    clear = [it for it in items if it.properties.get("eo:cloud_cover", 100) < 1] or items[:5]
    it = max(clear, key=lambda it: it.datetime)
    return {"id": it.id, "date": it.datetime.date().isoformat(), "cloud": it.properties.get("eo:cloud_cover"), "visual": it.assets["visual"].href}


def build_drape(site: dict, extent_m: float, px: int, scene: dict) -> np.ndarray:
    tr, crs, _ = grid(site, extent_m, px)
    out = np.zeros((3, px, px), dtype="uint8")
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES"):
        with rasterio.open(scene["visual"]) as src:
            for b in range(3):
                reproject(rasterio.band(src, b + 1), out[b], dst_transform=tr, dst_crs=crs, resampling=Resampling.bilinear)
    return out


def city_frame(city: str) -> dict:
    """A pseudo-site centred on the bbox of a city's sites, with extent covering all of them."""
    ss = [s for s in load_sites() if s["city"] == city]
    epsg = ss[0]["utm_epsg"]
    pts = [project_point(s["centroid"][0], s["centroid"][1], epsg) for s in ss]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    cfg = load("terrain")["city"]
    return {
        "site_id": city,
        "city": city,
        "utm_epsg": epsg,
        "centroid": ss[0]["centroid"],
        "_centre_utm": ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2),
        "_extent_m": max(cfg["extent_m"], round(span + 2 * cfg["margin_m"], -3)),
    }


def build(site: dict, kind: str = "site") -> dict:
    tcfg = dict(load("terrain")[kind])
    if site.get("_extent_m"):
        tcfg["extent_m"] = site["_extent_m"]
    icfg = load("imagery")
    d = OUT / (site["site_id"] if kind == "site" else f"{site['city']}-city")
    d.mkdir(parents=True, exist_ok=True)
    arr, meta = build_dem(site, tcfg["extent_m"], tcfg["dem_px"])
    if tcfg.get("smooth_px"):
        # The DEM is a surface model: buildings add noise. Smooth city tiles so contours read as terrain.
        from scipy.ndimage import gaussian_filter

        arr = gaussian_filter(arr, sigma=tcfg["smooth_px"])
        meta["smoothed_sigma_px"] = tcfg["smooth_px"]
    lo, hi = write_height_png(arr, d / "height.png")
    meta.update(
        {
            "centre_utm": [round((meta["bounds_utm"][0] + meta["bounds_utm"][2]) / 2, 1), round((meta["bounds_utm"][1] + meta["bounds_utm"][3]) / 2, 1)],
            "site_id": site["site_id"],
            "kind": kind,
            "extent_m": tcfg["extent_m"],
            "min_m": round(lo, 2),
            "max_m": round(hi, 2),
            "vertical_exaggeration": tcfg["vertical_exaggeration"],
            "contour_interval_m": tcfg["contour_interval_m"],
            "dem": "Copernicus DEM GLO-30 (AWS Open Data). Elevation data vintage 2011-2015 (TanDEM-X); landfill height today differs.",
        }
    )
    if tcfg.get("drape_px"):
        scene = find_drape_scene(site, icfg)
        if scene:
            rgb = build_drape(site, tcfg["extent_m"], tcfg["drape_px"], scene)
            Image.fromarray(np.transpose(rgb, (1, 2, 0))).save(d / "drape.webp", quality=82)
            meta["drape"] = {"scene": scene["id"], "date": scene["date"], "cloud_pct": scene["cloud"], "res_m": tcfg["extent_m"] / tcfg["drape_px"], "credit": "Contains modified Copernicus Sentinel data " + scene["date"][:4]}
        else:
            meta["drape"] = None
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def main(args: list[str]) -> None:
    city = "--city" in args
    ids = [a for a in args if not a.startswith("--")]
    done_city = set()
    for s in load_sites():
        if ids and s["site_id"] not in ids:
            continue
        if city:
            if s["city"] in done_city:
                continue
            done_city.add(s["city"])
            print(build(city_frame(s["city"]), "city"))
        else:
            m = build(s, "site")
            print(s["site_id"], m["min_m"], m["max_m"], m.get("drape", {}) and m["drape"]["date"])


if __name__ == "__main__":
    main(sys.argv[1:])
