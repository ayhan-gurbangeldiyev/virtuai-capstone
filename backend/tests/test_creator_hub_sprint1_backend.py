import unittest
from pydantic import ValidationError

from routes.profile import BrandVoice, _merge_brand_voice
from routes.settings import DefaultDraftStyle


class CreatorHubSprint1BackendTests(unittest.TestCase):
    def test_merge_brand_voice_preserves_existing_fields_when_unset(self):
        existing = {
            "tones": {
                "informative": 40,
                "friendly": 40,
                "witty": 20,
                "aggressive": 0,
                "inspirational": 0,
            },
            "principles": ["storytelling"],
            "avoid": ["emoji-spam"],
            "sample_voice": "Mevcut örnek ses korunmalı",
            "reference_tweets": ["Eski referans 1", "Eski referans 2"],
            "legacy_flag": True,
        }

        incoming = BrandVoice(
            principles=[" concise "],
            avoid=[" corporate "],
            target_audience="founders",
        )

        merged = _merge_brand_voice(existing, incoming)

        self.assertEqual(merged["principles"], ["concise"])
        self.assertEqual(merged["avoid"], ["corporate"])
        self.assertEqual(merged["target_audience"], "founders")
        self.assertEqual(merged["sample_voice"], "Mevcut örnek ses korunmalı")
        self.assertEqual(merged["reference_tweets"], ["Eski referans 1", "Eski referans 2"])
        self.assertTrue(merged["legacy_flag"])

    def test_merge_brand_voice_updates_reference_tweets_without_blanking_sample_voice(self):
        existing = {
            "sample_voice": "Bu alan sessizce boşlanmamalı",
            "reference_tweets": ["Eski referans"],
        }

        incoming = BrandVoice(reference_tweets=[" Yeni referans 1 ", "", "Yeni referans 2"])

        merged = _merge_brand_voice(existing, incoming)

        self.assertEqual(merged["reference_tweets"], ["Yeni referans 1", "Yeni referans 2"])
        self.assertEqual(merged["sample_voice"], "Bu alan sessizce boşlanmamalı")

    def test_default_draft_style_serializes_cloned_payload(self):
        style = DefaultDraftStyle(type="cloned", profile_id="profile-123")

        self.assertEqual(
            style.model_dump(exclude_none=True),
            {
                "type": "cloned",
                "profile_id": "profile-123",
            },
        )

    def test_default_draft_style_own_voice_drops_irrelevant_keys(self):
        style = DefaultDraftStyle(type="own_voice", profile_id="ignored", key="ignored")

        self.assertEqual(style.model_dump(exclude_none=True), {"type": "own_voice"})

    def test_default_draft_style_requires_shape(self):
        for payload in ({"type": "cloned"}, {"type": "archetype"}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    DefaultDraftStyle(**payload)


if __name__ == "__main__":
    unittest.main()
