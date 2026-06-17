import unittest

from routes.trends import _passes_trend_relevance_guard
from services.trend_relevance import is_kubra_relevant_text


class TrendRelevanceGuardTests(unittest.TestCase):
    def test_keyword_boundary_regression_dubai_is_not_ai(self):
        self.assertFalse(is_kubra_relevant_text("Dubai Uluslararası Havalimanı"))

    def test_ai_model_release_is_relevant(self):
        self.assertTrue(is_kubra_relevant_text("OpenAI released GPT-5 model"))

    def test_route_guard_filters_irrelevant_kubra_row(self):
        trend = {
            "source_type": "kubra_pipeline",
            "topic": "Dubai Uluslararası Havalimanı",
            "summary": "Yeni terminal açılışı duyuruldu",
            "keywords": ["dubai", "travel"],
        }
        self.assertFalse(_passes_trend_relevance_guard(trend))

    def test_route_guard_fail_closed_without_analysis_artifact(self):
        trend = {
            "source_type": "kubra_pipeline",
            "topic": "Anthropic launched Claude Code SDK",
            "summary": "Yeni AI product release ve developer API erişimi açıklandı",
            "keywords": ["ai", "sdk", "api"],
            "raw_content": "{}",
        }
        self.assertFalse(_passes_trend_relevance_guard(trend))

    def test_route_guard_keeps_relevant_kubra_row(self):
        trend = {
            "source_type": "kubra_pipeline",
            "topic": "Anthropic launched Claude Code SDK",
            "summary": "Yeni AI product release ve developer API erişimi açıklandı",
            "keywords": ["ai", "sdk", "api"],
            "raw_content": {
                "kubra_analysis": {
                    "score": 82,
                    "focus_tags": ["api_release", "ai_product"],
                }
            },
        }
        self.assertTrue(_passes_trend_relevance_guard(trend))


if __name__ == "__main__":
    unittest.main()
