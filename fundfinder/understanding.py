"""Query understanding: turn the constraint-like parts of a plain-English search
into structured filters, and leave the descriptive rest for the embedding.

Embeddings capture what a query is *about*, but not limits ("under 0.2%"),
hard requirements ("index funds") or negation ("not tech" pulls tech funds
*closer*). This module pulls those parts out with deterministic rules:

  * cost caps           "under 0.2%", "fees below 30bps"   -> ocf_max
  * fund type           "index fund", "tracker", "active"  -> is_passive
  * asset class         "bonds", "property", "multi-asset" -> asset_class
  * negations           "not tech", "excluding UK", "no bonds"
                        -> exclusions, and removed from the embedded text

Places and themes stay soft: the embedding already handles "Japan" or
"healthcare" well, and a hard filter would throw away near misses. Each
inference is reported back (key + label) so clients can show it and let the
user drop it with `ignore`.
"""

import re
from dataclasses import dataclass, field

from pydantic import BaseModel

from fundfinder.search import Filters

# A fund is "mainly" a sector or region at this share. Tech funds in the data
# hold 60-81% technology; broad global funds reach about 40%.
MAINLY = 0.5
# OCFs above this are implausible, so a bigger number is probably an allocation
# ("under 50% in shares") unless cost words make it explicit.
MAX_PLAUSIBLE_OCF = 3.0
# Even with cost words, a cap above this is not a cost ("fees under 99999%").
# It also keeps huge numbers (float("9" * 400) is inf) out of filters and JSON.
MAX_OCF = 100.0

# Embedded when a query is only constraints.
NEUTRAL_TEXT = "investment fund"

# ------------------------------------------------------------------ vocabulary
# Phrase patterns -> canonical names. Longer phrases first within each group.

SECTORS: dict[str, str] = {
    r"information technology|technology|tech|software|semiconductors?|chips?": (
        "Information Technology"
    ),
    r"health\s*care|healthcare|pharma(?:ceuticals?)?|biotech(?:nology)?": "Health Care",
    r"financials?|banks?|banking": "Financials",
    r"oil and gas|oil & gas|energy|oil": "Energy",
    r"mining|miners|materials": "Materials",
    r"utilities": "Utilities",
    r"real estate|reits?": "Real Estate",
    r"industrials?|defence|defense": "Industrials",
    r"consumer staples|staples": "Consumer Staples",
    r"consumer discretionary|retail": "Consumer Discretionary",
    r"telecoms?|telecommunications|media|communication services": "Communication Services",
}

REGIONS: dict[str, tuple[str, ...]] = {
    r"united kingdom|uk|british|britain": ("UK",),
    r"north america|united states|usa|us|america|american": ("North America",),
    r"europe|european": ("Europe ex UK",),
    r"japan|japanese": ("Japan",),
    r"asia pacific|developed asia": ("Developed Asia Pacific",),
    r"china|chinese|india|indian|emerging asia": ("Emerging Asia",),
    r"latin america|brazil": ("Latin America",),
    r"emerging markets?|em": ("Emerging Asia", "Emerging EMEA", "Latin America"),
}

ASSET_CLASSES: dict[str, str] = {
    r"multi[\s-]?asset|mixed[\s-]?assets?|balanced": "Mixed Assets",
    r"money market|cash funds?": "Money Market",
    r"bonds?|gilts?|fixed income|treasuries": "Fixed Income",
    r"property|real estate": "Property",
    r"equit(?:y|ies)|shares|stocks|stock market": "Equity",
}

# IA sectors that can be negated ("not commodities"). Only where the word names the
# sector itself; "not tech" stays a GICS exposure exclusion.
IA_SECTORS: dict[str, str] = {
    r"commodit(?:y|ies)|natural resources": "Commodities and Natural Resources",
    # "not gilts" rules out gilt funds, not every bond fund.
    r"(?:uk\s+)?gilts?|government bonds?": "UK Gilts",
    r"corporate bonds?": "£ Corporate Bond",
}

ASSET_LABEL = {
    "Equity": "share (equity) funds",
    "Fixed Income": "bond funds",
    "Mixed Assets": "mixed-asset funds",
    "Property": "property funds",
    "Money Market": "money market funds",
}

SECTOR_LABEL = {"Information Technology": "technology"}

PASSIVE = re.compile(
    r"\b(?:index(?![\s-]linked)(?:\s+funds?|\s+trackers?)?|trackers?|passive(?:ly managed)?"
    r"|(?:tracks?|tracking|follows?|following)\s+(?:the\s+)?(?:[\w&\s-]{0,30}?)"
    r"(?:index|market))\b",
    re.IGNORECASE,
)
ACTIVE = re.compile(
    r"\b(?:actively[\s-]managed|active(?:\s+funds?)?|stock[\s-]?pick(?:ers?|ing))\b",
    re.IGNORECASE,
)

_NUM = r"(\d+(?:\.\d+)?)"
_UNIT = r"(%|\s*percent|\s*per\s*cent|\s*bps|\s*basis\s+points)"
_CMP = (
    r"(?:under|below|less\s+than|lower\s+than|cheaper\s+than|at\s+most|no\s+more\s+than"
    r"|up\s+to|max(?:imum)?(?:\s+of)?|<=?|≤)"
)
_COST_WORD = r"(?:ocf|fees?|charges?|costs?|costing|ongoing\s+charges?)"
_PER_YEAR = (
    r"(?:\s+(?:a|per)\s+year|\s+p\.?\s?a\.?|\s+annually|\s+(?:in\s+)?(?:fees|charges|costs?))?"
)

# "under 0.2%", "fees below 30bps", "OCF under 0.25" (unitless only after a cost word)
COST_CAP = re.compile(
    rf"(?:(?P<pre>{_COST_WORD})\s+(?:of\s+)?)?{_CMP}\s*{_NUM}{_UNIT}?{_PER_YEAR}",
    re.IGNORECASE,
)


def _alternation(patterns: dict) -> str:
    return "|".join(f"(?:{p})" for p in patterns)


# IA sectors first, so "not UK gilts" is the gilts sector rather than "not UK".
# "not index-linked" isn't about trackers.
_TERM = (
    rf"(?:{_alternation(IA_SECTORS)}|{_alternation(SECTORS)}|{_alternation(REGIONS)}"
    rf"|{_alternation(ASSET_CLASSES)}"
    r"|index(?![\s-]linked)|trackers?|passive|active(?:ly[\s-]managed)?)"
)
_SUFFIX = r"(?:\s+(?:funds?|stocks?|shares|companies|sectors?|exposure|names|heavy|focused))?"
# Words right after a number that make it an allocation, not a cost: "50% in shares",
# "20% of the fund". "0.1% in S&P" is still a cost: an index name isn't something you
# hold a share *in* this sense.
_ALLOCATION_AFTER = re.compile(
    rf"^\s*(?:(?:in|of)\s+(?:the\s+)?(?:{_alternation(ASSET_CLASSES)}|fund|portfolio|assets?"
    r"|cash)\b|shares|equit|bonds?|exposure|allocation)",
    re.IGNORECASE,
)
# "1% in tech", "2% in the US" are allocations too, but below 1% a sector or region
# is what the fund invests in: "under 0.2% in tech or healthcare" is a cost cap.
_PLACE_AFTER = re.compile(
    rf"^\s*(?:in|of)\s+(?:the\s+)?(?:{_alternation(SECTORS)}|{_alternation(REGIONS)})\b",
    re.IGNORECASE,
)
MIN_PLACE_ALLOCATION = 1.0
_APOS = r"['’]"
NEGATION = re.compile(
    rf"(?:\b(?:but|and)\s+)?\b(?:not|no|excluding|exclude|except(?:\s+for)?|without"
    rf"|avoid(?:ing)?|outside|ex|non|neither|(?:anything|everything)\s+but|other\s+than"
    rf"|(?:apart|aside)\s+from|nothing\s+(?:with|in)|not\s+(?:heavy|overweight|concentrated)\s+in"
    rf"|(?:does|do)(?:n{_APOS}?t|\s+not)\s+(?:invest|hold)(?:\s+in)?)"
    rf"(?:\s+(?:the|any|an?|in)){{0,2}}[\s-]+(?P<terms>{_TERM}{_SUFFIX}"
    rf"(?:\s*(?:,|or|and|nor|/)\s*(?:{_TERM}){_SUFFIX})*)\b",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ results


class Understood(BaseModel):
    """One inference, for display. `key` is what clients pass back in `ignore`."""

    key: str
    label: str


@dataclass
class Exclusions:
    """Filters applied after the search (the indexes can't pre-filter on these):
    drop funds *mainly* in these sectors or regions, and, if `tracked_indexes`
    is set, funds that don't track one of those indexes."""

    sectors: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    tracked_indexes: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.sectors or self.regions or self.tracked_indexes)

    def excludes(
        self,
        sector_weights: dict[str, float],
        region_weights: dict[str, float],
        tracked_index: str | None = None,
    ) -> bool:
        if self.tracked_indexes and tracked_index not in self.tracked_indexes:
            return True
        if any(sector_weights.get(s, 0.0) >= MAINLY for s in self.sectors):
            return True
        return any(
            sum(region_weights.get(r, 0.0) for r in group) >= MAINLY
            for group in _region_groups(self.regions)
        )


@dataclass
class Plan:
    """Everything /search needs: embedded text, merged filters, exclusions, report."""

    text: str
    filters: Filters
    exclusions: Exclusions
    applied: list[Understood]


def _region_groups(names: list[str]) -> list[tuple[str, ...]]:
    # Excluded region names are stored joined with "+" for multi-region terms (EM).
    return [tuple(n.split("+")) for n in names]


def _lookup(term: str, table: dict) -> object | None:
    for pattern, value in table.items():
        if re.fullmatch(pattern, term, re.IGNORECASE):
            return value
    return None


def _split_terms(terms: str) -> list[str]:
    parts = re.split(r"\s*(?:,|\bor\b|\band\b|\bnor\b|/)\s*", terms, flags=re.IGNORECASE)
    out = []
    for p in parts:
        p = re.sub(rf"{_SUFFIX}$", "", p.strip(), flags=re.IGNORECASE).strip()
        if p:
            out.append(p)
    return out


def _or_with_other(text: str, named: set[str]) -> set[str]:
    """Asset classes offered as one alternative to something outside that class:
    "income from bonds or dividends" isn't "bonds only". "bonds or gilts" and
    "UK or European equity" (the class word qualifies both) still are."""
    out = set()
    for m in re.finditer(r"((?:[\w-]+\s+)?[\w-]+)\s+or\s+([\w-]+(?:\s+[\w-]+)?)", text, re.I):
        left, right = m.group(1), m.group(2)
        for asset in named:
            patterns = _class_patterns(asset)
            ends_left = any(re.search(rf"\b(?:{p})$", left, re.I) for p in patterns)
            starts_right = any(re.match(rf"(?:{p})\b", right, re.I) for p in patterns)
            if ends_left != starts_right:
                out.add(asset)
    return out


def _class_patterns(asset: str) -> list[str]:
    """Words for an asset class, including IA sectors that are kinds of it ("gilts")."""
    return [p for p, a in ASSET_CLASSES.items() if a == asset] + [
        p for p, s in IA_SECTORS.items() if s in _IA_SECTOR_CLASS.get(asset, ())
    ]


# IA sectors whose names are also kinds of an asset class ("gilts" are bonds).
_IA_SECTOR_CLASS = {"Fixed Income": ("UK Gilts", "£ Corporate Bond")}


def _fmt_pct(v: float) -> str:
    return f"{v:.2f}%"


def _found(pattern: str, text: str) -> bool:
    return re.search(rf"\b(?:{pattern})\b", text, re.IGNORECASE) is not None


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    # Connectors left dangling at either end ("global equity but", "with fees").
    dangling = r"(?:but|and|with|or|in|of|that|which|is|are|has|have|fees?|charges?|costs?|ocf|,)"
    for _ in range(3):
        text = re.sub(rf"^\s*{dangling}\b\s*|\s*\b{dangling}\s*[,.]?\s*$", "", text, flags=re.I)
    return text.strip(" ,.;:-")


# ------------------------------------------------------------------ main entry


def interpret(q: str) -> tuple[str, Filters, Exclusions, list[Understood]]:
    """Read q. Returns (text to embed, inferred filters, exclusions, what was understood)."""
    text = q
    filters = Filters()
    exclusions = Exclusions()
    applied: list[Understood] = []
    excluded_assets: list[str] = []
    excluded_ia_sectors: list[str] = []
    negated_type: set[bool] = set()  # is_passive values implied by "not active" etc.

    # 1. Negations first, so "not an index fund" isn't read as "index fund".
    for m in list(NEGATION.finditer(q)):
        took = False
        terms, phrase = m.group("terms"), m.group(0)
        # A comma only continues the list when a conjunction closes it ("tech, banks
        # or energy"); otherwise it starts a new clause ("not an index fund, japan").
        # "neither tech nor banks, UK": the conjunction must come after the comma.
        while "," in terms and not re.search(r"\b(?:or|and|nor)\b", terms.rsplit(",", 1)[1], re.I):
            terms = terms.rsplit(",", 1)[0]
            phrase = phrase[: m.start("terms") - m.start() + len(terms)]
        for term in _split_terms(terms):
            if re.fullmatch(r"index|trackers?|passive", term, re.I):
                negated_type.add(False)
                took = True
            elif re.fullmatch(r"active(?:ly[\s-]managed)?", term, re.I):
                negated_type.add(True)
                took = True
            elif ia_sector := _lookup(term, IA_SECTORS):
                excluded_ia_sectors.append(ia_sector)
                took = True
            elif (asset := _lookup(term, ASSET_CLASSES)) and not _lookup(term, SECTORS):
                excluded_assets.append(asset)
                took = True
            elif sector := _lookup(term, SECTORS):
                exclusions.sectors.append(sector)
                took = True
            elif regions := _lookup(term, REGIONS):
                exclusions.regions.append("+".join(regions))
                took = True
        if took:
            text = text.replace(phrase, " ")

    # 2. Cost cap.
    for m in COST_CAP.finditer(text):
        value = float(m.group(2))
        unit = (m.group(3) or "").strip().lower()
        if unit in ("bps", "basis points") or unit.startswith("basis"):
            value /= 100
        elif not unit and not m.group("pre"):
            continue  # a bare number with no % and no cost word: not a cost
        after = text[m.end() :]
        if _ALLOCATION_AFTER.match(after) or (
            value >= MIN_PLACE_ALLOCATION and _PLACE_AFTER.match(after)
        ):
            continue
        if not 0 < value <= MAX_OCF or (value > MAX_PLAUSIBLE_OCF and not m.group("pre")):
            continue
        filters.ocf_max = value
        applied.append(Understood(key="ocf_max", label=f"Annual cost {_fmt_pct(value)} or less"))
        text = text.replace(m.group(0), " ")
        break

    # 3. Fund type. "Not index funds, not active" contradicts itself: apply neither.
    if negated_type:
        filters.is_passive = negated_type.pop() if len(negated_type) == 1 else None
    else:
        passive, active = PASSIVE.search(text), ACTIVE.search(text)
        if passive and not active:
            filters.is_passive = True
        elif active and not passive:
            filters.is_passive = False
    if filters.is_passive is not None:
        label = "Index funds only" if filters.is_passive else "Actively managed only"
        applied.append(Understood(key="is_passive", label=label))

    # 4. Asset class: only when exactly one is named. "Mixed" wins, since
    # multi-asset descriptions also mention shares and bonds.
    named = {a for p, a in ASSET_CLASSES.items() if _found(p, text)}
    if _found(r"\d+\s*%\s*(?:in\s+)?(?:shares|equit(?:y|ies)|stocks|bonds?)", text):
        named.add("Mixed Assets")  # "60% in shares" describes a mix
    if "Mixed Assets" in named:
        named = {"Mixed Assets"}
    if "Property" in named and _found(r"property shares|real estate shares|reits?", text):
        named.discard("Equity")
    named -= set(excluded_assets)
    named -= _or_with_other(text, named)
    if len(named) == 1:
        asset = named.pop()
        filters.asset_class = asset
        applied.append(Understood(key="asset_class", label=f"Only {ASSET_LABEL[asset]}"))

    for asset in dict.fromkeys(excluded_assets):
        applied.append(Understood(key=f"not_asset:{asset}", label=f"No {ASSET_LABEL[asset]}"))
    filters.asset_class_nin = list(dict.fromkeys(excluded_assets)) or None
    for sector in dict.fromkeys(excluded_ia_sectors):
        applied.append(Understood(key=f"not_ia_sector:{sector}", label=f"No {sector} funds"))
    filters.ia_sector_nin = list(dict.fromkeys(excluded_ia_sectors)) or None
    for s in dict.fromkeys(exclusions.sectors):
        name = SECTOR_LABEL.get(s, s.lower())
        applied.append(Understood(key=f"not_sector:{s}", label=f"Not mainly {name}"))
    for r in dict.fromkeys(exclusions.regions):
        name = "emerging markets" if "+" in r else r
        applied.append(Understood(key=f"not_region:{r}", label=f"Not mainly {name}"))

    cleaned = _tidy(text)
    # Nothing descriptive left ("under 0.1%", "excluding tech"): the filters do the
    # work, and a neutral text ranks the rest. Re-embedding q would undo a negation.
    if not re.search(r"[a-z]{2}", cleaned, re.I):
        cleaned = NEUTRAL_TEXT
    return cleaned, filters, exclusions, applied


def plan(q: str, explicit: Filters, ignore: set[str] | frozenset[str] = frozenset()) -> Plan:
    """Merge what q implies with the filters the user set (see `merge`)."""
    return merge(*interpret(q), explicit=explicit, ignore=ignore)


def merge(
    text: str,
    inferred: Filters,
    exclusions: Exclusions,
    applied: list[Understood],
    *,
    explicit: Filters,
    ignore: set[str] | frozenset[str] = frozenset(),
) -> Plan:
    """Combine an interpretation (rules or LLM) with the filters the user set.
    Explicit filters win, and anything in `ignore` (keys from a previous
    response) is dropped."""
    keep = []
    merged = explicit.model_copy()
    for item in applied:
        if item.key in ignore:
            continue
        kind, _, value = item.key.partition(":")
        if kind in ("ocf_max", "is_passive", "asset_class", "ia_sector"):
            if getattr(explicit, kind) is not None:
                continue  # the user's own filter wins
            setattr(merged, kind, getattr(inferred, kind))
        elif kind == "not_asset":
            if explicit.asset_class == value:
                continue
            merged.asset_class_nin = [*(merged.asset_class_nin or []), value]
        elif kind == "not_ia_sector":
            if explicit.ia_sector == value:
                continue
            merged.ia_sector_nin = [*(merged.ia_sector_nin or []), value]
        keep.append(item)
    kept = {i.key for i in keep}
    final_exclusions = Exclusions(
        sectors=[s for s in exclusions.sectors if f"not_sector:{s}" in kept],
        regions=[r for r in exclusions.regions if f"not_region:{r}" in kept],
        tracked_indexes=[i for i in exclusions.tracked_indexes if f"tracks:{i}" in kept],
    )
    return Plan(text=text, filters=merged, exclusions=final_exclusions, applied=keep)
