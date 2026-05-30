from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

MANIFEST_PATH = DATA_DIR / "01_manifest" / "documents_manifest.csv"
CLEAN_DIR = DATA_DIR / "03_clean_text"
TEXTS_DIR = CLEAN_DIR / "texts"
SEGMENTS_PATH = DATA_DIR / "04_segments" / "segments.csv"
FEATURES_DIR = DATA_DIR / "05_features"
CLOSE_READING_DIR = DATA_DIR / "06_close_reading"
INTERNAL_DIR = DATA_DIR / "07_internal"
RESEARCH_MATERIALS_DIR = DATA_DIR / "08_research_materials"

MANIFEST_COLUMNS = [
    "doc_id",
    "dataset_name",
    "dataset_layer",
    "dataset_role",
    "source_record_id",
    "dataset_release_or_snapshot",
    "platform",
    "platform_slug",
    "platform_type",
    "doc_type",
    "url",
    "access_date",
    "last_updated",
    "language",
    "source_format",
    "raw_path",
    "version_group",
    "audience",
    "jurisdiction",
    "notes",
]

DOC_METADATA_COLUMNS = [
    "dataset_name",
    "dataset_layer",
    "dataset_role",
    "source_record_id",
    "dataset_release_or_snapshot",
    "platform",
    "platform_slug",
    "platform_type",
    "doc_type",
    "url",
    "access_date",
    "last_updated",
    "language",
    "version_group",
    "audience",
    "jurisdiction",
]

DATASET_LAYER_VALUES = {
    "main_core",
    "historical_module",
    "codebook_calibration",
    "weak_label_layer",
    "ai_module",
    "auxiliary_not_core",
}

DATA_DISCLOSURE_TERMS = [
    "data",
    "personal data",
    "data collection",
    "collect data",
    "data processing",
    "process data",
    "data use",
    "use data",
    "data sharing",
    "share data",
    "data transfer",
    "transfer data",
    "data categories",
    "categories of data",
]

ALGORITHMIC_PRACTICE_TERMS = [
    "personalization",
    "personalisation",
    "personalize",
    "personalise",
    "recommendation",
    "recommendations",
    "recommender",
    "ranking",
    "rank",
    "moderation",
    "content moderation",
    "automated",
    "automated processing",
    "automated decision",
    "automated decision-making",
    "artificial intelligence",
    "machine learning",
    "algorithm",
    "algorithmic",
    "training data",
    "model training",
    "ai training",
    "profiling",
    "targeting",
    "advertising",
    "ads",
    "service improvement",
    "improve services",
    " ai ",
]

DISCLOSURE_TERMS = DATA_DISCLOSURE_TERMS + ALGORITHMIC_PRACTICE_TERMS

ACCOUNTABILITY_TERMS = [
    "complaint",
    "complain",
    "appeal",
    "appeals",
    "dispute",
    "challenge",
    "contest",
    "opt-out",
    "opt out",
    "withdraw consent",
    "object",
    "objection",
    "restrict processing",
    "restriction of processing",
    "delete",
    "deletion",
    "erase",
    "erasure",
    "export",
    "download",
    "data portability",
    "access",
    "correction",
    "correct",
    "rectify",
    "rectification",
    "explanation",
    "decision explanation",
    "explain decision",
    "review",
    "request review",
    "human review",
    "manual review",
    "contact",
    "contact us",
    "deadline",
    "response time",
    "within 30 days",
    "external control",
    "oversight",
    "audit",
    "regulator",
    "supervisory authority",
]

ACTOR_FORUM_TERMS = [
    "platform",
    "company",
    "provider",
    "service provider",
    "operator",
    "support",
    "customer support",
    "moderator",
    "moderation team",
    "regulator",
    "supervisory authority",
    "court",
    "tribunal",
    "auditor",
    "oversight body",
    "oversight",
    "dpo",
    "data protection officer",
    "third party",
    "controller",
    "processor",
    "public authority",
]

CONSEQUENCE_TERMS = [
    "consequence",
    "result",
    "effect",
    "change",
    "modify",
    "remove",
    "delete",
    "correct",
    "restore",
    "reinstate",
    "respond",
    "reply",
    "sanction",
    "remedy",
    "restrict",
    "provide",
    "suspend",
    "terminate",
    "reverse",
    "overturn",
    "update",
    "resolve",
]

OPACITY_TERMS = [
    "may",
    "might",
    "as needed",
    "where appropriate",
    "including but not limited to",
    "improve services",
    "service improvement",
    "legitimate interests",
    "company interests",
    "security purposes",
    "other purposes",
    "unspecified purposes",
    "unspecified third parties",
    "third parties",
    "partners",
    "affiliates",
    "from time to time",
    "at our discretion",
    "sole discretion",
    "without limitation",
    "for example",
    "such as",
]

CONSENT_TERMS = [
    "consent",
    "agree",
    "accept",
    "by using",
    "by accessing",
    "continued use",
    "continue to use",
    "click",
    "account settings",
    "settings",
    "opt in",
    "opt-in",
]

CONTEXT_TERMS = [
    "child",
    "children",
    "minor",
    "minors",
    "teen",
    "sensitive data",
    "sensitive information",
    "special category",
    "health",
    "medical",
    "finance",
    "financial",
    "payment",
    "location",
    "geolocation",
    "biometric",
    "biometrics",
    "public content",
    "public information",
]

CONTESTABILITY_TERMS = [
    "dispute",
    "challenge",
    "contest",
    "appeal",
    "complaint",
    "complain",
    "human review",
    "manual review",
    "request review",
    "review request",
    "decision explanation",
    "restrict processing",
    "object",
    "objection",
    "reconsider",
    "reconsideration",
]

TERM_GROUPS = {
    "disclosure": ALGORITHMIC_PRACTICE_TERMS,
    "data_disclosure": DATA_DISCLOSURE_TERMS,
    "algorithmic_practice": ALGORITHMIC_PRACTICE_TERMS,
    "accountability": ACCOUNTABILITY_TERMS,
    "actor_forum": ACTOR_FORUM_TERMS,
    "consequence": CONSEQUENCE_TERMS,
    "opacity": OPACITY_TERMS,
    "consent": CONSENT_TERMS,
    "context": CONTEXT_TERMS,
    "contestability": CONTESTABILITY_TERMS,
}

# Backward-compatible aliases used by older scripts and output labels.
ALG_TERMS = ALGORITHMIC_PRACTICE_TERMS
ACC_TERMS = ACCOUNTABILITY_TERMS

THEORY_FLAG_COLUMNS = [
    "documentary_transparency_flag",
    "procedure_flag",
    "actor_forum_flag",
    "consequence_flag",
    "contestability_flag",
    "opacity_flag",
    "consent_flag",
    "context_flag",
]

SECTION_HINT_TERMS = [
    "rights",
    "complaint",
    "appeal",
    "opt-out",
    "deletion",
    "delete",
    "export",
    "moderation",
    "procedure",
    "process",
    "review",
    "explanation",
    "personalization",
    "advertising",
    "ai",
    "automated",
    "enforcement",
    "human review",
    "recommendation",
    "ranking",
    "data",
    "privacy",
    "account",
    "safety",
]

STOPWORDS = {
    "the", "and", "or", "of", "to", "in", "for", "with", "a", "an", "is", "are",
    "you", "we", "your", "our", "this", "that", "these", "those", "be", "as", "by",
    "on", "at", "from", "it", "its", "they", "their", "not", "may", "will", "can",
}


def ensure_dirs() -> None:
    for path in [
        TEXTS_DIR,
        DATA_DIR / "04_segments",
        FEATURES_DIR,
        CLOSE_READING_DIR,
        INTERNAL_DIR / "tables",
        INTERNAL_DIR / "figures",
        RESEARCH_MATERIALS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\u00a0", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(remove_repeated_lines(lines))


def remove_repeated_lines(lines: list[str], max_repeats: int = 3) -> list[str]:
    counter = Counter(lines)
    seen: Counter[str] = Counter()
    result: list[str] = []
    for line in lines:
        if counter[line] > max_repeats and seen[line] >= 1:
            continue
        seen[line] += 1
        result.append(line)
    return result


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", text.lower())


def count_words(text: str) -> int:
    return len(tokenize(text))


def find_terms(text: str, terms: Iterable[str]) -> list[str]:
    low = text.lower()
    found = []
    for term in terms:
        pattern = term_pattern(term)
        if pattern and pattern.search(low):
            found.append(term)
    return found


def term_count(text: str, terms: Iterable[str]) -> int:
    low = text.lower()
    return sum(len(pattern.findall(low)) for term in terms if (pattern := term_pattern(term)))


def term_pattern(term: str) -> re.Pattern[str] | None:
    stripped = term.lower().strip()
    if not stripped:
        return None
    escaped = re.escape(stripped).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![a-z0-9-]){escaped}(?![a-z0-9-])")


def ngrams(tokens: list[str], n: int) -> list[str]:
    filtered = [tok for tok in tokens if tok not in STOPWORDS and len(tok) > 2]
    return [" ".join(filtered[i : i + n]) for i in range(max(0, len(filtered) - n + 1))]
