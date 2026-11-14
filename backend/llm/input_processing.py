"""Validate and normalize user data before it is sent to an LLM.

Accepted ``data`` shapes:

Quantitative
    - list of numbers: ``[1.2, 3.4, 5]``
    - named series: ``{"temperature": [20, 21], "humidity": [40, 42]}``
    - records (rows): ``[{"site": "A", "temp": 20}, {"site": "B", "temp": 23}]``

Qualitative
    - a string: ``"Observers reported thick smoke..."``
    - a list of strings: ``["response 1", "response 2"]``

Records may mix numeric and text columns; numeric columns get statistics and
text columns get value counts.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Any

DATA_TYPES = ("auto", "quantitative", "qualitative")


class InputValidationError(ValueError):
    """The request payload is missing data or has an unsupported shape."""


@dataclass(frozen=True)
class ProcessedInput:
    data_type: str  # "quantitative" or "qualitative"
    shape: str  # "series", "named_series", "records", "text", "text_list"
    summary: dict[str, Any]
    data_text: str  # serialized data included in the prompt


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _numeric_stats(values: list[float]) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }
    stats["stdev"] = statistics.stdev(values) if len(values) >= 2 else None
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in stats.items()}


def _column_summary(values: list[Any]) -> dict[str, Any]:
    present = [v for v in values if v is not None and v != ""]
    missing = len(values) - len(present)
    if present and all(_is_number(v) for v in present):
        summary = {"kind": "numeric", **_numeric_stats([float(v) for v in present])}
    else:
        counts = Counter(str(v) for v in present)
        summary = {
            "kind": "categorical",
            "count": len(present),
            "unique": len(counts),
            "top_values": [{"value": v, "count": c} for v, c in counts.most_common(5)],
        }
    summary["missing"] = missing
    return summary


def _summarize_series(data: list[Any]) -> dict[str, Any]:
    if not all(_is_number(v) for v in data):
        raise InputValidationError("Quantitative lists must contain only finite numbers.")
    return {"series": _numeric_stats([float(v) for v in data])}


def _summarize_named_series(data: dict[str, Any]) -> dict[str, Any]:
    columns: dict[str, Any] = {}
    for name, values in data.items():
        if not isinstance(values, list) or not values:
            raise InputValidationError(f"Series '{name}' must be a non-empty list.")
        columns[str(name)] = _column_summary(values)
    return {"columns": columns}


def _summarize_records(data: list[dict[str, Any]]) -> dict[str, Any]:
    keys: list[str] = []
    for row in data:
        for key in row:
            if key not in keys:
                keys.append(key)
    columns = {str(k): _column_summary([row.get(k) for row in data]) for k in keys}
    return {"row_count": len(data), "columns": columns}


def _detect(data: Any) -> tuple[str, str]:
    """Return (data_type, shape) for a payload."""
    if isinstance(data, str):
        return "qualitative", "text"
    if isinstance(data, dict):
        return "quantitative", "named_series"
    if isinstance(data, list):
        if all(isinstance(v, str) for v in data):
            return "qualitative", "text_list"
        if all(isinstance(v, dict) for v in data):
            return "quantitative", "records"
        if all(_is_number(v) for v in data):
            return "quantitative", "series"
    raise InputValidationError(
        "Unsupported data shape. Send a string, a list of strings, a list of numbers, "
        "an object of named number lists, or a list of row objects."
    )


def process_input(data: Any, data_type: str = "auto", *, max_chars: int = 50_000) -> ProcessedInput:
    if data is None or data == "" or data == [] or data == {}:
        raise InputValidationError("'data' is required and must not be empty.")
    if data_type not in DATA_TYPES:
        raise InputValidationError(f"'data_type' must be one of: {', '.join(DATA_TYPES)}.")

    detected_type, shape = _detect(data)
    if data_type != "auto" and data_type != detected_type:
        raise InputValidationError(
            f"'data_type' is '{data_type}' but the data looks {detected_type}."
        )

    if shape == "series":
        summary = _summarize_series(data)
    elif shape == "named_series":
        summary = _summarize_named_series(data)
    elif shape == "records":
        summary = _summarize_records(data)
    elif shape == "text":
        summary = {"characters": len(data), "words": len(data.split())}
    else:  # text_list
        summary = {
            "entries": len(data),
            "total_characters": sum(len(s) for s in data),
        }

    if shape == "text":
        data_text = data
    elif shape == "text_list":
        data_text = "\n".join(f"{i}. {s}" for i, s in enumerate(data, start=1))
    else:
        data_text = json.dumps(data, ensure_ascii=False, default=str)

    if len(data_text) > max_chars:
        raise InputValidationError(
            f"Data is {len(data_text):,} characters, over the {max_chars:,} character limit. "
            "Send a smaller subset or pre-aggregate it."
        )

    return ProcessedInput(data_type=detected_type, shape=shape, summary=summary, data_text=data_text)
