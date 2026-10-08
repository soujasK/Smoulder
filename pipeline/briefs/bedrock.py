"""Bedrock briefs: strict JSON of numbers in, ~100 words out, every number checked; else template.

Model ID from config/briefs.yaml (or BEDROCK_MODEL_ID). Uses the Converse API.
"""
from __future__ import annotations

import json
import os

from pipeline.briefs.template import brief_facts, check_numbers, lint, template_brief
from pipeline.common.config import load

SYSTEM = (
    "You write short, neutral fact sheets about landfill fires detected by satellite in Indian cities. "
    "Use only the numbers in the JSON you are given, written exactly as given (no rounding, no new numbers, no percentages, no arithmetic). "
    "About 90 words, plain sentences, no headings or lists. "
    "Say 'fire days' and 'detections', never 'fires burned'. Do not blame anyone. Do not mention health, toxicity, exposure, emissions, legality or negligence. "
    "Do not use the words: illegal, negligent, cover-up, deliberate, saved, prevented, avoided, toxic, poisoned, exposed. "
    "End with one sentence on a limit: satellite pixels are larger than parts of the site and smouldering below the surface is often not seen."
)


def _prompt(facts: dict, lang: str) -> str:
    target = "English" if lang == "en" else "Hindi (Devanagari script; keep digits as Western numerals; keep site and city names as given)"
    return f"Write the fact sheet in {target} from this JSON only:\n{json.dumps(facts, ensure_ascii=False)}"


def generate(site: dict, episodes: list[dict], lang: str, run_id: str, client=None) -> dict:
    cfg = load("briefs")
    model_id = os.environ.get("BEDROCK_MODEL_ID") or cfg["model_id"]
    facts = brief_facts(site, episodes)
    if client is None:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=os.environ.get("BEDROCK_REGION", cfg.get("region", "ap-south-1")))
    problems: list[str] = []
    for attempt in range(1 + cfg["max_regenerations"]):
        msg = _prompt(facts, lang)
        if problems:
            msg += f"\n\nYour previous draft was rejected because it contained: {', '.join(problems)}. Use only numbers from the JSON."
        try:
            r = client.converse(
                modelId=model_id,
                system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [{"text": msg}]}],
                inferenceConfig={"maxTokens": cfg["max_tokens"], "temperature": cfg["temperature"]},
            )
        except Exception as e:  # noqa: BLE001 - any Bedrock failure falls back to the template
            fb = template_brief(site, episodes, lang, run_id)
            fb["label"] += f" · template (Bedrock unavailable: {type(e).__name__})"
            return fb
        text = "".join(c.get("text", "") for c in r["output"]["message"]["content"]).strip()
        bad = check_numbers(text, facts)
        banned = lint(text)
        if not bad and not banned:
            return {
                "site_id": site["site_id"],
                "lang": lang,
                "text": text,
                "generator": "bedrock",
                "model_id": model_id,
                "numbers_checked": True,
                "label": "Generated draft" if lang == "en" else "Generated draft · machine-translated, please verify",
                "run_id": run_id,
            }
        problems = [f"numbers not in the JSON: {', '.join(bad)}"] if bad else []
        problems += [f"banned words: {', '.join(banned)}"] if banned else []
    fb = template_brief(site, episodes, lang, run_id)
    fb["label"] += " · template (model output failed the number check)"
    return fb
