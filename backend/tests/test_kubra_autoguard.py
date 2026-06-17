import importlib.util
import unittest
from pathlib import Path


def _load_pipeline_module():
    module_path = Path(__file__).resolve().parents[3] / "scripts" / "kubra_product_pipeline.py"
    spec = importlib.util.spec_from_file_location("kubra_product_pipeline", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


kp = _load_pipeline_module()


class KubraAutoguardTests(unittest.TestCase):
    def test_source_contract_rejects_unknown_source(self):
        with self.assertRaises(ValueError):
            kp.validate_radar_contract([
                {"source": "trends", "category": "tech", "region": "global", "limit": 10}
            ])

    def test_analysis_gate_fail_closed_without_summary(self):
        cfg = {
            "min_summary_length": 60,
            "min_keyword_count": 2,
        }
        ok, reason = kp.analysis_passes_quality_gate(
            "OpenAI launched GPT-5 API",
            {
                "is_relevant": True,
                "focus_tags": ["ai_product"],
                "score": 80,
                "summary": "kısa",
                "keywords": ["openai", "api"],
                "category": "AI",
            },
            cfg,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "summary_too_short")

    def test_shadow_gate_blocks_when_irrelevant_ratio_high(self):
        cfg = {
            "autoguard_min_sample": 8,
            "autoguard_max_irrelevant_ratio": 0.65,
            "autoguard_max_llm_failed_ratio": 0.45,
        }
        snapshot = {
            "analyzed": 12,
            "shadowed": 3,
            "irrelevant_ratio": 0.75,
            "llm_failed_ratio": 0.10,
        }
        ok, reason = kp.evaluate_shadow_gate(snapshot, cfg)
        self.assertFalse(ok)
        self.assertIn("irrelevant_ratio_high", reason)

    def test_shadow_gate_allows_clean_batch(self):
        cfg = {
            "autoguard_min_sample": 8,
            "autoguard_max_irrelevant_ratio": 0.65,
            "autoguard_max_llm_failed_ratio": 0.45,
        }
        snapshot = {
            "analyzed": 10,
            "shadowed": 4,
            "irrelevant_ratio": 0.40,
            "llm_failed_ratio": 0.10,
        }
        ok, reason = kp.evaluate_shadow_gate(snapshot, cfg)
        self.assertTrue(ok)
        self.assertEqual(reason, "quality_gate_pass")


if __name__ == "__main__":
    unittest.main()
