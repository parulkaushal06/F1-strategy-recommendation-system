"""Unit tests for src/features/probability.py (field normalisation helpers)."""
import numpy as np
import pytest

from src.features.probability import (
    normalize_counterfactual_probability,
    normalize_field_percentages,
    normalize_field_probabilities,
)


def test_probabilities_sum_to_one():
    result = normalize_field_probabilities([0.2, 0.3, 0.1])
    assert result.sum() == pytest.approx(1.0)
    assert result == pytest.approx([1 / 3, 0.5, 1 / 6])


def test_already_normalised_input_is_unchanged():
    values = np.array([0.5, 0.3, 0.2])
    assert normalize_field_probabilities(values) == pytest.approx(values)


def test_all_zero_field_becomes_uniform():
    assert normalize_field_probabilities([0, 0, 0, 0]) == pytest.approx([0.25] * 4)


def test_empty_field_stays_empty():
    assert normalize_field_probabilities([]).size == 0
    assert normalize_field_percentages([]).size == 0


@pytest.mark.parametrize("bad", [[0.2, -0.1], [0.2, np.nan], [0.2, np.inf]])
def test_invalid_values_are_rejected_not_hidden(bad):
    with pytest.raises(ValueError):
        normalize_field_probabilities(bad)


def test_two_dimensional_input_is_rejected():
    with pytest.raises(ValueError):
        normalize_field_probabilities([[0.1, 0.2], [0.3, 0.4]])


@pytest.mark.parametrize("raw", [
    [1 / 3, 1 / 3, 1 / 3],
    [0.123456, 0.654321, 0.222223, 0.000001],
    [0.9, 0.05, 0.03, 0.01, 0.01],
    [0.7, 0.7, 0.7],
])
def test_percentages_total_exactly_100(raw):
    percentages = normalize_field_percentages(raw)
    assert round(float(percentages.sum()), 2) == 100.0


def test_percentages_keep_driver_order():
    percentages = normalize_field_percentages([0.1, 0.6, 0.3])
    assert list(np.argsort(-percentages)) == [1, 2, 0]


def test_counterfactual_matches_hand_calculation():
    field = [0.4, 0.3, 0.3]
    # driver 0 simulated at 0.8 while the others stay at 0.3 each: 0.8 / (0.8 + 0.6)
    assert normalize_counterfactual_probability(0.8, field, 0) == pytest.approx(0.8 / 1.4)


def test_counterfactual_with_unchanged_score_matches_field_normalisation():
    field = [0.4, 0.3, 0.2]
    expected = normalize_field_probabilities(field)[1]
    assert normalize_counterfactual_probability(0.3, field, 1) == pytest.approx(expected)


def test_counterfactual_better_score_raises_probability():
    field = [0.4, 0.3, 0.2]
    base = normalize_counterfactual_probability(0.4, field, 0)
    better = normalize_counterfactual_probability(0.6, field, 0)
    assert better > base


def test_counterfactual_zero_field_falls_back_to_uniform():
    assert normalize_counterfactual_probability(0.0, [0.0, 0.0, 0.0, 0.0], 2) == pytest.approx(0.25)


def test_counterfactual_rejects_bad_inputs():
    with pytest.raises(IndexError):
        normalize_counterfactual_probability(0.5, [0.2, 0.3], 5)
    with pytest.raises(ValueError):
        normalize_counterfactual_probability(-0.1, [0.2, 0.3], 0)
    with pytest.raises(ValueError):
        normalize_counterfactual_probability(0.1, [], 0)