import json
import math
from datetime import date, datetime
from decimal import Decimal

import numpy as np


def clean(o):
    """Make DB/numpy values JSON-safe (NaN -> None, Decimal -> float, dates -> ISO)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [clean(v) for v in o]
    if isinstance(o, str) and o[:1] in "[{" and False:
        return o
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def jl(v):
    return json.loads(v) if isinstance(v, str) else v
