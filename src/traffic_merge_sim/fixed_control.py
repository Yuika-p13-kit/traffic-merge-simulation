from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FixedRatioController:
    """Allocate merge access by completed main/side vehicle passages."""

    main_quota: int
    side_quota: int
    active: str = "main"
    served: int = 0

    def __post_init__(self) -> None:
        if self.main_quota <= 0 or self.side_quota <= 0:
            raise ValueError("Fixed-ratio quotas must be positive.")

    @property
    def signal_state(self) -> str:
        # TLS link 0 is side_in -> out; link 1 is main_in -> out.
        return "rG" if self.active == "main" else "Gr"

    def update(self, passed_approach: str | None, main_present: bool, side_present: bool) -> str:
        if passed_approach == self.active:
            self.served += 1

        quota = self.main_quota if self.active == "main" else self.side_quota
        other_present = side_present if self.active == "main" else main_present
        active_present = main_present if self.active == "main" else side_present
        if other_present and (self.served >= quota or not active_present):
            self.active = "side" if self.active == "main" else "main"
            self.served = 0
        return self.signal_state


def parse_strategy(strategy: str) -> tuple[int, int]:
    try:
        main_quota, side_quota = (int(value) for value in strategy.split(":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid fixed-control strategy: {strategy!r}") from exc
    if main_quota <= 0 or side_quota <= 0:
        raise ValueError("Fixed-control ratios must contain positive integers.")
    return main_quota, side_quota
