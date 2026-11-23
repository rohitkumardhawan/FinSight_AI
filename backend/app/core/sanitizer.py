"""
FinSight AI — Float & JSON Sanitizer Utility
Recursively cleans NaN, Inf, and -Inf values to None before JSON serialization,
ensuring RFC 8259 compliance and preventing browser JSON.parse crashes.
"""

import math
from typing import Any
from pydantic import BaseModel


def sanitize_floats(obj: Any) -> Any:
    """
    Recursively replaces NaN, Inf, and -Inf in dicts, lists, tuples,
    floats, and Pydantic models with None.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_floats(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_floats(v) for v in obj)
    elif isinstance(obj, BaseModel):
        return sanitize_floats(obj.model_dump())
    return obj
