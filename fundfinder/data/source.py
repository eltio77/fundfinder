from typing import Protocol

from fundfinder.models import Fund


class FundSource(Protocol):
    """Anything that can supply the fund universe. The synthetic generator is one
    implementation; a real data API client should be another."""

    def fetch(self) -> list[Fund]: ...
