"""
Brand Manifest Pydantic Schema

Validates all markdown files in brand_manifest/ against a canonical schema.
Used by:
- CI gate (GitHub Actions): manifest-validate job
- Writer agent: context package builder
- Compliance Checker: rules loader
- Visual Director: visual style loader

Run locally:
    python schema.py validate

Run as CI:
    python schema.py ci
"""
from __future__ import annotations

import re
import sys
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


MANIFEST_DIR = Path(__file__).parent
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ---------- Common Enums ----------


class DocumentType(str, Enum):
    PERSONA = "persona"
    VOICE_GUIDE = "voice_guide"
    VISUAL_GUIDE = "visual_guide"
    PLATFORM_CONFIG = "platform_config"
    COMPLIANCE_RULES = "compliance_rules"
    EXAMPLES_CORPUS = "examples_corpus"


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    YOUTUBE_SHORTS = "youtube_shorts"
    MEDIUM = "medium"


class PersonaStatus(str, Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


class Language(str, Enum):
    TR = "tr"
    EN = "en"


class Severity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class EnforcementLevel(str, Enum):
    BLOCKING = "blocking"
    SOFT = "soft"


# ---------- Common Validators ----------


def validate_semver(v: str) -> str:
    if not SEMVER_RE.match(v):
        raise ValueError(f"Must be valid semver (X.Y.Z), got: {v}")
    return v


# ---------- Persona ----------


class Identity(BaseModel):
    full_name: str
    age: int = Field(ge=18, le=99)
    gender: str
    nationality: str
    city: str
    country: str
    timezone: str


class Education(BaseModel):
    institution: str
    department: str
    year: str
    expected_graduation: str


class Background(BaseModel):
    education: Education
    work_status: str
    experience_level: str


class LanguageDistribution(BaseModel):
    tr: float = Field(ge=0.0, le=1.0)
    en: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def must_sum_to_one(self):
        total = self.tr + self.en
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Distribution must sum to 1.0, got {total}")
        return self


class Niche(BaseModel):
    primary: str
    primary_weight: float = Field(ge=0.0, le=1.0)
    secondary: str
    secondary_weight: float = Field(ge=0.0, le=1.0)
    topics: list[str]


class Languages(BaseModel):
    primary: Language
    secondary: Language
    distribution: LanguageDistribution


class AIDisclosurePersona(BaseModel):
    type: str
    disclosure_level: str
    is_real_person: bool
    consent_status: str
    disclosure_strategy: str
    baseline_rule: str


class AssociatedFiles(BaseModel):
    voice: str
    visual: str
    compliance: str
    examples: str
    platforms_dir: str


class PersonaFrontmatter(BaseModel):
    schema_version: str
    manifest_version: str
    persona_codename: str
    persona_display_name: str
    persona_type: str
    persona_status: PersonaStatus
    created: date
    last_updated: date
    identity: Identity
    background: Background
    niche: Niche
    languages: Languages
    values: list[str] = Field(min_length=1)
    personality_traits: list[str] = Field(min_length=1)
    ai_disclosure: AIDisclosurePersona
    associated_files: AssociatedFiles

    _semver_schema = field_validator("schema_version")(validate_semver)
    _semver_manifest = field_validator("manifest_version")(validate_semver)


# ---------- Voice ----------


class GlobalRules(BaseModel):
    always: list[str]
    never: list[str]


class EmojiPolicy(BaseModel):
    general: str
    per_post_max: int = Field(ge=0, le=10)
    preferred: list[str]
    avoid: list[str]


class VoiceFrontmatter(BaseModel):
    schema_version: str
    manifest_version: str
    document_type: DocumentType
    persona_codename: str
    created: date
    last_updated: date
    voice_strategy: str
    global_rules: GlobalRules
    emoji_policy: EmojiPolicy

    _semver_schema = field_validator("schema_version")(validate_semver)
    _semver_manifest = field_validator("manifest_version")(validate_semver)

    @field_validator("document_type")
    @classmethod
    def must_be_voice(cls, v):
        if v != DocumentType.VOICE_GUIDE:
            raise ValueError(f"Must be voice_guide, got {v}")
        return v


# ---------- Visual ----------


class VisualFrontmatter(BaseModel):
    schema_version: str
    manifest_version: str
    document_type: DocumentType
    persona_codename: str
    created: date
    last_updated: date
    visual_strategy: str
    primary_style: str
    secondary_style: Optional[str] = None
    tertiary_style: Optional[str] = None
    clip_similarity_threshold: float = Field(ge=0.0, le=1.0)
    ocr_check_enabled: bool
    aesthetic_predictor_threshold: float = Field(ge=0.0, le=1.0)
    primary_models: dict[str, str]
    reference_images: dict[str, str]

    _semver_schema = field_validator("schema_version")(validate_semver)
    _semver_manifest = field_validator("manifest_version")(validate_semver)


# ---------- Platform Config ----------


class Hashtags(BaseModel):
    count_min: int = Field(ge=0)
    count_max: int = Field(ge=0)
    required: list[str]
    preferred: list[str]

    @model_validator(mode="after")
    def max_gte_min(self):
        if self.count_max < self.count_min:
            raise ValueError(
                f"count_max ({self.count_max}) < count_min ({self.count_min})"
            )
        return self


class AIDisclosurePlatform(BaseModel):
    """
    Platform-specific AI disclosure config. Different platforms use
    different mechanisms — at least ONE disclosure mechanism must be set.
    """

    # Standard fields (LinkedIn, Instagram, Twitter)
    bio_mention_required: Optional[bool] = None
    bio_text: Optional[str] = None
    per_post_disclosure: Optional[bool] = None
    per_post_disclosure_text: Optional[str] = None
    per_post_disclosure_method: Optional[str] = None
    per_post_hashtag: Optional[str] = None
    per_image_watermark: Optional[bool] = None
    watermark_position: Optional[str] = None
    watermark_text: Optional[str] = None

    # YouTube Shorts specific
    channel_description: Optional[str] = None
    video_description_required_line: Optional[str] = None
    per_video_visual_label: Optional[bool] = None
    visual_label_position: Optional[str] = None
    visual_label_text: Optional[str] = None

    # Medium specific
    profile_bio_mention_required: Optional[bool] = None
    profile_bio_text: Optional[str] = None
    per_article_footer_required: Optional[bool] = None
    per_article_footer_text: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_disclosure_mechanism(self):
        has_bio = self.bio_mention_required or self.profile_bio_mention_required
        has_per_post = (
            self.per_post_disclosure
            or self.per_video_visual_label
            or self.per_article_footer_required
        )
        has_channel = bool(self.channel_description)
        if not (has_bio or has_per_post or has_channel):
            raise ValueError(
                "AI disclosure must have at least one mechanism: "
                "bio_mention, per_post_disclosure, channel_description, "
                "video_label, or article_footer."
            )
        return self


class PlatformFrontmatter(BaseModel):
    schema_version: str
    manifest_version: str
    document_type: DocumentType
    platform: Platform
    persona_codename: str
    created: date
    active: bool
    priority_tier: int = Field(ge=1, le=3)
    implementation_phase: str
    primary_language: Language
    secondary_language: Language
    language_distribution: dict[str, float]
    content_types: list[str]
    posting_strategy: dict[str, Any]
    cadence: dict[str, Any]
    content_pillars: list[dict[str, Any]]
    hashtags: Optional[Hashtags] = None
    publishing: dict[str, Any]
    ai_disclosure: AIDisclosurePlatform

    _semver_schema = field_validator("schema_version")(validate_semver)
    _semver_manifest = field_validator("manifest_version")(validate_semver)

    @field_validator("document_type")
    @classmethod
    def must_be_platform(cls, v):
        if v != DocumentType.PLATFORM_CONFIG:
            raise ValueError(f"Must be platform_config, got {v}")
        return v

    @model_validator(mode="after")
    def language_distribution_sums_to_one(self):
        total = sum(self.language_distribution.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"language_distribution must sum to 1.0, got {total}"
            )
        return self

    @model_validator(mode="after")
    def pillars_weights_sum_to_one(self):
        total = sum(p.get("weight", 0) for p in self.content_pillars)
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"content_pillars weights must sum to 1.0, got {total}"
            )
        return self


# ---------- Compliance ----------


class BannedTopic(BaseModel):
    id: str = Field(pattern=r"^BT\d{2}$")
    name: str
    severity: Severity


class AllowedWithCaveat(BaseModel):
    id: str = Field(pattern=r"^AT\d{2}$")
    name: str
    rule: str


class ComplianceAIDisclosure(BaseModel):
    global_required: bool
    global_baseline_rule: str
    platform_specific: str


class ComplianceFrontmatter(BaseModel):
    schema_version: str
    manifest_version: str
    document_type: DocumentType
    persona_codename: str
    created: date
    last_updated: date
    enforcement_level: EnforcementLevel
    auto_reject_threshold: int = Field(ge=1)
    strike_rule: str
    ai_disclosure: ComplianceAIDisclosure
    banned_topics_default: list[BannedTopic] = Field(min_length=1)
    allowed_with_caveats: list[AllowedWithCaveat]

    _semver_schema = field_validator("schema_version")(validate_semver)
    _semver_manifest = field_validator("manifest_version")(validate_semver)

    @field_validator("document_type")
    @classmethod
    def must_be_compliance(cls, v):
        if v != DocumentType.COMPLIANCE_RULES:
            raise ValueError(f"Must be compliance_rules, got {v}")
        return v


# ---------- Examples ----------


class ExamplesFrontmatter(BaseModel):
    schema_version: str
    manifest_version: str
    document_type: DocumentType
    persona_codename: str
    created: date
    last_updated: date
    purpose: str
    total_examples: int = Field(ge=1)
    distribution: dict[str, int]

    _semver_schema = field_validator("schema_version")(validate_semver)
    _semver_manifest = field_validator("manifest_version")(validate_semver)

    @field_validator("document_type")
    @classmethod
    def must_be_examples(cls, v):
        if v != DocumentType.EXAMPLES_CORPUS:
            raise ValueError(f"Must be examples_corpus, got {v}")
        return v

    @model_validator(mode="after")
    def distribution_sum_matches_total(self):
        actual_sum = sum(self.distribution.values())
        if actual_sum != self.total_examples:
            raise ValueError(
                f"distribution sum ({actual_sum}) != total_examples ({self.total_examples})"
            )
        return self


# ---------- Frontmatter Parser ----------


def parse_frontmatter(file_path: Path) -> dict:
    text = file_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{file_path}: missing YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{file_path}: malformed frontmatter")
    return yaml.safe_load(parts[1])


# ---------- File-to-Schema Mapping ----------


SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "persona.md": PersonaFrontmatter,
    "voice.md": VoiceFrontmatter,
    "visual.md": VisualFrontmatter,
    "compliance.md": ComplianceFrontmatter,
    "examples.md": ExamplesFrontmatter,
}

PLATFORM_FILES = [
    "platforms/linkedin.md",
    "platforms/instagram.md",
    "platforms/twitter.md",
    "platforms/youtube-shorts.md",
    "platforms/medium.md",
]


# ---------- Validator ----------


def validate_all(manifest_dir: Path = MANIFEST_DIR) -> tuple[int, int, list[str]]:
    """
    Returns (passed, failed, errors).
    """
    passed = 0
    failed = 0
    errors: list[str] = []

    # Top-level files
    for filename, schema in SCHEMA_MAP.items():
        file_path = manifest_dir / filename
        if not file_path.exists():
            failed += 1
            errors.append(f"❌ {filename}: file not found")
            continue
        try:
            data = parse_frontmatter(file_path)
            schema.model_validate(data)
            passed += 1
            print(f"✅ {filename}")
        except (ValidationError, ValueError, yaml.YAMLError) as e:
            failed += 1
            errors.append(f"❌ {filename}: {e}")

    # Platform files
    for filename in PLATFORM_FILES:
        file_path = manifest_dir / filename
        if not file_path.exists():
            failed += 1
            errors.append(f"❌ {filename}: file not found")
            continue
        try:
            data = parse_frontmatter(file_path)
            PlatformFrontmatter.model_validate(data)
            passed += 1
            print(f"✅ {filename}")
        except (ValidationError, ValueError, yaml.YAMLError) as e:
            failed += 1
            errors.append(f"❌ {filename}: {e}")

    return passed, failed, errors


# ---------- CLI ----------


def main():
    if len(sys.argv) < 2:
        print("Usage: python schema.py [validate|ci]")
        sys.exit(2)

    cmd = sys.argv[1]

    if cmd in ("validate", "ci"):
        passed, failed, errors = validate_all()
        print()
        print(f"📊 Results: {passed} passed, {failed} failed")
        if errors:
            print("\nErrors:")
            for e in errors:
                print(f"  {e}")
        if failed > 0:
            sys.exit(1)
        sys.exit(0)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(2)


if __name__ == "__main__":
    main()
