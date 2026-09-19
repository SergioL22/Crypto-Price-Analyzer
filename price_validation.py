"""Numeric validation shared by CLI evidence and HTTP analysis services."""
import math
from numbers import Real


class PriceValidationError(ValueError):
    pass


def finite_number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PriceValidationError(f'{label} must be a finite number.')
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise PriceValidationError(f'{label} must be a finite' + (' positive' if positive else '') + ' number.')
    return result


def validate_prices(frame):
    """Copy and validate observations; never coerce strings into market prices."""
    frame = frame.copy(deep=True)
    frame['price'] = [finite_number(v, 'Historical price', positive=True) for v in frame['price']]
    return frame
