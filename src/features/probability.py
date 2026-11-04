"""Helpers for turning independent driver scores into race-field probabilities."""

import numpy as np


def normalize_field_probabilities(probabilities) -> np.ndarray:
    """Rescale one race-lap's non-negative driver probabilities to sum to 1.

    If every input is zero, return a uniform distribution across the supplied
    field. Empty inputs stay empty. Inputs must be finite and non-negative so
    data/model errors are not silently hidden by normalization.
    """
    values = np.asarray(probabilities, dtype=float)
    if values.ndim != 1:
        raise ValueError("field probabilities must be a one-dimensional array")
    if values.size == 0:
        return values.copy()
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("field probabilities must be finite and non-negative")

    total = values.sum()
    if total == 0:
        return np.full(values.size, 1.0 / values.size)
    return values / total


def normalize_field_percentages(probabilities, decimals: int = 2) -> np.ndarray:
    """Return percentages rounded to ``decimals`` that total exactly 100."""
    normalized = normalize_field_probabilities(probabilities)
    if normalized.size == 0:
        return normalized.copy()
    percentages = np.round(normalized * 100, decimals)
    remainder = round(100.0 - float(percentages.sum()), decimals)
    percentages[int(np.argmax(percentages))] = round(
        percentages[int(np.argmax(percentages))] + remainder, decimals
    )
    return percentages


def normalize_counterfactual_probability(simulated_probability, field_probabilities, driver_index):
    """Normalize one driver's simulated score while holding others at baseline.

    This provides a comparable field-scale estimate for a one-driver what-if;
    it does not model how the action would alter opponents' race states.
    """
    values = np.asarray(field_probabilities, dtype=float)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("field probabilities must be a non-empty one-dimensional array")
    if not 0 <= driver_index < values.size:
        raise IndexError("driver_index is outside the field probability array")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("field probabilities must be finite and non-negative")
    if not np.isfinite(simulated_probability) or simulated_probability < 0:
        raise ValueError("simulated probability must be finite and non-negative")

    other_total = values.sum() - values[driver_index]
    denominator = other_total + simulated_probability
    if denominator == 0:
        return 1.0 / values.size
    return float(simulated_probability / denominator)
