def allocate_demand(total_rate: int, ratio: str) -> tuple[int, int]:
    """Split total demand using a ``main:side`` integer ratio."""
    try:
        main_weight, side_weight = (int(value) for value in ratio.split(":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid demand ratio: {ratio!r}") from exc
    if total_rate < 0 or main_weight <= 0 or side_weight <= 0:
        raise ValueError("Total demand must be non-negative and ratio weights must be positive.")
    main_rate = round(total_rate * main_weight / (main_weight + side_weight))
    return main_rate, total_rate - main_rate
