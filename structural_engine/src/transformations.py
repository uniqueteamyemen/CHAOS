from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DerivedValue:
    variable_id: str
    timestamp: str
    value: float
    transformation: str
    source_observation_refs: tuple[str, ...]
    notes: str = ""


def real_value_from_cpi(
    *,
    nominal_value: float,
    cpi_at_observation: float,
    cpi_at_base: float,
    variable_id: str,
    timestamp: str,
    nominal_ref: str,
    cpi_ref: str,
) -> DerivedValue:
    if cpi_at_observation <= 0 or cpi_at_base <= 0:
        raise ValueError("CPI values must be positive; no value was derived")
    value = nominal_value * cpi_at_base / cpi_at_observation
    return DerivedValue(
        variable_id=variable_id,
        timestamp=timestamp,
        value=value,
        transformation="real_value_using_explicit_cpi_base",
        source_observation_refs=(nominal_ref, cpi_ref),
        notes="Derived value; never replaces nominal or CPI observations",
    )


def zscore_observed(values: Sequence[float], *, variable_id: str, timestamps: Sequence[str], refs: Sequence[str]) -> list[DerivedValue]:
    if len(values) != len(timestamps) or len(values) != len(refs):
        raise ValueError("values, timestamps, and refs must have equal lengths")
    if not values:
        return []
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = variance ** 0.5
    if std == 0:
        raise ValueError("constant observed series has no defined z-score")
    return [
        DerivedValue(
            variable_id=variable_id,
            timestamp=timestamp,
            value=(value - mean) / std,
            transformation="observed_series_zscore",
            source_observation_refs=(ref,),
            notes="Derived from observed values only; no missing values filled",
        )
        for value, timestamp, ref in zip(values, timestamps, refs)
    ]


def assert_raw_payload_untouched(raw_bytes_before: bytes, raw_bytes_after: bytes) -> None:
    if raw_bytes_before != raw_bytes_after:
        raise AssertionError("raw payload changed during derived transformation")
