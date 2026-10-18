import asyncio
from types import SimpleNamespace

import pytest

from fundfinder.intent import Sort
from fundfinder.llm_intent import (
    EM_GROUP,
    TOOL_NAME,
    LlmInterpreter,
    LlmUnavailable,
    Vocabulary,
    reading_from_plan,
    tool_schema,
)

VOCAB = Vocabulary(
    asset_classes=("Equity", "Fixed Income", "Mixed Assets", "Property"),
    ia_sectors=("UK All Companies", "UK Gilts", "Japan"),
    tracked_indexes=("FTSE 100 Index", "S&P 500 Index"),
)

FTSE_PLAN = {
    "search_text": "UK large companies index fund tracking the FTSE 100 Index",
    "summary": "Low-cost index funds that track the FTSE 100, cheapest first.",
    "is_passive": True,
    "asset_class": "Equity",
    "ia_sector": None,
    "ocf_max": None,
    "exclude_sectors": [],
    "exclude_regions": [],
    "exclude_asset_classes": [],
    "tracked_indexes": ["FTSE 100 Index", "Made-up Index"],
    "sort": "cost",
}


class FakeMessages:
    def __init__(self, reply=None, error: Exception | None = None):
        self.reply = reply if reply is not None else FTSE_PLAN
        self.error = error
        self.calls: list[dict] = []

    async def create(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        block = SimpleNamespace(type="tool_use", name=TOOL_NAME, input=self.reply)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="..."), block])


def interpreter(**kw) -> tuple[LlmInterpreter, FakeMessages]:
    messages = FakeMessages(**kw)
    return LlmInterpreter(SimpleNamespace(messages=messages), "claude-test"), messages


def test_reads_vague_query_into_a_plan():
    llm, messages = interpreter()
    r = asyncio.run(llm.read("cheap well known Uk", VOCAB))
    assert r.text.startswith("UK large companies index fund tracking the FTSE 100")
    assert r.filters.is_passive is True and r.filters.asset_class == "Equity"
    assert r.sort is Sort.cost
    assert r.exclusions.tracked_indexes == ["FTSE 100 Index"]  # unknown index dropped
    assert [a.key for a in r.applied] == ["is_passive", "asset_class", "tracks:FTSE 100 Index"]
    assert r.applied[-1].label == "Tracks the FTSE 100"
    call = messages.calls[0]
    assert call["model"] == "claude-test"
    assert call["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    assert "<query>cheap well known Uk</query>" in call["messages"][0]["content"]
    assert "FTSE 100 Index" in call["messages"][0]["content"]  # vocabulary is offered


def test_caches_per_normalised_query():
    llm, messages = interpreter()
    asyncio.run(llm.read("cheap well known Uk", VOCAB))
    asyncio.run(llm.read("  cheap well   known uk ", VOCAB))
    assert len(messages.calls) == 1


def test_failures_raise_unavailable():
    llm, _ = interpreter(error=TimeoutError("slow"))
    with pytest.raises(LlmUnavailable):
        asyncio.run(llm.read("x", VOCAB))

    llm, messages = interpreter()
    messages.create = _no_tool_reply
    with pytest.raises(LlmUnavailable):
        asyncio.run(llm.read("x", VOCAB))


async def _no_tool_reply(**kw):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text="hello")])


def test_unknown_or_invalid_values_are_dropped():
    raw = {
        "search_text": "",
        "summary": "s",
        "is_passive": "yes",  # not a bool
        "asset_class": "Crypto",  # not in the data
        "ia_sector": "UK Gilts",
        "ocf_max": 40,  # implausible
        "exclude_sectors": ["Information Technology", "Astrology", 3],
        "exclude_regions": ["UK", "Emerging markets", "Mars"],
        "exclude_asset_classes": ["Property", "Gold"],
        "sort": "random",
    }
    r = reading_from_plan(raw, "original query", VOCAB)
    assert r.text == "original query"  # empty search_text falls back to q
    assert r.filters.is_passive is None and r.filters.asset_class is None
    assert r.filters.ocf_max is None and r.filters.ia_sector == "UK Gilts"
    assert r.exclusions.sectors == ["Information Technology"]
    assert r.exclusions.regions == ["UK", EM_GROUP]
    assert r.sort is Sort.relevance
    assert [a.key for a in r.applied] == [
        "ia_sector",
        "not_asset:Property",
        "not_sector:Information Technology",
        "not_region:UK",
        f"not_region:{EM_GROUP}",
    ]


def test_tool_schema_offers_only_real_values():
    schema = tool_schema(VOCAB)["properties"]
    assert schema["ia_sector"]["anyOf"][0]["enum"] == list(VOCAB.ia_sectors)
    assert "Emerging markets" in schema["exclude_regions"]["items"]["enum"]
    assert schema["sort"]["enum"] == ["relevance", "cost", "cost_desc"]
