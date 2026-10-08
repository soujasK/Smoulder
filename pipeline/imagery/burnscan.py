"""Burn Scan: Sentinel-2 L2A around each fire episode; dNBR burn mask and hot-surface heuristic inside the site.

Scenes: Earth Search STAC (AWS Open Data registry), collection sentinel-2-l2a, COGs read over HTTPS.
Reflectance = DN * scale + offset as declared per asset (raster:bands).
  NBR  = (B8A - B12) / (B8A + B12)             20 m grid
  dNBR = NBR_pre - NBR_post; burn where dNBR > dnbr_threshold, inside the polygon, clear in both scenes
  hot  = B12 > hot_b12_min and B12 > B11 > B8A  (heuristic; post scene)
  area = burn_px * pixel_ha; range = area +/- 0.5 * boundary_px * pixel_ha (widened by cloudy boundary pixels)
Usage: python -m pipeline.imagery.burnscan [site_id ...]
"""
from __future__ import annotations

import io
import os
import sys
from datetime import date, timedelta

import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from shapely.geometry import mapping, shape

from pipeline.common import store
from pipeline.common.config import ROOT, load
from pipeline.common.geo import to_metric
from pipeline.common.sites import load_sites

WEB_IMG = ROOT / "web" / "public" / "imagery"
CLEAR_SCL = {4, 5, 6, 7, 11}  # vegetation, not vegetated, water, unclassified, snow; excludes cloud, shadow, saturated, no data
MAX_EPISODES = 4


def grid(site: dict, res: float, pad_m: float = 400):
    poly = to_metric(shape(site["polygon"]), site["utm_epsg"])
    minx, miny, maxx, maxy = poly.bounds
    minx, miny, maxx, maxy = minx - pad_m, miny - pad_m, maxx + pad_m, maxy + pad_m
    w, h = int(np.ceil((maxx - minx) / res)), int(np.ceil((maxy - miny) / res))
    return from_origin(minx, maxy, res, res), w, h, poly


def read_band(href: str, tr, w: int, h: int, crs: CRS, scale: float | None, offset: float | None, nearest: bool = False) -> np.ndarray:
    out = np.zeros((h, w), dtype="float32")
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES", GDAL_HTTP_MAX_RETRY="3"):
        with rasterio.open(href) as src:
            reproject(rasterio.band(src, 1), out, src_nodata=0, dst_nodata=0, dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest if nearest else Resampling.bilinear)
    if scale is None:
        return out
    valid = out > 0
    refl = out * scale + (offset or 0.0)
    return np.where(valid, refl, np.nan)


def _band_meta(item, key):
    b = (item.assets[key].extra_fields.get("raster:bands") or [{}])[0]
    return b.get("scale", 0.0001), b.get("offset", 0.0)


def scenes(site: dict, start: date, end: date, cfg: dict):
    from pystac_client import Client

    lon, lat = site["centroid"]
    cat = Client.open(cfg["stac_url"])
    items = list(cat.search(collections=[cfg["collection"]], intersects={"type": "Point", "coordinates": [lon, lat]},
                            datetime=f"{start.isoformat()}/{end.isoformat()}", query={"eo:cloud_cover": {"lt": cfg["max_cloud_pct"]}}, max_items=40).items())
    return sorted(items, key=lambda it: it.datetime)


def load_scene(item, site, tr, w, h, mask):
    crs = CRS.from_epsg(site["utm_epsg"])
    scl = read_band(item.assets["scl"].href, tr, w, h, crs, None, None, nearest=True).astype("uint8")
    clear = np.isin(scl, list(CLEAR_SCL))
    frac_clear = float(clear[mask].mean()) if mask.any() else 0.0
    bands = {k: read_band(item.assets[k].href, tr, w, h, crs, *_band_meta(item, k)) for k in ("red", "nir08", "swir16", "swir22")}
    return {"item": item, "date": item.datetime.date().isoformat(), "clear": clear, "frac_clear": frac_clear, "cloud": item.properties.get("eo:cloud_cover"), **bands}


def stretch(rgb: np.ndarray) -> np.ndarray:
    out = np.zeros(rgb.shape, dtype="uint8")
    for i in range(3):
        b = rgb[..., i]
        v = b[np.isfinite(b)]
        if v.size == 0:
            continue
        lo, hi = np.percentile(v, 2), np.percentile(v, 98)
        out[..., i] = np.clip((np.nan_to_num(b, nan=lo) - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype("uint8")
    return out


def swir_png(sc) -> bytes:
    # SWIR composite R=B12, G=B8A, B=B4: vegetation green, bare/burned red-brown, active fire bright
    img = Image.fromarray(stretch(np.dstack([sc["swir22"], sc["nir08"], sc["red"]]))).resize((sc["swir22"].shape[1] * 4, sc["swir22"].shape[0] * 4), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=88)
    return buf.getvalue()


def mask_png(burn: np.ndarray, hot: np.ndarray, boundary: np.ndarray) -> bytes:
    h, w = burn.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    rgba[burn] = (224, 122, 46, 210)    # ember-4
    rgba[hot] = (244, 199, 122, 255)    # ember-5
    rgba[boundary] = (233, 228, 216, 255)  # bone outline
    img = Image.fromarray(rgba, "RGBA").resize((w * 4, h * 4), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def publish_crop(key: str, data: bytes, content_type: str) -> str:
    store.put(f"imagery/{key}", data, content_type)
    if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):  # local runs also write into the web app for offline mode
        p = WEB_IMG / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return f"/imagery/{key}"


def measure_episode(site: dict, ep: dict, cfg: dict) -> list[dict]:
    res = cfg["grid_m"]
    tr, w, h, poly = grid(site, res)
    inside = rasterize([(mapping(poly), 1)], out_shape=(h, w), transform=tr, fill=0, dtype="uint8").astype(bool)
    edge = rasterize([(mapping(poly.exterior), 1)], out_shape=(h, w), transform=tr, fill=0, dtype="uint8", all_touched=True).astype(bool)
    start, end = date.fromisoformat(ep["start_date"]), date.fromisoformat(ep["end_date"])
    items = scenes(site, start - timedelta(days=cfg["days_before"]), end + timedelta(days=cfg["days_after"]), cfg)
    pre_items = [it for it in items if it.datetime.date() < start][::-1]
    post_items = [it for it in items if it.datetime.date() >= start]
    pick = lambda its: next((sc for sc in (load_scene(it, site, tr, w, h, inside) for it in its[:3]) if sc["frac_clear"] >= 0.8), None)  # noqa: E731
    pre, post = pick(pre_items), pick(post_items)
    base = {"site_id": site["site_id"], "episode_start": ep["start_date"]}
    if not pre or not post:
        why = "no clear Sentinel-2 scene before the episode" if not pre else "no clear Sentinel-2 scene after the episode"
        return [{**base, "scene_date": (post or pre or {"date": ep["start_date"]})["date"], "kind": "post", "hot_px": None, "burn_px": None,
                 "area_ha": None, "area_ha_lo": None, "area_ha_hi": None, "cloud_pct": None, "note": f"No clear image for this episode ({why}, cloud < {cfg['max_cloud_pct']}% and ≥ 80% clear pixels over the site, ±{cfg['days_before']} days).", "crops": {}}]
    nbr = lambda s: (s["nir08"] - s["swir22"]) / (s["nir08"] + s["swir22"] + 1e-6)  # noqa: E731
    dnbr = nbr(pre) - nbr(post)
    both_clear = pre["clear"] & post["clear"]
    burn = (dnbr > cfg["dnbr_threshold"]) & inside & both_clear & np.isfinite(dnbr)
    hot = (post["swir22"] > cfg["hot_b12_min"]) & (post["swir22"] > post["swir16"]) & (post["swir16"] > post["nir08"]) & inside & post["clear"]
    px = cfg["pixel_ha"]
    area = float(burn.sum() * px)
    cloudy_edge = int((edge & ~both_clear).sum())
    half_edge = 0.5 * int(edge.sum()) * px + cloudy_edge * px
    key = f"{site['site_id']}/{ep['start_date']}"
    crops_pre = {"swir": publish_crop(f"{key}/pre_{pre['date']}_swir.webp", swir_png(pre), "image/webp")}
    crops_post = {
        "swir": publish_crop(f"{key}/post_{post['date']}_swir.webp", swir_png(post), "image/webp"),
        "mask": publish_crop(f"{key}/post_{post['date']}_mask.png", mask_png(burn, hot, edge), "image/png"),
    }
    note = f"Scenes {pre['item'].id} and {post['item'].id}; {round(pre['frac_clear'] * 100)}% and {round(post['frac_clear'] * 100)}% clear over the site."
    return [
        {**base, "scene_date": pre["date"], "kind": "pre", "hot_px": None, "burn_px": None, "area_ha": None, "area_ha_lo": None, "area_ha_hi": None, "cloud_pct": pre["cloud"], "note": note, "crops": crops_pre},
        {**base, "scene_date": post["date"], "kind": "post", "hot_px": int(hot.sum()), "burn_px": int(burn.sum()), "area_ha": round(area, 2),
         "area_ha_lo": round(max(0.0, area - half_edge), 2), "area_ha_hi": round(area + half_edge, 2), "cloud_pct": post["cloud"], "note": note, "crops": crops_post},
    ]


def measure_site(site: dict) -> list[dict]:
    cfg = load("imagery")
    eps = [e for e in store.get_json("derived/episodes.json", []) if e["site_id"] == site["site_id"] and e["start_date"] >= "2019-01-01"]
    eps.sort(key=lambda e: (e["detections"], e["max_frp_mw"] or 0), reverse=True)
    obs: list[dict] = []
    for ep in eps[:MAX_EPISODES]:
        try:
            obs += measure_episode(site, ep, cfg)
        except Exception as e:  # noqa: BLE001 - one bad scene should not drop the site
            obs.append({"site_id": site["site_id"], "episode_start": ep["start_date"], "scene_date": ep["start_date"], "kind": "post", "hot_px": None, "burn_px": None,
                        "area_ha": None, "area_ha_lo": None, "area_ha_hi": None, "cloud_pct": None, "note": f"Imagery could not be read ({type(e).__name__}).", "crops": {}})
    all_obs = [o for o in store.get_json("derived/burn_obs.json", []) if o["site_id"] != site["site_id"]] + obs
    store.put_json("derived/burn_obs.json", all_obs)
    return obs


def main(ids: list[str]) -> None:
    for s in load_sites():
        if ids and s["site_id"] not in ids:
            continue
        for o in measure_site(s):
            print(s["site_id"], o["episode_start"], o["kind"], o["scene_date"], o["area_ha"], o["area_ha_lo"], o["area_ha_hi"], o["hot_px"], o["note"][:90])


if __name__ == "__main__":
    main(sys.argv[1:])
