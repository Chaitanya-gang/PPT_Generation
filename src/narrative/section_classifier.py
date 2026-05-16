"""
Section classification and slide planning helpers.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Sequence


SECTION_PATTERNS: Dict[str, Sequence[str]] = {
    "introduction": (
        "introduction", "overview", "abstract", "background", "summary", "context",
    ),
    "problem": (
        "problem", "challenge", "issue", "gap", "pain", "need", "limitation",
    ),
    "objective": (
        "objective", "goal", "aim", "purpose", "scope", "proposal",
    ),
    "definition": (
        "definition", "concept", "theory", "principle", "foundation", "about",
    ),
    "methodology": (
        "method", "methodology", "workflow", "process", "pipeline", "architecture", "system",
    ),
    "example": (
        "example", "case", "scenario", "demo", "application", "use case",
    ),
    "results": (
        "result", "results", "finding", "analysis", "performance", "evaluation", "impact",
    ),
    "conclusion": (
        "conclusion", "closing", "summary", "future", "recommendation", "next step",
    ),
}


FLOW_BLUEPRINTS: Dict[str, List[str]] = {
    "general": ["introduction", "problem", "definition", "methodology", "example", "results", "conclusion"],
    "project": ["introduction", "problem", "objective", "methodology", "example", "results", "conclusion"],
    "research": ["introduction", "problem", "definition", "methodology", "results", "conclusion"],
}


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    sentences: List[str] = []
    for part in parts:
        cleaned = " ".join(part.split()).strip(" -•\t")
        if len(cleaned) >= 18:
            sentences.append(cleaned)
    return sentences


def summarize_to_bullets(text: str, limit: int = 4, max_chars: int = 90) -> List[str]:
    bullets: List[str] = []
    for sentence in split_sentences(text):
        bullet = sentence[:max_chars].rstrip(" ,;:")
        if bullet and bullet not in bullets:
            bullets.append(bullet)
        if len(bullets) >= limit:
            break
    if bullets:
        return bullets

    compact = " ".join((text or "").split())
    if compact:
        return [compact[:max_chars].rstrip(" ,;:")]
    return ["Key point generated from the document"]


def classify_section(title: str, content: str) -> str:
    haystack = f"{title} {content}".lower()
    scores = Counter()

    for label, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if pattern in haystack:
                scores[label] += 2 if pattern in title.lower() else 1

    if scores:
        return scores.most_common(1)[0][0]

    if any(token in haystack for token in ("why", "need", "pain")):
        return "problem"
    if any(token in haystack for token in ("how", "workflow", "steps")):
        return "methodology"
    if any(token in haystack for token in ("therefore", "overall", "in summary")):
        return "conclusion"
    return "definition"


def infer_document_mode(text: str) -> str:
    lowered = (text or "").lower()
    if sum(
        1
        for keyword in ("system", "architecture", "implementation", "module", "api", "frontend", "backend")
        if keyword in lowered
    ) >= 3:
        return "project"
    if sum(
        1 for keyword in ("literature", "hypothesis", "experiment", "evaluation", "study")
        if keyword in lowered
    ) >= 2:
        return "research"
    return "general"


def plan_slide_flow(section_types: Sequence[str], document_mode: str, slide_count: int) -> List[str]:
    blueprint = FLOW_BLUEPRINTS.get(document_mode, FLOW_BLUEPRINTS["general"])
    content_slots = max(1, slide_count - 2)
    planned: List[str] = []

    for section_type in blueprint:
        if section_type in section_types and section_type not in planned:
            planned.append(section_type)
        if len(planned) >= content_slots:
            break

    for section_type in section_types:
        if section_type not in planned:
            planned.append(section_type)
        if len(planned) >= content_slots:
            break

    while len(planned) < content_slots:
        fallback = blueprint[min(len(planned), len(blueprint) - 1)]
        planned.append(fallback)

    return planned[:content_slots]


def choose_layout(section_type: str, has_visual: bool, bullet_count: int) -> str:
    if section_type in {"results"} and bullet_count <= 2:
        return "title_big_number"
    if has_visual or section_type in {"methodology", "example"}:
        return "two_column"
    if bullet_count >= 4:
        return "title_bullets"
    return "visual_focus"
