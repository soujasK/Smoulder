"""Deterministic template brief (fallback for Bedrock) + number check + banned-word lint."""
from __future__ import annotations

import re

BANNED = ["illegal", "negligent", "negligence", "cover-up", "cover up", "deliberate", "deliberately", "saved", "prevented", "avoided", "toxic", "poisoned", "exposed", "exposure"]
BANNED_HI = ["अवैध", "लापरवाह", "जहरीला", "ज़हरीला", "जानबूझकर"]

MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def brief_facts(site: dict, episodes: list[dict]) -> dict:
    """The strict JSON of numbers a brief may use (and nothing else)."""
    st = site["stats"]
    eps = [e for e in episodes if e["site_id"] == site["site_id"]]
    longest = max(eps, key=lambda e: (e["fire_days"], e["start_date"]), default=None)
    years = st["fire_days_by_year"]
    last_full = str(int(st["data_through"][:4]) - 1)
    ctx = site.get("context") or {}
    return {
        "site": site["name"],
        "city": site["city_name"],
        "area_ha": site["area_ha"],
        "first_year": int(st["first_data_date"][:4]),
        "data_through": st["data_through"],
        "fire_days_total": sum(years.values()),
        "last_full_year": int(last_full),
        "fire_days_last_full_year": years.get(last_full, 0),
        "fire_days_365": st["fire_days_365"],
        "episodes_total": len(eps),
        "longest_episode_start": longest["start_date"] if longest else None,
        "longest_episode_fire_days": longest["fire_days"] if longest else None,
        "schools_3km": ctx.get("schools_3km"),
        "buildings_1km": ctx.get("buildings_1km"),
        "people_1km_est": ctx.get("people_1km_est"),
    }


def _date_en(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS_EN[int(m) - 1]} {y}"


def _date_hi(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS_HI[int(m) - 1]} {y}"


def render(f: dict, lang: str) -> str:
    if lang == "en":
        s = [
            f"{f['site']} ({f['city']}, {f['area_ha']} ha): satellites recorded {f['fire_days_total']} fire days between {f['first_year']} and {_date_en(f['data_through'])} (Tier A or B VIIRS detections, nominal or high confidence).",
            f"In {f['last_full_year']} there were {f['fire_days_last_full_year']} fire days; in the last 365 days, {f['fire_days_365']}.",
        ]
        if f["longest_episode_start"]:
            s.append(f"The longest episode began on {_date_en(f['longest_episode_start'])} and had {f['longest_episode_fire_days']} fire days.")
        if f["schools_3km"] is not None:
            s.append(f"OpenStreetMap shows {f['schools_3km']} schools or colleges within 3 km and {f['buildings_1km']} buildings within 1 km; WorldPop estimates about {f['people_1km_est']} people within 1 km.")
        s.append("Detections are satellite pixels larger than parts of the site; smouldering below the surface is often not seen.")
        return " ".join(s)
    s = [
        f"{f['site']} ({f['city']}, {f['area_ha']} हेक्टेयर): उपग्रहों ने {f['first_year']} से {_date_hi(f['data_through'])} तक {f['fire_days_total']} दिन आग दर्ज की (VIIRS टियर A या B, सामान्य या उच्च विश्वास)।",
        f"{f['last_full_year']} में {f['fire_days_last_full_year']} दिन आग दर्ज हुई; पिछले 365 दिनों में {f['fire_days_365']} दिन।",
    ]
    if f["longest_episode_start"]:
        s.append(f"सबसे लंबा दौर {_date_hi(f['longest_episode_start'])} को शुरू हुआ और उसमें {f['longest_episode_fire_days']} दिन आग दर्ज हुई।")
    if f["schools_3km"] is not None:
        s.append(f"OpenStreetMap के अनुसार 3 किमी के भीतर {f['schools_3km']} स्कूल या कॉलेज और 1 किमी के भीतर {f['buildings_1km']} इमारतें हैं; WorldPop के अनुमान से 1 किमी के भीतर लगभग {f['people_1km_est']} लोग रहते हैं।")
    s.append("उपग्रह का एक पिक्सेल साइट के हिस्सों से बड़ा है; सतह के नीचे सुलगती आग अक्सर दिखाई नहीं देती।")
    return " ".join(s)


NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def allowed_numbers(facts: dict) -> set[str]:
    out = set()
    for v in facts.values():
        if v is None:
            continue
        if isinstance(v, (int, float)):
            out.add(_norm(str(v)))
        elif isinstance(v, str):
            for m in NUM.findall(v):
                out.add(_norm(m))
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                y, m, d = v.split("-")
                out |= {y, str(int(m)), str(int(d))}
    out |= {"1", "3", "365", "1000", "3000"}  # ring sizes and the window phrase used by the template
    return out


def _norm(s: str) -> str:
    s = s.replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def check_numbers(text: str, facts: dict) -> list[str]:
    """Return numbers in text that are not in the facts JSON (empty list = pass)."""
    allowed = allowed_numbers(facts)
    bad = []
    for m in NUM.findall(text):
        if _norm(m) not in allowed:
            bad.append(m)
    return bad


def lint(text: str) -> list[str]:
    low = text.lower()
    hits = [w for w in BANNED if re.search(r"\b" + re.escape(w) + r"\b", low)]
    hits += [w for w in BANNED_HI if w in text]
    return hits


def template_brief(site: dict, episodes: list[dict], lang: str, run_id: str) -> dict:
    f = brief_facts(site, episodes)
    text = render(f, lang)
    assert not check_numbers(text, f), check_numbers(text, f)
    assert not lint(text), lint(text)
    return {
        "site_id": site["site_id"],
        "lang": lang,
        "text": text,
        "generator": "template",
        "model_id": None,
        "numbers_checked": True,
        "label": "Generated draft" if lang == "en" else "Generated draft · Hindi draft translation, please verify",
        "run_id": run_id,
    }
