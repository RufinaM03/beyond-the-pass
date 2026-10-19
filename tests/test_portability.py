"""Synthetic IEEE-754 agreement boundaries; never model performance evidence."""

import copy
import math
import unittest

from backend.app import predictions_agree


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.expected = {"status": "scored", "exploratory_prioritization_score": 10.0,
                         "recurrence_used_by_model": False,
                         "explanation": {"intercept_log_odds": -2.0, "terms": [{"feature": "mileage", "log_odds_contribution": 0.1}]}}

    def test_only_two_score_ulps_allowed_in_either_direction(self):
        for direction in [math.inf, -math.inf]:
            actual = copy.deepcopy(self.expected)
            self.assertTrue(predictions_agree(actual, self.expected))
            for step in range(1, 4):
                actual['exploratory_prioritization_score'] = math.nextafter(actual['exploratory_prioritization_score'], direction)
                self.assertEqual(predictions_agree(actual, self.expected), step <= 2)

    def test_explanations_metadata_types_and_keys_stay_exact(self):
        actual = copy.deepcopy(self.expected)
        actual['explanation']['terms'][0]['log_odds_contribution'] = math.nextafter(0.1, math.inf)
        self.assertFalse(predictions_agree(actual, self.expected))
        actual = self.expected | {'recurrence_used_by_model': 0}
        self.assertFalse(predictions_agree(actual, self.expected))
        self.assertFalse(predictions_agree(self.expected | {'unexpected': 1}, self.expected))
        self.assertFalse(predictions_agree(self.expected | {'status': 'unsupported_scope'}, self.expected))

    def test_invalid_scores_and_unscored_states(self):
        for value in [None, True, 10, '10.0', math.nan, math.inf, -1.0, 101.0]:
            self.assertFalse(predictions_agree(self.expected | {'exploratory_prioritization_score': value}, self.expected))
        unscored = {'status': 'insufficient_data', 'exploratory_prioritization_score': None}
        self.assertTrue(predictions_agree(unscored, unscored))
        self.assertFalse(predictions_agree({'status': 'insufficient_data'}, unscored))
        self.assertFalse(predictions_agree(None, unscored))
