from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


LOGGER = logging.getLogger("reconstructed_corpus_nlp_analysis")


try:
    from common import (  # type: ignore
        ACCOUNTABILITY_TERMS,
        ACTOR_FORUM_TERMS,
        ALGORITHMIC_PRACTICE_TERMS,
        BASE_DIR,
        CONSEQUENCE_TERMS,
        CONSENT_TERMS,
        CONTESTABILITY_TERMS,
        CONTEXT_TERMS,
        DATA_DISCLOSURE_TERMS,
        DISCLOSURE_TERMS,
        OPACITY_TERMS,
        STOPWORDS,
    )
except Exception:  # pragma: no cover - fallback for standalone use outside project
    BASE_DIR = Path(__file__).resolve().parents[1]
    DISCLOSURE_TERMS = [
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
        "automated decision",
        "automated decision-making",
        "automated processing",
        "artificial intelligence",
        "machine learning",
        "algorithm",
        "algorithmic",
        "model training",
        "training data",
        "ai training",
        "profiling",
        "targeting",
        "advertising",
        "ads",
        "service improvement",
        "improve services",
        " ai ",
    ]
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
        term for term in DISCLOSURE_TERMS if term not in set(DATA_DISCLOSURE_TERMS)
    ]
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
    STOPWORDS = {
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "with",
        "a",
        "an",
        "is",
        "are",
        "you",
        "we",
        "your",
        "our",
        "this",
        "that",
        "these",
        "those",
        "be",
        "as",
        "by",
        "on",
        "at",
        "from",
        "it",
        "its",
        "they",
        "their",
        "not",
        "may",
        "will",
        "can",
    }


MANIFEST_COLUMNS = [
    "doc_id",
    "original_doc_id",
    "doc_id_collision_status",
    "file_name",
    "absolute_path",
    "relative_path_from_project",
    "size_bytes",
    "sha256",
    "last_write_time",
    "encoding",
    "read_status",
    "char_count",
    "word_count",
    "line_count",
    "source_match_status",
    "source_relative_path",
    "source_root",
    "source_size_bytes",
    "source_sha256",
    "dataset_layer",
    "dataset_role",
    "platform",
    "platform_slug",
    "doc_type",
    "language",
    "filename_date",
    "filename_datetime",
    "date_precision",
    "date_pattern",
    "date_parse_status",
]

DOCUMENT_METADATA_COLUMNS = [
    "doc_id",
    "file_name",
    "source_root",
    "dataset_layer",
    "dataset_role",
    "platform",
    "platform_slug",
    "doc_type",
    "language",
    "filename_date",
    "date_precision",
    "source_match_status",
    "relative_path_from_project",
    "source_relative_path",
]

SEGMENT_COLUMNS = [
    "segment_id",
    "doc_id",
    "file_name",
    "source_root",
    "dataset_layer",
    "platform",
    "doc_type",
    "filename_date",
    "section_title",
    "position",
    "segment_text",
    "char_count",
    "word_count",
]

DOC_TYPE_PATTERNS = [
    ("acceptable_use_policy", ["acceptable use", "acceptableuse", "aup"]),
    ("community_guidelines", ["community guideline", "communityguideline", "guidelines", "guideline"]),
    ("privacy_policy", ["privacy policy", "privacypolicy", "privacy notice", "privacy"]),
    ("developer_terms", ["developer terms", "developer", "api terms"]),
    ("cookie_policy", ["cookie"]),
    ("data_policy", ["data policy", "data processing", "data use"]),
    ("terms_of_service", ["terms of service", "termsofservice", "terms_of_service", "terms", "tos", "service"]),
]

SOURCE_LAYER_MAP = {
    "COMPARE-main": ("main_core", "sampling frame / community guidelines"),
    "pga-versions-actual": ("main_core", "platform governance archive versions"),
    "pga-corpus-1.01": ("historical_module", "historical platform governance archive"),
    "genai-eu-2026-05-25": ("ai_module", "AI governance extension"),
}

THEORY_TERM_GROUPS = {
    "documentary_transparency": ALGORITHMIC_PRACTICE_TERMS,
    "algorithmic_practice": ALGORITHMIC_PRACTICE_TERMS,
    "data_disclosure": DATA_DISCLOSURE_TERMS,
    "procedure": ACCOUNTABILITY_TERMS,
    "actor_forum": ACTOR_FORUM_TERMS,
    "consequence": CONSEQUENCE_TERMS,
    "contestability": CONTESTABILITY_TERMS,
    "algorithmic_opacity": OPACITY_TERMS,
    "boilerplate_consent": CONSENT_TERMS,
    "contextual_integrity": CONTEXT_TERMS,
}


@dataclass(slots=True)
class CorpusAnalysisConfig:
    """Runtime settings for the reconstructed corpus analysis pipeline."""

    base_dir: Path
    input_dir: Path
    old_index_path: Path
    out_dir: Path
    report_path: Path
    candidate_limit: int = 60
    max_tfidf_features: int = 5000
    top_terms_limit: int = 5000
    top_ngram_limit: int = 500
    min_segment_words: int = 8
    close_reading_min_words: int = 30
    close_reading_max_words: int = 320
    expected_document_count: int = 1059
    random_seed: int = 42
    skip_figures: bool = False
    use_spacy: bool = False
    spacy_model: str = "en_core_web_sm"
    max_spacy_chars: int = 100_000

    def resolve_paths(self) -> "CorpusAnalysisConfig":
        """Resolve CLI paths relative to the project directory."""

        for field_name in ["input_dir", "old_index_path", "out_dir", "report_path"]:
            value = getattr(self, field_name)
            if not value.is_absolute():
                setattr(self, field_name, self.base_dir / value)
        return self


def configure_logging(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, mode="w", encoding="utf-8"),
        ],
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> tuple[str, str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            status = "ok_suspicious_mojibake" if looks_like_mojibake(text) else "ok"
            return text, encoding, status
        except UnicodeDecodeError:
            continue
    text = path.read_text(encoding="utf-8", errors="replace")
    status = "replacement_suspicious_mojibake" if looks_like_mojibake(text) else "replacement"
    return text, "utf-8", status


def looks_like_mojibake(text: str) -> bool:
    if not text:
        return False
    replacement_ratio = text.count("\ufffd") / max(1, len(text))
    mojibake_fragments = ("Рґ", "Рµ", "Р°", "СЃ", "С‚", "СЏ", "СЊ", "Рё", "Рѕ", "РЅ")
    mojibake_hits = sum(text.count(fragment) for fragment in mojibake_fragments)
    return replacement_ratio > 0.001 or mojibake_hits > 30


def tokenize_regex(text: str) -> list[str]:
    return re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", text.lower())


def count_words(text: str) -> int:
    return len(tokenize_regex(text))


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9а-яё]+", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered).strip("-")
    return lowered or "unknown"


def safe_name_without_hash(file_name: str) -> str:
    stem = Path(file_name).stem
    if "__" in stem:
        return stem.split("__", 1)[1]
    return stem


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def dictionary_hash() -> str:
    payload = json.dumps(THEORY_TERM_GROUPS, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_hash_or_not_found(path: Path) -> str:
    if not path.exists():
        return "not_found"
    return sha256_file(path)


def source_code_paths(config: CorpusAnalysisConfig) -> list[Path]:
    paths = [Path(__file__).resolve()]
    common_path = config.base_dir / "scripts" / "common.py"
    if common_path.exists():
        paths.append(common_path)
    return paths


class MetadataInferencer:
    """Infer cautious working metadata from file names and old index paths."""

    def parse_filename_date(self, file_name: str) -> dict[str, str]:
        base = safe_name_without_hash(file_name)
        iso = re.search(r"(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-(\d{2})Z", base)
        if iso:
            year, month, day, hour, minute, second = iso.groups()
            return {
                "filename_date": f"{year}-{month}-{day}",
                "filename_datetime": f"{year}-{month}-{day}T{hour}:{minute}:{second}Z",
                "date_precision": "datetime",
                "date_pattern": "YYYY-MM-DDTHH-MM-SSZ",
                "date_parse_status": "parsed",
            }
        compact = re.search(r"(?:^|[_-])(\d{4})(\d{2})(\d{2})(?:[_-]|$)", base)
        if compact:
            year, month, day = compact.groups()
            return {
                "filename_date": f"{year}-{month}-{day}",
                "filename_datetime": "",
                "date_precision": "day",
                "date_pattern": "YYYYMMDD",
                "date_parse_status": "parsed",
            }
        generic = re.search(r"(\d{4})-(\d{2})-(\d{2})", base)
        if generic:
            year, month, day = generic.groups()
            return {
                "filename_date": f"{year}-{month}-{day}",
                "filename_datetime": "",
                "date_precision": "day",
                "date_pattern": "YYYY-MM-DD",
                "date_parse_status": "parsed",
            }
        return {
            "filename_date": "not_found",
            "filename_datetime": "",
            "date_precision": "not_found",
            "date_pattern": "not_found",
            "date_parse_status": "not_found",
        }

    def infer_source_root(self, source_relative_path: str) -> str:
        if not source_relative_path:
            return "unknown"
        parts = Path(source_relative_path).parts
        return parts[0] if parts else "unknown"

    def infer_doc_type(self, file_name: str, source_relative_path: str) -> str:
        haystack = f"{safe_name_without_hash(file_name)} {source_relative_path}".lower().replace("_", " ")
        for doc_type, patterns in DOC_TYPE_PATTERNS:
            if any(pattern in haystack for pattern in patterns):
                return doc_type
        return "unknown"

    def infer_platform(self, file_name: str, source_relative_path: str) -> str:
        path_parts = Path(source_relative_path).parts if source_relative_path else ()
        if path_parts:
            if path_parts[0] == "COMPARE-main" and len(path_parts) >= 5:
                return path_parts[4]
            if path_parts[0] == "genai-eu-2026-05-25" and len(path_parts) >= 3:
                return path_parts[2]
            if path_parts[0] in {"pga-versions-actual"} and len(path_parts) >= 2:
                return path_parts[1]
            if path_parts[0] == "pga-corpus-1.01" and len(path_parts) >= 5:
                return path_parts[-3]
        base = safe_name_without_hash(file_name)
        base = re.sub(r"^\d{8}_", "", base)
        base = re.sub(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$", "", base)
        markers = [
            "_PrivacyPolicy",
            "_TermsofService",
            "_CommunityGuidelines",
            "_Terms_of_Service",
            "_Privacy_Policy",
            "_Community_Guidelines",
        ]
        for marker in markers:
            base = base.replace(marker, "")
        base = re.sub(r"[_-]+", " ", base).strip()
        if not base or re.fullmatch(r"\d+", base):
            return "unknown"
        return base[:120]

    def infer_language(self, file_name: str, text: str) -> str:
        base = safe_name_without_hash(file_name).lower()
        if base.endswith("_en"):
            return "en"
        latin = len(re.findall(r"[A-Za-z]", text))
        cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
        if latin > cyrillic * 3 and latin > 200:
            return "en_or_latin_script"
        if cyrillic > latin and cyrillic > 200:
            return "ru_or_cyrillic_script"
        return "unknown"


class CorpusIndexer:
    """Build a non-destructive index for the current Markdown corpus."""

    def __init__(self, config: CorpusAnalysisConfig, inferencer: MetadataInferencer) -> None:
        self.config = config
        self.inferencer = inferencer

    def load_old_index(self) -> dict[str, list[dict[str, str]]]:
        by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in read_csv_rows(self.config.old_index_path):
            if row.get("file_group") != "md":
                continue
            copied_name = Path(row.get("copied_relative_path", "")).name
            if copied_name:
                by_name[copied_name].append(row)
        return by_name

    def resolve_old_index_row(
        self,
        path: Path,
        digest: str,
        old_by_name: dict[str, list[dict[str, str]]],
    ) -> tuple[dict[str, str] | None, str]:
        candidates = old_by_name.get(path.name, [])
        if not candidates:
            return None, "unmatched_in_old_index"
        exact = [
            row
            for row in candidates
            if row.get("source_sha256") == digest
            and str(row.get("source_size_bytes", "")) == str(path.stat().st_size)
        ]
        if len(exact) == 1:
            return exact[0], "matched_by_hash_size_and_name"
        if len(exact) > 1:
            return None, "ambiguous_old_index_hash_size_name"
        if len(candidates) == 1:
            return candidates[0], "matched_by_name_only"
        return None, "ambiguous_old_index_name"

    def build_index(self) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        if not self.config.input_dir.exists():
            raise FileNotFoundError(f"Markdown corpus directory not found: {self.config.input_dir}")
        old_by_name = self.load_old_index()
        rows: list[dict[str, Any]] = []
        text_by_doc_id: dict[str, str] = {}
        old_matches = 0
        match_status_counts: Counter[str] = Counter()
        seen_doc_ids: Counter[str] = Counter()
        paths = sorted(self.config.input_dir.rglob("*.md"))
        for path in paths:
            text, encoding, read_status = read_text(path)
            original_doc_id = path.stem
            seen_doc_ids[original_doc_id] += 1
            if seen_doc_ids[original_doc_id] == 1:
                doc_id = original_doc_id
                doc_id_collision_status = "unique"
            else:
                doc_id = f"{original_doc_id}__dup{seen_doc_ids[original_doc_id]:03d}"
                doc_id_collision_status = "renamed_duplicate_stem"
            digest = sha256_file(path)
            old_row, source_match_status = self.resolve_old_index_row(path, digest, old_by_name)
            source_relative_path = old_row.get("source_relative_path", "") if old_row else ""
            source_root = self.inferencer.infer_source_root(source_relative_path)
            match_status_counts[source_match_status] += 1
            if old_row:
                old_matches += 1
            dataset_layer, dataset_role = SOURCE_LAYER_MAP.get(source_root, ("unknown", "unknown"))
            platform = self.inferencer.infer_platform(path.name, source_relative_path)
            date_info = self.inferencer.parse_filename_date(path.name)
            row = {
                "doc_id": doc_id,
                "original_doc_id": original_doc_id,
                "doc_id_collision_status": doc_id_collision_status,
                "file_name": path.name,
                "absolute_path": str(path.resolve()),
                "relative_path_from_project": path.relative_to(self.config.base_dir).as_posix()
                if path.is_relative_to(self.config.base_dir)
                else str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "sha256": digest,
                "last_write_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "encoding": encoding,
                "read_status": read_status,
                "char_count": len(text),
                "word_count": count_words(text),
                "line_count": text.count("\n") + (1 if text else 0),
                "source_match_status": source_match_status,
                "source_relative_path": source_relative_path,
                "source_root": source_root,
                "source_size_bytes": old_row.get("source_size_bytes", "") if old_row else "",
                "source_sha256": old_row.get("source_sha256", "") if old_row else "",
                "dataset_layer": dataset_layer,
                "dataset_role": dataset_role,
                "platform": platform,
                "platform_slug": slugify(platform),
                "doc_type": self.inferencer.infer_doc_type(path.name, source_relative_path),
                "language": self.inferencer.infer_language(path.name, text),
                **date_info,
            }
            rows.append(row)
            text_by_doc_id[doc_id] = text
        diagnostics = {
            "total_md_files": len(rows),
            "old_index_md_rows": sum(len(value) for value in old_by_name.values()),
            "old_index_unique_copied_names": len(old_by_name),
            "old_index_name_matches": old_matches,
            "unmatched_in_old_index": len(rows) - old_matches,
            "match_status_counts": dict(match_status_counts),
            "doc_id_duplicate_stems": sum(1 for count in seen_doc_ids.values() if count > 1),
        }
        return rows, diagnostics, text_by_doc_id


class MarkdownSegmenter:
    """Split Markdown documents into section-aware paragraph segments."""

    def __init__(self, config: CorpusAnalysisConfig) -> None:
        self.config = config

    def split(self, text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []
        section_title = ""
        buffer: list[str] = []
        position = 0

        def flush() -> None:
            nonlocal position, buffer
            joined = "\n".join(buffer).strip()
            buffer = []
            if not joined:
                return
            paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", joined) if paragraph.strip()]
            for paragraph in paragraphs:
                if count_words(paragraph) < self.config.min_segment_words:
                    continue
                position += 1
                doc_id = metadata["doc_id"]
                segments.append(
                    {
                        "segment_id": f"{doc_id}::s{position:04d}",
                        "doc_id": doc_id,
                        "file_name": metadata["file_name"],
                        "source_root": metadata["source_root"],
                        "dataset_layer": metadata["dataset_layer"],
                        "platform": metadata["platform"],
                        "doc_type": metadata["doc_type"],
                        "filename_date": metadata["filename_date"],
                        "section_title": section_title,
                        "position": position,
                        "segment_text": paragraph,
                        "char_count": len(paragraph),
                        "word_count": count_words(paragraph),
                    }
                )

        for line in text.splitlines():
            header_match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$", line)
            if header_match:
                flush()
                section_title = header_match.group(2).strip()
                continue
            buffer.append(line)
        flush()
        return segments


class TheoryFeatureExtractor:
    """Extract theory-aligned dictionary features without treating them as final interpretation."""

    def __init__(self) -> None:
        self.term_groups = THEORY_TERM_GROUPS
        self.term_patterns: dict[str, re.Pattern[str]] = {}
        self.compiled_term_groups: dict[str, list[tuple[str, str, re.Pattern[str]]]] = {}
        for group, terms in self.term_groups.items():
            compiled_terms: list[tuple[str, str, re.Pattern[str]]] = []
            for term in terms:
                stripped = term.lower().strip()
                if not stripped:
                    continue
                pattern = self.term_pattern(term)
                self.term_patterns[term] = pattern
                compiled_terms.append((term, stripped, pattern))
            self.compiled_term_groups[group] = compiled_terms

    def find_terms(self, text: str, terms: Iterable[str]) -> list[str]:
        lowered = text.lower()
        found: list[str] = []
        for term in terms:
            stripped = term.lower().strip()
            pattern = self.term_patterns.get(term) or self.term_pattern(term)
            if stripped in lowered and pattern.search(lowered):
                found.append(term)
        return found

    def count_occurrences(self, text: str, terms: Iterable[str]) -> int:
        lowered = text.lower()
        total = 0
        for term in terms:
            stripped = term.lower().strip()
            pattern = self.term_patterns.get(term) or self.term_pattern(term)
            if stripped in lowered:
                total += len(pattern.findall(lowered))
        return total

    def term_pattern(self, term: str) -> re.Pattern[str]:
        stripped = term.lower().strip()
        if not stripped:
            raise ValueError("Cannot build a pattern for an empty term")
        escaped = re.escape(stripped).replace(r"\ ", r"\s+")
        return re.compile(rf"(?<![a-z0-9-]){escaped}(?![a-z0-9-])")

    def group_hits(self, text: str, group: str) -> tuple[list[str], int]:
        lowered = text.lower()
        found: list[str] = []
        total = 0
        for term, stripped, pattern in self.compiled_term_groups[group]:
            if stripped not in lowered:
                continue
            matches = pattern.findall(lowered)
            if matches:
                found.append(term)
                total += len(matches)
        return found, total

    def evidence_phrase(self, text: str, terms: list[str], max_len: int = 280) -> str:
        lowered = text.lower()
        spans: list[tuple[int, int]] = []
        for term in terms:
            stripped = term.lower().strip()
            pattern = self.term_patterns.get(term) or self.term_pattern(term)
            if stripped not in lowered:
                continue
            match = pattern.search(lowered)
            if match:
                spans.append(match.span())
        if not spans:
            return compact_text(text)[:max_len]
        start = max(min(span[0] for span in spans) - 90, 0)
        end = min(max(span[1] for span in spans) + max_len, len(text))
        phrase = compact_text(text[start:end])
        if start > 0:
            phrase = "..." + phrase
        if end < len(text):
            phrase += "..."
        return phrase[: max_len + 6]

    def classify_cooccurrence(self, row: dict[str, Any]) -> str:
        disclosure = row["documentary_transparency_flag"] == "present"
        procedure = row["procedure_flag"] == "present"
        if disclosure and procedure:
            return "both"
        if disclosure:
            return "disclosure_only"
        if procedure:
            return "procedure_only"
        return "none"

    def infer_candidate_gap_signals(self, row: dict[str, Any]) -> list[str]:
        disclosure = row["documentary_transparency_flag"] == "present"
        procedure = row["procedure_flag"] == "present"
        actor_forum = row["actor_forum_flag"] == "present"
        consequence = row["consequence_flag"] == "present"
        contestability = row["contestability_flag"] == "present"
        opacity = row["algorithmic_opacity_flag"] == "present"
        consent = row["boilerplate_consent_flag"] == "present"
        context = row["contextual_integrity_flag"] == "present"
        signals: list[str] = []
        if disclosure and not procedure:
            signals.append("disclosure_without_procedure")
        if procedure and not consequence:
            signals.append("procedure_without_consequence")
        if disclosure and not contestability:
            signals.append("disclosure_without_contestability")
        if consent and not contestability:
            signals.append("consent_without_alternative")
        if context and not procedure:
            signals.append("context_sensitive_processing_without_procedure")
        if disclosure and opacity:
            signals.append("visible_practice_with_opaque_formula")
        if procedure and not actor_forum:
            signals.append("procedure_without_forum")
        return signals

    def extract(self, text: str) -> dict[str, Any]:
        row: dict[str, Any] = {}
        all_found: list[str] = []
        for group in self.term_groups:
            found, count = self.group_hits(text, group)
            all_found.extend(found)
            row[f"{group}_flag"] = "present" if found else "absent"
            row[f"{group}_terms"] = "|".join(found)
            row[f"{group}_count"] = count
        row["cooccurrence_class"] = self.classify_cooccurrence(row)
        signals = self.infer_candidate_gap_signals(row)
        row["candidate_gap_signals"] = "|".join(signals)
        row["silence_or_ambiguity_flag"] = "present" if signals else "absent"
        row["silence_or_ambiguity_terms"] = "|".join(signals)
        row["silence_or_ambiguity_count"] = len(signals)
        row["evidence_phrase"] = self.evidence_phrase(text, all_found)
        return row


class NlpPreprocessor:
    """Tokenize and optionally lemmatize text with graceful fallback to regex processing."""

    def __init__(self, config: CorpusAnalysisConfig) -> None:
        self.config = config
        self.stopwords = set(STOPWORDS)
        self.nlp = None
        self.optional_status: dict[str, str] = {}
        self._load_optional_tools()

    def _load_optional_tools(self) -> None:
        try:
            import nltk  # type: ignore

            self.optional_status["nltk"] = "available"
            try:
                from nltk.corpus import stopwords as nltk_stopwords  # type: ignore

                self.stopwords.update(nltk_stopwords.words("english"))
                self.optional_status["nltk_stopwords"] = "available"
            except Exception as exc:
                self.optional_status["nltk_stopwords"] = f"unavailable: {exc.__class__.__name__}"
        except Exception as exc:
            self.optional_status["nltk"] = f"unavailable: {exc.__class__.__name__}"
        if not self.config.use_spacy:
            self.optional_status["spacy"] = "disabled_by_default"
            return
        try:
            import spacy  # type: ignore

            try:
                self.nlp = spacy.load(self.config.spacy_model, disable=["parser", "ner"])
                self.nlp.max_length = max(self.nlp.max_length, self.config.max_spacy_chars + 1)
                self.optional_status["spacy"] = f"available: {self.config.spacy_model}"
            except Exception as exc:
                self.nlp = None
                self.optional_status["spacy"] = f"available_without_model: {exc.__class__.__name__}"
        except Exception as exc:
            self.optional_status["spacy"] = f"unavailable: {exc.__class__.__name__}"

    def normalize_tokens(self, text: str) -> list[str]:
        if self.nlp is not None:
            return self._normalize_with_spacy_chunks(text)
        return [token for token in tokenize_regex(text) if self._keep_token(token)]

    def _normalize_with_spacy_chunks(self, text: str) -> list[str]:
        tokens: list[str] = []
        for chunk in self._iter_text_chunks(text):
            doc = self.nlp(chunk)
            for token in doc:
                lemma = token.lemma_.lower().strip() if token.lemma_ else token.text.lower().strip()
                if self._keep_token(lemma):
                    tokens.append(lemma)
        return tokens

    def _iter_text_chunks(self, text: str) -> Iterable[str]:
        max_chars = self.config.max_spacy_chars
        if len(text) <= max_chars:
            yield text
            return
        buffer: list[str] = []
        size = 0
        for paragraph in re.split(r"\n\s*\n", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) > max_chars:
                if buffer:
                    yield "\n\n".join(buffer)
                    buffer = []
                    size = 0
                for start in range(0, len(paragraph), max_chars):
                    yield paragraph[start : start + max_chars]
                continue
            if size + len(paragraph) + 2 > max_chars and buffer:
                yield "\n\n".join(buffer)
                buffer = []
                size = 0
            buffer.append(paragraph)
            size += len(paragraph) + 2
        if buffer:
            yield "\n\n".join(buffer)

    def _keep_token(self, token: str) -> bool:
        if not token or token in self.stopwords:
            return False
        if len(token) < 3:
            return False
        if len(token) > 40:
            return False
        if token.isdigit():
            return False
        if re.fullmatch(r"https?|www|com|org|net|html?|amp", token):
            return False
        if re.fullmatch(r"[0-9a-f]{16,}", token):
            return False
        return True


class CorpusMetricsBuilder:
    """Build corpus-level token and document statistics used for navigation and QC."""

    def __init__(self, preprocessor: NlpPreprocessor) -> None:
        self.preprocessor = preprocessor

    def document_metadata(self, index_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{key: row.get(key, "") for key in DOCUMENT_METADATA_COLUMNS} for row in index_rows]

    def token_frequencies(self, text_by_doc_id: dict[str, str], limit: int) -> tuple[list[dict[str, Any]], dict[str, list[str]], Counter[str]]:
        corpus_counter: Counter[str] = Counter()
        document_counter: Counter[str] = Counter()
        tokens_by_doc: dict[str, list[str]] = {}
        for doc_id, text in text_by_doc_id.items():
            tokens = self.preprocessor.normalize_tokens(text)
            tokens_by_doc[doc_id] = tokens
            corpus_counter.update(tokens)
            document_counter.update(set(tokens))
        rows = [
            {
                "token": token,
                "count": count,
                "document_count": document_counter[token],
            }
            for token, count in corpus_counter.most_common(limit)
        ]
        return rows, tokens_by_doc, corpus_counter


class NgramAndCollocationAnalyzer:
    """Compute n-grams and simple PMI-like collocations from normalized tokens."""

    def build_ngrams(self, tokens_by_doc: dict[str, list[str]], limit: int) -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
        bigrams: Counter[str] = Counter()
        trigrams: Counter[str] = Counter()
        for tokens in tokens_by_doc.values():
            bigrams.update(" ".join(tokens[i : i + 2]) for i in range(max(0, len(tokens) - 1)))
            trigrams.update(" ".join(tokens[i : i + 3]) for i in range(max(0, len(tokens) - 2)))
        rows: list[dict[str, Any]] = []
        for gram, count in bigrams.most_common(limit):
            rows.append({"ngram": gram, "n": 2, "count": count})
        for gram, count in trigrams.most_common(limit):
            rows.append({"ngram": gram, "n": 3, "count": count})
        return rows, bigrams, trigrams

    def build_collocations(
        self,
        unigram_counter: Counter[str],
        bigram_counter: Counter[str],
        limit: int,
        min_count: int = 5,
    ) -> list[dict[str, Any]]:
        total_unigrams = sum(unigram_counter.values())
        rows: list[dict[str, Any]] = []
        for bigram, bigram_count in bigram_counter.items():
            if bigram_count < min_count:
                continue
            parts = bigram.split()
            if len(parts) != 2:
                continue
            first, second = parts
            denominator = unigram_counter[first] * unigram_counter[second]
            if not denominator:
                continue
            pmi = math.log2((bigram_count * total_unigrams) / denominator)
            rows.append(
                {
                    "bigram": bigram,
                    "count": bigram_count,
                    "first_token_count": unigram_counter[first],
                    "second_token_count": unigram_counter[second],
                    "pmi": round(pmi, 6),
                }
            )
        rows.sort(key=lambda row: (-float(row["pmi"]), -int(row["count"]), row["bigram"]))
        return rows[:limit]


class TfidfAnalyzer:
    """Optional TF-IDF analysis using scikit-learn when it is installed."""

    def __init__(self, config: CorpusAnalysisConfig) -> None:
        self.config = config
        self.status = "not_started"

    def build(
        self,
        index_rows: list[dict[str, Any]],
        tokens_by_doc: dict[str, list[str]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        except Exception as exc:
            self.status = f"skipped: sklearn unavailable ({exc.__class__.__name__})"
            return [], []

        documents = [" ".join(tokens_by_doc.get(row["doc_id"], [])) for row in index_rows]
        doc_ids = [row["doc_id"] for row in index_rows]
        if not any(documents):
            self.status = "skipped: no tokens"
            return [], []
        vectorizer = TfidfVectorizer(
            max_features=self.config.max_tfidf_features,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.9,
            token_pattern=r"(?u)\b\w+\b",
            lowercase=False,
        )
        try:
            matrix = vectorizer.fit_transform(documents)
        except ValueError as exc:
            self.status = f"skipped: {exc}"
            return [], []
        terms = vectorizer.get_feature_names_out()
        doc_rows: list[dict[str, Any]] = []
        top_per_doc = 20
        for row_index, doc_id in enumerate(doc_ids):
            vector = matrix.getrow(row_index)
            if vector.nnz == 0:
                continue
            pairs = zip(vector.indices, vector.data)
            top_pairs = sorted(pairs, key=lambda pair: pair[1], reverse=True)[:top_per_doc]
            for rank, (term_index, score) in enumerate(top_pairs, start=1):
                doc_rows.append(
                    {
                        "doc_id": doc_id,
                        "rank": rank,
                        "term": terms[term_index],
                        "tfidf": round(float(score), 8),
                    }
                )

        group_rows: list[dict[str, Any]] = []
        for group_field in ["source_root", "dataset_layer", "doc_type"]:
            grouped_indices: dict[str, list[int]] = defaultdict(list)
            for row_index, item in enumerate(index_rows):
                grouped_indices[str(item.get(group_field, "unknown"))].append(row_index)
            for group_value, row_indices in grouped_indices.items():
                if not row_indices:
                    continue
                mean_vector = matrix[row_indices].mean(axis=0)
                mean_array = mean_vector.A1
                top_indices = mean_array.argsort()[::-1][:25]
                for rank, term_index in enumerate(top_indices, start=1):
                    score = float(mean_array[term_index])
                    if score <= 0:
                        continue
                    group_rows.append(
                        {
                            "group_field": group_field,
                            "group_value": group_value,
                            "rank": rank,
                            "term": terms[term_index],
                            "mean_tfidf": round(score, 8),
                            "document_count": len(row_indices),
                        }
                    )
        self.status = "completed"
        return doc_rows, group_rows


class CandidateSelector:
    """Select fragments for later close reading from automatic diagnostic features."""

    def __init__(self, config: CorpusAnalysisConfig) -> None:
        self.config = config

    def select(self, feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for row in feature_rows:
            word_count = int(row.get("word_count", 0))
            if word_count < self.config.close_reading_min_words or word_count > self.config.close_reading_max_words:
                continue
            candidate_gap_signals = row.get("candidate_gap_signals", "")
            if row.get("cooccurrence_class") == "none" and not candidate_gap_signals:
                continue
            reasons: list[str] = []
            if row.get("cooccurrence_class") == "disclosure_only":
                reasons.append("algorithmic_practice_without_explicit_procedure")
            if row.get("cooccurrence_class") == "both":
                reasons.append("disclosure_and_procedure_in_same_fragment")
            if row.get("filename_date") != "not_found":
                reasons.append("dated_filename")
            if row.get("algorithmic_opacity_flag") == "present":
                reasons.append("opaque_formula")
            if row.get("boilerplate_consent_flag") == "present":
                reasons.append("boilerplate_consent")
            if row.get("contextual_integrity_flag") == "present":
                reasons.append("context_sensitive_processing")
            if candidate_gap_signals:
                reasons.extend(str(candidate_gap_signals).split("|"))
            score = (
                5 * (row.get("cooccurrence_class") == "both")
                + 4 * (row.get("cooccurrence_class") == "disclosure_only")
                + 2 * (row.get("algorithmic_opacity_flag") == "present")
                + 2 * (row.get("contestability_flag") == "present")
                + 1 * (row.get("filename_date") != "not_found")
                + len(reasons)
            )
            candidate = dict(row)
            candidate["selection_reason"] = "|".join(dict.fromkeys(reasons))
            candidate["selection_score"] = score
            candidates.append(candidate)

        candidates.sort(key=lambda item: (-int(item["selection_score"]), item["doc_id"], int(item["position"])))
        return self._balanced_selection(candidates)

    def _balanced_selection(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        selected_ids: set[str] = set()
        doc_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        reason_counts: Counter[str] = Counter()
        source_order = ["COMPARE-main", "pga-corpus-1.01", "pga-versions-actual", "genai-eu-2026-05-25", "unknown"]
        available_sources = [source for source in source_order if any(row["source_root"] == source for row in candidates)]
        per_source_target = max(6, self.config.candidate_limit // max(1, len(available_sources)))

        def try_add(row: dict[str, Any], source_cap: int) -> bool:
            if len(selected) >= self.config.candidate_limit:
                return False
            if row["segment_id"] in selected_ids:
                return False
            if doc_counts[row["doc_id"]] >= 3:
                return False
            if source_counts[row["source_root"]] >= source_cap:
                return False
            main_reason = row["selection_reason"].split("|")[0] if row["selection_reason"] else "general"
            if reason_counts[main_reason] >= 16:
                return False
            selected.append(row)
            selected_ids.add(row["segment_id"])
            doc_counts[row["doc_id"]] += 1
            source_counts[row["source_root"]] += 1
            reason_counts[main_reason] += 1
            return True

        for source in available_sources:
            for row in candidates:
                if row["source_root"] != source:
                    continue
                if source_counts[source] >= per_source_target:
                    break
                try_add(row, per_source_target)

        source_cap = max(per_source_target + 4, 14)
        for row in candidates:
            if len(selected) >= self.config.candidate_limit:
                break
            try_add(row, source_cap)

        if len(selected) < self.config.candidate_limit:
            for row in candidates:
                if len(selected) >= self.config.candidate_limit:
                    break
                if row["segment_id"] in selected_ids:
                    continue
                if doc_counts[row["doc_id"]] >= 4:
                    continue
                selected.append(row)
                selected_ids.add(row["segment_id"])
                doc_counts[row["doc_id"]] += 1
        return selected[: self.config.candidate_limit]


class VisualizationBuilder:
    """Create internal diagnostic figures when optional visualization libraries are installed."""

    def __init__(self, config: CorpusAnalysisConfig) -> None:
        self.config = config
        self.status: list[str] = []

    def build(
        self,
        index_rows: list[dict[str, Any]],
        document_feature_rows: list[dict[str, Any]],
        token_rows: list[dict[str, Any]],
    ) -> list[str]:
        if self.config.skip_figures:
            self.status.append("skipped: --skip-figures")
            return self.status
        try:
            import matplotlib.pyplot as plt  # type: ignore
            import seaborn as sns  # type: ignore
        except Exception as exc:
            self.status.append(f"skipped: matplotlib/seaborn unavailable ({exc.__class__.__name__})")
            return self.status
        figures_dir = self.config.out_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        sns.set_theme(style="whitegrid")
        self._bar_plot(
            plt,
            Counter(row["doc_type"] for row in index_rows),
            figures_dir / "document_types.png",
            "Document Types",
        )
        self._bar_plot(
            plt,
            Counter(row["source_root"] for row in index_rows),
            figures_dir / "source_layers.png",
            "Source Layers",
        )
        feature_counts = Counter(
            {
                group: sum(1 for row in document_feature_rows if row.get(f"{group}_flag") == "present")
                for group in THEORY_TERM_GROUPS
            }
        )
        self._bar_plot(plt, feature_counts, figures_dir / "theory_feature_counts.png", "Theory Feature Counts")
        self._bar_plot(
            plt,
            Counter({row["token"]: int(row["count"]) for row in token_rows[:25]}),
            figures_dir / "top_terms.png",
            "Top Terms",
        )
        self._wordcloud(figures_dir / "wordcloud.png", token_rows)
        self.status.append("completed")
        return self.status

    def _bar_plot(self, plt: Any, counter: Counter[str], path: Path, title: str) -> None:
        items = counter.most_common(25)
        labels = [item[0] for item in items]
        values = [item[1] for item in items]
        width = max(8, min(16, len(labels) * 0.55))
        plt.figure(figsize=(width, 5))
        plt.bar(labels, values)
        plt.xticks(rotation=45, ha="right")
        plt.title(title)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()

    def _wordcloud(self, path: Path, token_rows: list[dict[str, Any]]) -> None:
        try:
            import matplotlib.pyplot as plt  # type: ignore
            from wordcloud import WordCloud  # type: ignore
        except Exception as exc:
            self.status.append(f"wordcloud skipped: {exc.__class__.__name__}")
            return
        frequencies = {row["token"]: int(row["count"]) for row in token_rows[:500]}
        if not frequencies:
            self.status.append("wordcloud skipped: no tokens")
            return
        cloud = WordCloud(width=1200, height=700, background_color="white").generate_from_frequencies(frequencies)
        plt.figure(figsize=(12, 7))
        plt.imshow(cloud, interpolation="bilinear")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()


class QualityChecker:
    """Collect reproducibility and integrity checks for the generated artifacts."""

    def __init__(self, config: CorpusAnalysisConfig) -> None:
        self.config = config

    def build_checks(
        self,
        index_rows: list[dict[str, Any]],
        segments: list[dict[str, Any]],
        output_paths: list[Path],
        optional_statuses: dict[str, str],
        source_paths: list[Path] | None = None,
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []

        def add(name: str, status: str, detail: str) -> None:
            checks.append({"check_name": name, "status": status, "detail": detail})

        add(
            "document_count",
            "pass" if len(index_rows) == self.config.expected_document_count else "warn",
            f"actual={len(index_rows)}; expected={self.config.expected_document_count}",
        )
        suspicious_reads = [row["doc_id"] for row in index_rows if "suspicious" in str(row.get("read_status", ""))]
        bad_reads = [row["doc_id"] for row in index_rows if row.get("read_status") not in {"ok", "replacement"}]
        add("read_status", "pass" if not bad_reads else "warn", f"bad_or_suspicious_read_count={len(bad_reads)}")
        add("suspicious_encoding", "pass" if not suspicious_reads else "warn", f"suspicious_read_count={len(suspicious_reads)}")
        empty_docs = [row["doc_id"] for row in index_rows if int(row.get("word_count", 0)) == 0]
        add("empty_documents", "pass" if not empty_docs else "warn", f"empty_document_count={len(empty_docs)}")
        doc_ids = {row["doc_id"] for row in index_rows}
        duplicate_doc_ids = len(index_rows) - len(doc_ids)
        add("unique_doc_ids", "pass" if duplicate_doc_ids == 0 else "fail", f"duplicate_doc_id_count={duplicate_doc_ids}")
        orphan_segments = [row["segment_id"] for row in segments if row.get("doc_id") not in doc_ids]
        add("segment_document_links", "pass" if not orphan_segments else "fail", f"orphan_segment_count={len(orphan_segments)}")
        add("deduplication", "pass", "deduplication_performed=false; current corpus is treated as source of truth")
        unknown_source_rate = sum(1 for row in index_rows if row.get("source_root") == "unknown") / max(1, len(index_rows))
        unknown_doc_type_rate = sum(1 for row in index_rows if row.get("doc_type") == "unknown") / max(1, len(index_rows))
        add("unknown_source_rate", "warn" if unknown_source_rate > 0.2 else "pass", f"rate={unknown_source_rate:.4f}")
        add("unknown_doc_type_rate", "warn" if unknown_doc_type_rate > 0.2 else "pass", f"rate={unknown_doc_type_rate:.4f}")
        max_source_mtime = 0.0
        if source_paths:
            existing_sources = [path for path in source_paths if path.exists()]
            max_source_mtime = max((path.stat().st_mtime for path in existing_sources), default=0.0)
        for path in output_paths:
            exists = path.exists()
            add(
                f"output_exists:{path.name}",
                "pass" if exists else "fail",
                str(path.relative_to(self.config.base_dir)) if exists and path.is_relative_to(self.config.base_dir) else str(path),
            )
            if not exists:
                continue
            stale = max_source_mtime and path.stat().st_mtime < max_source_mtime
            add(f"output_fresh:{path.name}", "warn" if stale else "pass", f"stale={bool(stale)}")
            if path.suffix.lower() == ".csv":
                record_count = self._count_csv_records(path)
                if path.name.startswith("tfidf_") and str(optional_statuses.get("sklearn", "")).startswith("skipped"):
                    add(f"csv_rows:{path.name}", "info", f"record_count={record_count}; tfidf skipped")
                else:
                    add(f"csv_rows:{path.name}", "pass" if record_count > 0 else "warn", f"record_count={record_count}")
        for name, status in optional_statuses.items():
            add(f"optional_dependency:{name}", "info", status)
        return checks

    def _count_csv_records(self, path: Path) -> int:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            try:
                next(reader)
            except StopIteration:
                return 0
            return sum(1 for _ in reader)


class ReportWriter:
    """Write a self-contained methodological report for the reconstructed script run."""

    def __init__(self, config: CorpusAnalysisConfig) -> None:
        self.config = config

    def write(
        self,
        index_rows: list[dict[str, Any]],
        segments: list[dict[str, Any]],
        document_feature_rows: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        diagnostics: dict[str, Any],
        tfidf_status: str,
        visualization_status: list[str],
        quality_rows: list[dict[str, Any]],
        token_rows: list[dict[str, Any]],
    ) -> None:
        self.config.report_path.parent.mkdir(parents=True, exist_ok=True)
        source_counts = Counter(row["source_root"] for row in index_rows)
        layer_counts = Counter(row["dataset_layer"] for row in index_rows)
        doc_type_counts = Counter(row["doc_type"] for row in index_rows)
        date_status_counts = Counter(row["date_parse_status"] for row in index_rows)
        cooccurrence_counts = Counter(row["cooccurrence_class"] for row in document_feature_rows)
        feature_counts = {
            group: sum(1 for row in document_feature_rows if row.get(f"{group}_flag") == "present")
            for group in THEORY_TERM_GROUPS
        }
        total_words = sum(int(row["word_count"]) for row in index_rows)
        word_values = [int(row["word_count"]) for row in index_rows]
        median_words = statistics.median(word_values) if word_values else 0
        top_terms = ", ".join(f"{row['token']} ({row['count']})" for row in token_rows[:20])
        quality_summary = Counter(row["status"] for row in quality_rows)
        report = f"""# Reconstructed Corpus NLP Analysis

## Введение

- Markdown-файлов в текущем индексе: `{len(index_rows)}`.
- Сегментов после разбиения: `{len(segments)}`.
- Общее число слов по regex-токенизации: `{total_words}`.
- Медианное число слов в документе: `{median_words}`.
- Записей Markdown в старом индексе: `{diagnostics.get('old_index_md_rows')}`.
- Совпадений с текущими файлами по имени копии: `{diagnostics.get('old_index_name_matches')}`.
- Несопоставленных файлов относительно старого индекса: `{diagnostics.get('unmatched_in_old_index')}`.

{self._format_counter(source_counts)}.

Слои датасета: {self._format_counter(layer_counts)}.

Типы документов: {self._format_counter(doc_type_counts)}.

Статус распознавания даты из имени файла: {self._format_counter(date_status_counts)}. Дата в имени файла не приравнивается автоматически к дате вступления документа в силу или дате последнего обновления.


Срабатывания теоретических блоков на уровне документов: {self._format_mapping(feature_counts)}.

{self._format_counter(cooccurrence_counts)}.

Наиболее частотные нормализованные токены: {top_terms if top_terms else 'нет данных'}.

Статус TF-IDF: `{tfidf_status}`.

Статус визуализаций: `{'; '.join(visualization_status) if visualization_status else 'not_started'}`.

## Фрагменты для close reading

Скрипт отобрал `{len(candidates)}` фрагментов-кандидатов. Отбор строился по методологическим условиям: наличие документального раскрытия без явной процедуры, совместное появление раскрытия и процедуры, наличие даты в имени файла, расплывчатые формулы, boilerplate consent, контекстно чувствительная обработка и потенциальные зоны молчания. Эти фрагменты не являются готовыми выводами: они предназначены для ручного close reading, проверки evidence phrases и последующего качественного кодирования.

Качество проверок: {self._format_counter(quality_summary)}.

"""
        self.config.report_path.write_text(report, encoding="utf-8")

    def _format_counter(self, counter: Counter[str], limit: int = 12) -> str:
        if not counter:
            return "нет данных"
        return ", ".join(f"`{key}`: {value}" for key, value in counter.most_common(limit))

    def _format_mapping(self, mapping: dict[str, Any], limit: int = 12) -> str:
        if not mapping:
            return "нет данных"
        items = sorted(mapping.items(), key=lambda item: str(item[0]))[:limit]
        return ", ".join(f"`{key}`: {value}" for key, value in items)


def build_segments_and_features(
    config: CorpusAnalysisConfig,
    index_rows: list[dict[str, Any]],
    text_by_doc_id: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    segmenter = MarkdownSegmenter(config)
    extractor = TheoryFeatureExtractor()
    segments: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    document_feature_rows: list[dict[str, Any]] = []
    for row in index_rows:
        text = text_by_doc_id[row["doc_id"]]
        doc_features = extractor.extract(text)
        document_feature_rows.append(
            {
                "doc_id": row["doc_id"],
                "file_name": row["file_name"],
                "source_root": row["source_root"],
                "dataset_layer": row["dataset_layer"],
                "doc_type": row["doc_type"],
                "platform": row["platform"],
                "filename_date": row["filename_date"],
                "word_count": row["word_count"],
                **doc_features,
            }
        )
        doc_segments = segmenter.split(text, row)
        segments.extend(doc_segments)
        for segment in doc_segments:
            features = extractor.extract(segment["segment_text"])
            feature_rows.append({**segment, **features})
    return segments, feature_rows, document_feature_rows


def write_run_manifest(
    config: CorpusAnalysisConfig,
    diagnostics: dict[str, Any],
    tfidf_status: str,
    visualization_status: list[str],
    optional_statuses: dict[str, str],
    counts: dict[str, int],
) -> None:
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "script": "scripts/14_reconstructed_corpus_nlp_analysis.py",
        "input_dir": str(config.input_dir),
        "old_index_path": str(config.old_index_path),
        "out_dir": str(config.out_dir),
        "report_path": str(config.report_path),
        "candidate_limit": config.candidate_limit,
        "max_tfidf_features": config.max_tfidf_features,
        "expected_document_count": config.expected_document_count,
        "random_seed": config.random_seed,
        "deduplication_performed": False,
        "script_sha256": file_hash_or_not_found(Path(__file__).resolve()),
        "common_sha256": file_hash_or_not_found(config.base_dir / "scripts" / "common.py"),
        "dictionary_hash": dictionary_hash(),
        "dictionary_group_sizes": {group: len(terms) for group, terms in THEORY_TERM_GROUPS.items()},
        "diagnostics": diagnostics,
        "counts": counts,
        "tfidf_status": tfidf_status,
        "visualization_status": visualization_status,
        "optional_dependencies": optional_statuses,
    }
    (config.out_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> CorpusAnalysisConfig:
    parser = argparse.ArgumentParser(description="Reconstructed corpus NLP analysis for platform documents.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/02_unified_dataset_20260527_2/files/md"))
    parser.add_argument("--old-index", type=Path, default=Path("data/02_unified_dataset_20260527_2/manifest/files_index.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/07_internal/reconstructed_corpus_nlp_analysis"))
    parser.add_argument("--report", type=Path, default=Path("data/08_research_materials/reconstructed_corpus_nlp_analysis.md"))
    parser.add_argument("--candidate-limit", type=int, default=60)
    parser.add_argument("--max-tfidf-features", type=int, default=5000)
    parser.add_argument("--expected-document-count", type=int, default=1059)
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument(
        "--use-spacy",
        action="store_true",
        help="Enable optional spaCy lemmatization. Disabled by default to keep full-corpus runs tractable.",
    )
    args = parser.parse_args()
    return CorpusAnalysisConfig(
        base_dir=BASE_DIR,
        input_dir=args.input_dir,
        old_index_path=args.old_index,
        out_dir=args.out_dir,
        report_path=args.report,
        candidate_limit=args.candidate_limit,
        max_tfidf_features=args.max_tfidf_features,
        expected_document_count=args.expected_document_count,
        skip_figures=args.skip_figures,
        use_spacy=args.use_spacy,
    ).resolve_paths()


def main() -> None:
    config = parse_args()
    random.seed(config.random_seed)
    configure_logging(config.out_dir)
    LOGGER.info("Starting reconstructed corpus NLP analysis")

    inferencer = MetadataInferencer()
    indexer = CorpusIndexer(config, inferencer)
    index_rows, diagnostics, text_by_doc_id = indexer.build_index()
    LOGGER.info("Indexed %s Markdown files", len(index_rows))

    segments, feature_rows, document_feature_rows = build_segments_and_features(config, index_rows, text_by_doc_id)
    LOGGER.info("Built %s segments and %s segment feature rows", len(segments), len(feature_rows))

    preprocessor = NlpPreprocessor(config)
    metrics = CorpusMetricsBuilder(preprocessor)
    document_metadata_rows = metrics.document_metadata(index_rows)
    token_rows, tokens_by_doc, unigram_counter = metrics.token_frequencies(text_by_doc_id, config.top_terms_limit)
    LOGGER.info("Built token frequencies for %s documents", len(tokens_by_doc))

    ngram_analyzer = NgramAndCollocationAnalyzer()
    ngram_rows, bigram_counter, _ = ngram_analyzer.build_ngrams(tokens_by_doc, config.top_ngram_limit)
    collocation_rows = ngram_analyzer.build_collocations(unigram_counter, bigram_counter, config.top_ngram_limit)

    tfidf_analyzer = TfidfAnalyzer(config)
    tfidf_doc_rows, tfidf_group_rows = tfidf_analyzer.build(index_rows, tokens_by_doc)
    LOGGER.info("TF-IDF status: %s", tfidf_analyzer.status)

    candidates = CandidateSelector(config).select(feature_rows)

    output_paths = [
        config.out_dir / "corpus_index.csv",
        config.out_dir / "document_metadata.csv",
        config.out_dir / "segments.csv",
        config.out_dir / "theory_feature_hits.csv",
        config.out_dir / "document_feature_summary.csv",
        config.out_dir / "token_frequencies.csv",
        config.out_dir / "ngrams.csv",
        config.out_dir / "collocations.csv",
        config.out_dir / "tfidf_terms_by_document.csv",
        config.out_dir / "tfidf_terms_by_group.csv",
        config.out_dir / "candidate_fragments.csv",
    ]

    write_csv_rows(config.out_dir / "corpus_index.csv", index_rows, MANIFEST_COLUMNS)
    write_csv_rows(config.out_dir / "document_metadata.csv", document_metadata_rows, DOCUMENT_METADATA_COLUMNS)
    write_csv_rows(config.out_dir / "segments.csv", segments, SEGMENT_COLUMNS)
    write_csv_rows(config.out_dir / "theory_feature_hits.csv", feature_rows)
    write_csv_rows(config.out_dir / "document_feature_summary.csv", document_feature_rows)
    write_csv_rows(config.out_dir / "token_frequencies.csv", token_rows, ["token", "count", "document_count"])
    write_csv_rows(config.out_dir / "ngrams.csv", ngram_rows, ["ngram", "n", "count"])
    write_csv_rows(
        config.out_dir / "collocations.csv",
        collocation_rows,
        ["bigram", "count", "first_token_count", "second_token_count", "pmi"],
    )
    write_csv_rows(config.out_dir / "tfidf_terms_by_document.csv", tfidf_doc_rows, ["doc_id", "rank", "term", "tfidf"])
    write_csv_rows(
        config.out_dir / "tfidf_terms_by_group.csv",
        tfidf_group_rows,
        ["group_field", "group_value", "rank", "term", "mean_tfidf", "document_count"],
    )
    write_csv_rows(config.out_dir / "candidate_fragments.csv", candidates)

    visualization_status = VisualizationBuilder(config).build(index_rows, document_feature_rows, token_rows)
    optional_statuses = {**preprocessor.optional_status, "sklearn": tfidf_analyzer.status}
    write_run_manifest(
        config,
        diagnostics,
        tfidf_analyzer.status,
        visualization_status,
        optional_statuses,
        {
            "documents": len(index_rows),
            "segments": len(segments),
            "candidate_fragments": len(candidates),
            "token_rows": len(token_rows),
            "ngram_rows": len(ngram_rows),
            "collocation_rows": len(collocation_rows),
            "tfidf_document_rows": len(tfidf_doc_rows),
            "tfidf_group_rows": len(tfidf_group_rows),
        },
    )

    quality_checker = QualityChecker(config)
    quality_rows = quality_checker.build_checks(
        index_rows,
        segments,
        [*output_paths, config.out_dir / "run_manifest.json", config.out_dir / "quality_checks.csv"],
        optional_statuses,
        source_code_paths(config),
    )
    write_csv_rows(config.out_dir / "quality_checks.csv", quality_rows, ["check_name", "status", "detail"])

    report_writer = ReportWriter(config)
    report_writer.write(
        index_rows,
        segments,
        document_feature_rows,
        candidates,
        diagnostics,
        tfidf_analyzer.status,
        visualization_status,
        quality_rows,
        token_rows,
    )

    quality_rows = quality_checker.build_checks(
        index_rows,
        segments,
        [*output_paths, config.report_path, config.out_dir / "run_manifest.json", config.out_dir / "quality_checks.csv"],
        optional_statuses,
        source_code_paths(config),
    )
    write_csv_rows(config.out_dir / "quality_checks.csv", quality_rows, ["check_name", "status", "detail"])
    report_writer.write(
        index_rows,
        segments,
        document_feature_rows,
        candidates,
        diagnostics,
        tfidf_analyzer.status,
        visualization_status,
        quality_rows,
        token_rows,
    )
    LOGGER.info("Report written to %s", config.report_path)

    summary = {
        "documents": len(index_rows),
        "segments": len(segments),
        "candidate_fragments": len(candidates),
        "out_dir": str(config.out_dir),
        "report_path": str(config.report_path),
        "tfidf_status": tfidf_analyzer.status,
        "visualization_status": visualization_status,
        "deduplication_performed": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
