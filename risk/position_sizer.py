"""Position sizing — never risk more than risk_pct of account on a single trade."""


def calculate_position_size(
    account_equity: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = 0.01,
) -> float:
    """
    Returns number of shares/units to buy.

    Max loss = (entry - stop) × units = account × risk_pct
    """
    max_loss = account_equity * risk_pct
    risk_per_unit = abs(entry_price - stop_loss_price)

    if risk_per_unit == 0:
        return 0.0

    return round(max_loss / risk_per_unit, 4)
