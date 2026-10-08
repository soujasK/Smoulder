from pipeline.briefs.template import brief_facts, check_numbers, lint, render, template_brief

SITE = {
    "site_id": "g", "name": "Ghazipur", "city_name": "Delhi", "area_ha": 29.2,
    "stats": {"fire_days_by_year": {"2024": 12, "2025": 9, "2026": 3}, "fire_days_365": 7, "first_data_date": "2019-01-01", "data_through": "2026-10-08"},
    "context": {"schools_3km": 87, "buildings_1km": 525, "people_1km_est": 166781},
}
EPS = [{"site_id": "g", "start_date": "2024-04-21", "end_date": "2024-04-24", "fire_days": 4}]


def test_template_numbers_all_in_facts():
    f = brief_facts(SITE, EPS)
    for lang in ("en", "hi"):
        assert check_numbers(render(f, lang), f) == []


def test_number_check_rejects_invented_numbers():
    f = brief_facts(SITE, EPS)
    assert check_numbers("Ghazipur had 13 fire days in 2025.", f) == ["13"]
    assert check_numbers("About 166,781 people; 29.2 ha.", f) == []
    assert check_numbers("Roughly 40% of days.", f) == ["40"]


def test_lint_banned_words():
    assert lint("The fire was deliberately set and toxic.") == ["deliberately", "toxic"]
    assert lint("Residents were exposed to smoke") == ["exposed"]
    assert lint("Satellites recorded 4 fire days.") == []


def test_template_brief_labels():
    b = template_brief(SITE, EPS, "hi", "r1")
    assert b["generator"] == "template" and "verify" in b["label"]
    assert b["numbers_checked"] is True


class FakeBedrock:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = 0

    def converse(self, **kw):
        self.calls += 1
        return {"output": {"message": {"content": [{"text": self.texts.pop(0)}]}}}


def test_bedrock_regenerates_then_accepts():
    from pipeline.briefs.bedrock import generate

    fake = FakeBedrock(["Ghazipur had 99 fire days.", "Ghazipur (Delhi, 29.2 ha) had 9 fire days in 2025."])
    b = generate(SITE, EPS, "en", "r1", client=fake)
    assert fake.calls == 2 and b["generator"] == "bedrock" and "99" not in b["text"]


def test_bedrock_falls_back_to_template():
    from pipeline.briefs.bedrock import generate

    fake = FakeBedrock(["13 fire days"] * 3)
    b = generate(SITE, EPS, "en", "r1", client=fake)
    assert fake.calls == 3 and b["generator"] == "template" and "number check" in b["label"]


def test_bedrock_rejects_banned_words():
    from pipeline.briefs.bedrock import generate

    fake = FakeBedrock(["The toxic fire burned 9 fire days in 2025."] * 3)
    b = generate(SITE, EPS, "en", "r1", client=fake)
    assert b["generator"] == "template"
