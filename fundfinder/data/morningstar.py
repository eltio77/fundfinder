"""Real UK funds from Morningstar's public list and snapshot APIs.

The security list (28K securities over ~29 pages) is filtered to Open Ended
Investment Companies with an IA sector; each fund's snapshot, fetched by SEDOL,
is then mapped onto `Fund`. Share classes of the same fund collapse to the first
one seen, and the pick is spread round-robin across IA sectors so a capped run
isn't dominated by whichever sectors sort first.

Not mapped exactly: Morningstar's 11 equity sectors stand in for GICS sectors
(same split under different names), regions are Morningstar's regional exposure,
and "passive" is read from the fund name (index, tracker, ETF), since the snapshot
has no index flag.
"""

import json
import random
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fundfinder.models import Fund, Holding

BASE = "https://lt.morningstar.com/api/rest.svc"
UNIVERSE = "1c6qh1t6k9"
LIST_URL = f"{BASE}/security_list/{UNIVERSE}/?outputtype=xml&pageSize={{size}}&pageno={{page}}"
DETAIL_URL = (
    f"{BASE}/{UNIVERSE}/security_details/{{sedol}}"
    "?viewId=snapshot&responseViewFormat=json&idType=sedol"
)
OEIC = "Open Ended Investment Company"
PAGE_SIZE = 1000
DEFAULT_LIMIT = 300
DEFAULT_SEED = 42
TIMEOUT_S = 30
WORKERS = 8
# The list API sometimes answers a valid page with "No securities found"; retry those.
RETRIES = 3
RETRY_WAIT_S = 2.0

# Morningstar global equity sector codes -> the GICS sector it corresponds to.
SECTORS = {
    "101": "Materials",
    "102": "Consumer Discretionary",
    "103": "Financials",
    "104": "Real Estate",
    "205": "Consumer Staples",
    "206": "Health Care",
    "207": "Utilities",
    "308": "Communication Services",
    "309": "Energy",
    "310": "Industrials",
    "311": "Information Technology",
}

# Morningstar regional exposure codes (14/15 are emerging/developed totals, 16 unclassified).
REGIONS = {
    "1": "North America",  # United States
    "2": "North America",  # Canada
    "3": "Latin America",
    "4": "UK",
    "5": "Europe ex UK",  # Eurozone
    "6": "Europe ex UK",  # Europe ex Euro
    "7": "Emerging EMEA",  # Europe emerging
    "8": "Emerging EMEA",  # Africa
    "9": "Emerging EMEA",  # Middle East
    "10": "Japan",
    "11": "Developed Asia Pacific",  # Australasia
    "12": "Developed Asia Pacific",  # Asia developed
    "13": "Emerging Asia",
}

# Bond country exposure has no regional roll-up, so map the usual issuers.
# Countries not listed here are left out and the rest rescaled.
COUNTRY_REGIONS = {
    "Emerging Asia": "CHN IND IDN MYS PHL THA VNM PAK LKA BGD MNG",
    "Developed Asia Pacific": "AUS NZL SGP HKG KOR TWN",
    "Emerging EMEA": (
        "POL HUN CZE ROU BGR SRB TUR RUS UKR KAZ ZAF EGY NGA KEN MAR GHA CIV AGO SAU ARE QAT "
        "KWT OMN BHR ISR JOR"
    ),
    "Latin America": "BRA MEX CHL COL PER ARG URY PAN DOM ECU GTM SLV CRI PRY JAM",
    "Europe ex UK": (
        "DEU FRA ITA ESP NLD BEL AUT IRL PRT FIN GRC LUX CHE SWE NOR DNK ISL SVN SVK EST LVA "
        "LTU HRV CYP MLT"
    ),
    "North America": "USA CAN",
    "Japan": "JPN",
    "UK": "GBR GGY JEY IMN",
}
COUNTRY_TO_REGION = {c: r for r, codes in COUNTRY_REGIONS.items() for c in codes.split()}

# MorningStarDefault asset allocation codes.
STOCK, BOND, PREFERRED, CONVERTIBLE, CASH, OTHER = "1", "3", "5", "6", "7", "8"
# MorningstarUK6 splits out direct property, which the default buckets as "other".
UK6_PROPERTY = "6"
# Level-1 bond sectors: government, municipal, corporate, securitized (cash/derivatives ignored).
GOVT_BONDS = {"10", "20"}
CORP_BONDS = {"30", "40"}

# IA sectors whose asset class differs from Morningstar's broad category.
IA_ASSET_CLASS = {
    "Standard Money Market": "Money Market",
    "Short Term Money Market": "Money Market",
    "Direct and Hybrid Property": "Property",
    "Property Other": "Property",
    "Listed Property": "Property",
    "Commodities and Natural Resources": "Commodities",
}
BROAD_ASSET_CLASS = {
    "Equity": "Equity",
    "Fixed Income": "Fixed Income",
    "Allocation": "Mixed Assets",
    "Property": "Property",
    "Real Estate": "Property",
    "Commodities": "Commodities",
    "Money Market": "Money Market",
}

PASSIVE_NAME = re.compile(r"\b(index|tracker|etf)\b(?![- ]linked)", re.IGNORECASE)
# Fund benchmarks that are a peer group or placeholder, not an index a tracker could follow.
NOT_AN_INDEX = re.compile(r"^(IA |Morningstar |N/A|Not Benchmarked)", re.IGNORECASE)


@dataclass(frozen=True)
class Listing:
    sedol: str
    name: str
    ia_sector: str


class SkipFund(Exception):
    """The snapshot lacks something the app needs (cost, objective, portfolio)."""


def parse_list(xml: bytes) -> tuple[list[Listing], int]:
    """OEICs with a SEDOL and IA sector on one list page, plus the total page count."""
    root = ET.fromstring(xml)
    if root.tag != "Securities":
        raise ValueError(f"not a security list: {root.findtext('StatusMessage') or root.tag}")
    listings = [
        Listing(sedol, s.findtext("Name") or "", sector)
        for s in root.iter("Security")
        if s.findtext("LegalStructure") == OEIC
        and (sedol := s.findtext("SEDOL"))
        and (sector := s.findtext("IMASectorName"))
    ]
    return listings, int(root.get("TotalNumberOfPages", "1"))


def spread(listings: list[Listing], seed: int) -> list[Listing]:
    """Round-robin over IA sectors (shuffled within each) so any prefix is varied."""
    by_sector: dict[str, list[Listing]] = defaultdict(list)
    for item in listings:
        by_sector[item.ia_sector].append(item)
    rng = random.Random(seed)
    queues = []
    for sector in sorted(by_sector):
        items = by_sector[sector]
        rng.shuffle(items)
        queues.append(items)
    out = []
    for i in range(max(map(len, queues), default=0)):
        out.extend(q[i] for q in queues if i < len(q))
    return out


def _values(block: dict[str, Any] | None) -> dict[str, float]:
    if not block:
        return {}
    return {b["Type"]: float(b["Value"]) for b in block.get("BreakdownValues", [])}


def _net(portfolio: dict[str, Any], key: str, **match: str) -> dict[str, float]:
    """Net-position (long minus short) breakdown for `key`, as code -> percent."""
    for block in portfolio.get(key) or []:
        if block.get("SalePosition") == "N" and all(block.get(k) == v for k, v in match.items()):
            return _values(block)
    return {}


def _rollup(values: dict[str, float], mapping: dict[str, str]) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for code, value in values.items():
        if code in mapping and value > 0:
            out[mapping[code]] += value
    return out


def _scaled(weights: dict[str, float], scale: float) -> dict[str, float]:
    """Rescale to sum to `scale`, rounded to 4 places, dropping zeros."""
    total = sum(weights.values())
    if total <= 0 or scale <= 0:
        return {}
    out = {k: round(v / total * scale, 4) for k, v in weights.items()}
    return {k: v for k, v in sorted(out.items()) if v > 0}


def asset_mix(portfolio: dict[str, Any], asset_class: str) -> dict[str, float]:
    alloc = _net(portfolio, "AssetAllocations", Type="MorningStarDefault")
    uk6 = _net(portfolio, "AssetAllocations", Type="MorningstarUK6")
    pos = {k: max(0.0, v) for k, v in alloc.items()}
    bonds = pos.get(BOND, 0.0) + pos.get(CONVERTIBLE, 0.0)
    bond_sectors = _net(portfolio, "GlobalBondSectorBreakdownLevel1")
    govt = sum(max(0.0, bond_sectors.get(c, 0.0)) for c in GOVT_BONDS)
    corp = sum(max(0.0, bond_sectors.get(c, 0.0)) for c in CORP_BONDS)
    govt_share = govt / (govt + corp) if govt + corp > 0 else 0.5
    property_ = min(max(0.0, uk6.get(UK6_PROPERTY, 0.0)), pos.get(OTHER, 0.0))
    other = pos.get(OTHER, 0.0) - property_
    mix = {
        "Equity": pos.get(STOCK, 0.0) + pos.get(PREFERRED, 0.0),
        "Government Bonds": bonds * govt_share,
        "Corporate Bonds": bonds * (1 - govt_share),
        "Cash": pos.get(CASH, 0.0),
        "Property": property_,
        "Commodities" if asset_class == "Commodities" else "Alternatives": other,
    }
    return _scaled(mix, 1.0)


def region_mix(portfolio: dict[str, Any], assets: dict[str, float]) -> dict[str, float]:
    """Equity regions and bond issuer countries, weighted by how much of each the fund holds."""
    equity = _scaled(_rollup(_net(portfolio, "RegionalExposure"), REGIONS), 1.0)
    bond = _scaled(_rollup(_net(portfolio, "CountryExposure", Type="Bond"), COUNTRY_TO_REGION), 1.0)
    equity_w = assets.get("Equity", 0.0) if equity else 0.0
    bond_w = assets.get("Government Bonds", 0.0) + assets.get("Corporate Bonds", 0.0)
    bond_w = bond_w if bond else 0.0
    mix: dict[str, float] = defaultdict(float)
    for region, w in equity.items():
        mix[region] += w * equity_w
    for region, w in bond.items():
        mix[region] += w * bond_w
    return _scaled(mix, 1.0)


def _asset_class(detail: dict[str, Any], ia_sector: str) -> str:
    if ia_sector in IA_ASSET_CLASS:
        return IA_ASSET_CLASS[ia_sector]
    broad = (detail.get("CategoryBroadAssetClass") or {}).get("Name", "")
    return BROAD_ASSET_CLASS.get(broad, "Mixed Assets")


def _tracked_index(detail: dict[str, Any]) -> str | None:
    for bench in detail.get("FundBenchmark") or []:
        name = (bench.get("Name") or "").strip()
        if name and not NOT_AN_INDEX.match(name):
            return name
    return None


def to_fund(detail: dict[str, Any], sedol: str) -> Fund:
    """Map one snapshot onto `Fund`. Raises SkipFund when essentials are missing."""
    name = detail.get("Name") or detail.get("LegalName")
    ia_sector = (detail.get("IMASector") or {}).get("Name")
    ocf = detail.get("OngoingCharge")
    objective = (detail.get("InvestmentStrategy") or "").strip()
    portfolios = detail.get("Portfolios") or []
    if not (name and ia_sector and ocf is not None and objective and portfolios):
        raise SkipFund("missing name, IA sector, OCF, objective or portfolio")
    portfolio = portfolios[0]

    asset_class = _asset_class(detail, ia_sector)
    assets = asset_mix(portfolio, asset_class)
    if not assets:
        raise SkipFund("no asset allocation")
    sectors = _scaled(
        _rollup(_net(portfolio, "GlobalStockSectorBreakdown"), SECTORS), assets.get("Equity", 0.0)
    )
    is_passive = bool(PASSIVE_NAME.search(name))
    holdings = sorted(
        (h for h in portfolio.get("PortfolioHoldings") or [] if h.get("SecurityName")),
        key=lambda h: -float(h.get("Weighting") or 0),
    )[:10]
    return Fund(
        id=sedol,
        name=name,
        provider=(detail.get("ProviderCompany") or {}).get("Name") or "Unknown",
        ia_sector=ia_sector,
        asset_class=asset_class,
        ocf=round(float(ocf), 4),
        is_passive=is_passive,
        tracked_index=_tracked_index(detail) if is_passive else None,
        objective=objective,
        top_holdings=[
            Holding(
                name=h["SecurityName"],
                weight=round(min(1.0, max(0.0, float(h.get("Weighting") or 0) / 100)), 4),
            )
            for h in holdings
        ],
        sector_weights=sectors,
        region_weights=region_mix(portfolio, assets),
        asset_class_weights=assets,
    )


class MorningstarSource:
    """`FundSource` over the live Morningstar APIs; `limit=None` loads every fund.
    Responses can be cached on disk (`cache_dir`) so re-runs and mapping tweaks don't
    hit the API again."""

    def __init__(
        self,
        limit: int | None = DEFAULT_LIMIT,
        seed: int = DEFAULT_SEED,
        cache_dir: Path | None = None,
    ):
        self.limit = limit
        self.seed = seed
        self.cache_dir = cache_dir
        self.skipped: dict[str, str] = {}

    def _get(self, url: str, cache_name: str, check: Callable[[bytes], object]) -> bytes:
        """GET `url`, cached under `cache_name` once `check` accepts the body."""
        path = self.cache_dir / cache_name if self.cache_dir else None
        if path and path.exists():
            return path.read_bytes()
        req = urllib.request.Request(url, headers={"User-Agent": "fund-finder/0.1"})
        for attempt in range(RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                    body = resp.read()
                check(body)
                break
            except (OSError, ValueError):
                if attempt == RETRIES - 1:
                    raise
                time.sleep(RETRY_WAIT_S * (attempt + 1))
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        return body

    def listings(self) -> list[Listing]:
        """Every OEIC in the list, walking all pages."""
        page, pages, out = 1, 1, []
        while page <= pages:
            url = LIST_URL.format(size=PAGE_SIZE, page=page)
            found, pages = parse_list(self._get(url, f"list/{page}.xml", parse_list))
            out.extend(found)
            page += 1
        return out

    def _detail(self, sedol: str) -> dict[str, Any] | None:
        try:
            url = DETAIL_URL.format(sedol=sedol)
            data = json.loads(self._get(url, f"detail/{sedol}.json", json.loads))
        except (OSError, ValueError) as e:
            self.skipped[sedol] = f"fetch failed: {e}"
            return None
        if not data:
            self.skipped[sedol] = "empty snapshot"
            return None
        return data[0] if isinstance(data, list) else data

    def _details(self, listings: list[Listing]) -> Iterator[tuple[Listing, dict[str, Any] | None]]:
        # Fetch in batches so a capped run stops shortly after reaching the limit.
        with ThreadPoolExecutor(WORKERS) as pool:
            for start in range(0, len(listings), WORKERS * 4):
                batch = listings[start : start + WORKERS * 4]
                details = pool.map(lambda li: self._detail(li.sedol), batch)
                yield from zip(batch, details, strict=True)

    def fetch(self) -> list[Fund]:
        funds: list[Fund] = []
        seen_funds: set[str] = set()
        for listing, detail in self._details(spread(self.listings(), self.seed)):
            if self.limit is not None and len(funds) >= self.limit:
                break
            if detail is None:
                continue
            fund_key = detail.get("FundId") or listing.sedol
            if fund_key in seen_funds:
                continue  # another share class of a fund we already have
            try:
                fund = to_fund(detail, listing.sedol)
            except (SkipFund, ValidationError, ValueError, KeyError, TypeError) as e:
                self.skipped[listing.sedol] = str(e).splitlines()[0]
                continue
            seen_funds.add(fund_key)
            funds.append(fund)
        return funds
