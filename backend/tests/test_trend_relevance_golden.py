import json
import unittest
from pathlib import Path

from services.trend_relevance import is_kubra_relevant_text


class TrendRelevanceGoldenSetTests(unittest.TestCase):
    def test_golden_set(self):
        fixture_path = Path(__file__).parent / "fixtures" / "trend_relevance_golden.json"
        cases = json.loads(fixture_path.read_text())
        self.assertGreaterEqual(len(cases), 8)

        failures = []
        for case in cases:
            actual = is_kubra_relevant_text(
                topic=case.get("topic", ""),
                summary=case.get("summary", ""),
                keywords=case.get("keywords") or [],
            )
            if actual != case.get("expected"):
                failures.append((case.get("label"), case.get("expected"), actual))

        self.assertFalse(failures, f"Golden regression failed: {failures}")


if __name__ == "__main__":
    unittest.main()
