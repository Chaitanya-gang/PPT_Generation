"""
Lightweight local presentation generation helpers.
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import List

from src.narrative.section_classifier import (
    choose_layout,
    classify_section,
    infer_document_mode,
    plan_slide_flow,
    summarize_to_bullets,
)
from src.parsers.models import ParsedDocument


STOP_WORDS = {
    "the", "and", "for", "that", "with", "this", "from", "into", "have", "has",
    "are", "was", "were", "will", "shall", "would", "could", "should", "about",
    "their", "there", "them", "then", "than", "been", "being", "also", "such",
    "your", "our", "but", "not", "can", "may", "using", "used", "use", "each",
    "through", "within", "between", "where", "when", "what", "which", "while",
    "document", "presentation", "slide",
}

PROJECT_KEYWORDS = {
    "fastapi", "streamlit", "ollama", "llama", "rag", "faiss", "embedding",
    "vector", "chunking", "parser", "python-pptx", "ppt", "presentation",
    "retrieval", "generation", "api", "backend", "frontend",
}


def _normalize_title(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"^\d{8}_\d{6}_", "", stem)
    stem = stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() or "Presentation"


def _split_sentences(text: str) -> List[str]:
    raw_parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    sentences = []
    for part in raw_parts:
        cleaned = " ".join(part.split()).strip(" -•\t")
        if len(cleaned) >= 20:
            sentences.append(cleaned)
    return sentences


def _fallback_bullets(text: str, limit: int = 4) -> List[str]:
    return summarize_to_bullets(text, limit=limit, max_chars=90)


def _top_keywords(text: str, limit: int = 5) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text.lower())
    filtered = [word for word in words if word not in STOP_WORDS]
    counts = Counter(filtered)
    return [word.title() for word, _ in counts.most_common(limit)]


def _contains_project_markers(text: str) -> bool:
    lowered = text.lower()
    hits = sum(1 for keyword in PROJECT_KEYWORDS if keyword in lowered)
    return hits >= 3


def _extract_matching_sentences(text: str, keywords: List[str], limit: int = 4) -> List[str]:
    sentences = _split_sentences(text)
    matches = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            matches.append(sentence)
        if len(matches) >= limit:
            break
    return matches


def _compact_points(sentences: List[str], fallback: List[str]) -> List[str]:
    points = []
    for sentence in sentences:
        cleaned = sentence.strip()
        if cleaned and cleaned not in points:
            points.append(cleaned[:140])
        if len(points) >= 4:
            break
    return points or fallback


def _clean_bullets(bullets: List[str], fallback_text: str, limit: int = 4) -> List[str]:
    cleaned = []
    for bullet in bullets or []:
        value = " ".join(str(bullet).split()).strip(" -•\t")
        if value and value not in cleaned:
            cleaned.append(value[:140])
        if len(cleaned) >= limit:
            break
    return cleaned or _fallback_bullets(fallback_text, limit=limit)


def _build_speaker_notes(title: str, bullets: List[str], section_type: str) -> str:
    intro_map = {
        "introduction": f"Introduce {title.lower()} and explain why it matters in the overall topic.",
        "problem": f"Clarify the pain point behind {title.lower()} before moving to the solution.",
        "objective": f"State the objective of {title.lower()} and what outcome this slide should leave with the audience.",
        "definition": f"Explain the core idea behind {title.lower()} in simple language.",
        "methodology": f"Walk through the process in {title.lower()} step by step.",
        "example": f"Use this example to make {title.lower()} feel concrete and easy to visualize.",
        "results": f"Highlight the most important takeaway from {title.lower()} and why it is meaningful.",
        "conclusion": f"Close {title.lower()} by reinforcing the big takeaway and next step.",
    }
    lead = intro_map.get(section_type, f"Explain {title.lower()} clearly and connect it to the presentation flow.")
    bullet_summary = " ".join(bullets[:2])
    return f"{lead} {bullet_summary}".strip()


def _ensure_slide_defaults(slide: dict, source_text: str) -> dict:
    slide_type = slide.get("slide_type", "content")
    section_type = slide.get("section_type")
    if not section_type:
        section_type = "conclusion" if slide_type == "closing" else "definition"
    slide["section_type"] = section_type

    bullets = _clean_bullets(slide.get("bullet_points", []), source_text)
    if slide_type == "title":
        bullets = []
    slide["bullet_points"] = bullets

    if not slide.get("speaker_notes"):
        slide["speaker_notes"] = _build_speaker_notes(slide.get("title", "this topic"), bullets, section_type)

    if not slide.get("visual_cue"):
        visual_hints = {
            "introduction": "Opening overview with clean visual hierarchy",
            "problem": "Pain-point graphic or challenge diagram",
            "objective": "Goal-oriented visual with focus markers",
            "definition": "Concept illustration with labeled parts",
            "methodology": "Step-by-step workflow diagram",
            "example": "Example-driven layout with supporting visual",
            "results": "Impact or outcome visual with emphasis",
            "conclusion": "Closing summary visual with final takeaway",
        }
        slide["visual_cue"] = visual_hints.get(section_type, "Supporting visual for the slide topic")

    bullet_count = len(bullets)
    has_visual = any(token in slide.get("visual_cue", "").lower() for token in ("diagram", "visual", "image", "workflow"))
    slide["layout"] = slide.get("layout") or choose_layout(section_type, has_visual, bullet_count)
    slide["duration_seconds"] = int(slide.get("duration_seconds", 45) or 45)
    return slide


def _section_blocks(doc: ParsedDocument) -> List[dict]:
    blocks = []
    for section in doc.sections:
        content = section.content.strip()
        title = section.title.strip()
        if title or content:
            blocks.append(
                {
                    "title": title or "Key Topic",
                    "content": content,
                }
            )

    if blocks:
        return blocks

    paragraphs = [p.strip() for p in doc.cleaned_text.split("\n\n") if p.strip()]
    for index, paragraph in enumerate(paragraphs[:12], start=1):
        blocks.append({"title": f"Topic {index}", "content": paragraph})
    return blocks


def build_simple_summary(doc: ParsedDocument) -> str:
    text = doc.cleaned_text[:8000]
    keywords = _top_keywords(text)
    sentences = _split_sentences(text)
    summary = {
        "main_theme": _normalize_title(doc.filename),
        "key_topics": keywords,
        "data_points": [],
        "conclusion": sentences[-1] if sentences else "",
    }
    return json.dumps(summary, ensure_ascii=False)


def _conclusion_bullets(text: str, keywords: List[str]) -> List[str]:
    bullets = _fallback_bullets(text, limit=3)
    if bullets and not all(len(item.split()) == 1 for item in bullets):
        return bullets
    return keywords[:4] or ["Summary complete"]


def _build_project_narrative(doc: ParsedDocument, slide_count: int, style: str) -> str:
    text = doc.cleaned_text
    title = _normalize_title(doc.filename)
    keywords = _top_keywords(text, limit=6)
    section_titles = [section.title for section in doc.sections if section.title.strip()]

    slide_specs = [
        ("Problem Statement", ["problem", "challenge", "manual", "time consuming"], [
            "Manual PPT creation is slow",
            "Large documents take time",
            "Important points may be missed",
            "Automation is needed",
        ]),
        ("Objective", ["objective", "aim", "goal", "system"], [
            "Convert documents into PPT",
            "Reduce manual summarization",
            "Improve presentation speed",
            "Keep slide flow structured",
        ]),
        ("System Architecture", ["architecture", "streamlit", "fastapi", "backend", "frontend"], [
            "Streamlit user interface",
            "FastAPI backend processing",
            "Parser and AI pipeline",
            "PPT generation module",
        ]),
        ("Workflow / Methodology", ["workflow", "upload", "parse", "chunk", "retrieve"], [
            "Upload input document",
            "Extract and clean text",
            "Generate structured slides",
            "Export final PPT",
        ]),
        ("Tech Stack", ["fastapi", "streamlit", "faiss", "ollama", "python"], [
            "FastAPI backend services",
            "Streamlit demo interface",
            "Ollama local LLM",
            "python-pptx slide creation",
        ]),
        ("AI Pipeline", ["rag", "embedding", "vector", "faiss", "ollama", "llm"], [
            "Chunking for long documents",
            "Embeddings for retrieval",
            "FAISS vector search",
            "LLM-based slide drafting",
        ]),
        ("Code Modules", ["api", "parser", "ppt", "llm", "rag", "module"], [
            "API route handlers",
            "Document parsers",
            "LLM and RAG modules",
            "PPT builder components",
        ]),
        ("Results / Output", ["output", "result", "ppt", "presentation"], [
            "Generated PPTX output",
            "Structured slide flow",
            "Downloadable presentation file",
            "Narrative speaker notes",
        ]),
        ("Limitations", ["limitation", "resource", "time", "memory"], [
            "Large files take longer",
            "Local models need memory",
            "Design customization is limited",
            "AI output may vary",
        ]),
        ("Future Scope", ["future", "scope", "improvement", "deploy"], [
            "Better slide design",
            "Image and diagram automation",
            "Multi-model support",
            "Cloud deployment options",
        ]),
    ]

    content_slots = max(1, slide_count - 2)
    chosen_specs = slide_specs[:content_slots]
    slides = [{
        "slide_number": 1,
        "slide_type": "title",
        "title": title,
        "subtitle": f"Project explanation in {style.replace('_', ' ')} style",
        "bullet_points": [],
        "speaker_notes": f"This presentation explains the project workflow and implementation of {title}.",
        "visual_cue": "Clean architecture overview with system modules",
        "section_type": "introduction",
        "layout": "title_bullets",
        "duration_seconds": 30,
    }]

    for index, (slide_title, search_terms, fallback) in enumerate(chosen_specs, start=2):
        matches = _extract_matching_sentences(text, search_terms, limit=4)
        if slide_title == "Code Modules" and section_titles:
            matches = section_titles[:4]
        if slide_title in {"Results / Output", "Limitations", "Future Scope"} and keywords:
            matches = matches or keywords[:4]

        bullet_points = _compact_points(matches, fallback)
        slides.append(
            {
                "slide_number": index,
                "slide_type": "content",
                "title": slide_title,
                "bullet_points": bullet_points,
                "speaker_notes": " ".join(bullet_points[:2]),
                "visual_cue": f"Diagram or layout for {slide_title.lower()}",
                "duration_seconds": 45,
                "style": style,
                "section_type": classify_section(slide_title, " ".join(bullet_points)),
                "layout": choose_layout(classify_section(slide_title, " ".join(bullet_points)), True, len(bullet_points)),
            }
        )

    slides.append(
        {
            "slide_number": len(slides) + 1,
            "slide_type": "closing",
            "title": "Conclusion",
            "bullet_points": _conclusion_bullets(text, keywords),
            "speaker_notes": "End by summarizing how the project automates document-to-presentation generation.",
            "visual_cue": "Closing summary with project highlights",
            "section_type": "conclusion",
            "layout": "visual_focus",
            "duration_seconds": 30,
        }
    )

    slides = [_ensure_slide_defaults(slide, text) for slide in slides]

    narrative = {
        "title": title,
        "subtitle": "AI powered document to presentation system",
        "slides": slides,
        "flow": ["Introduction"] + [slide.get("section_type", "content").title() for slide in slides[1:-1]] + ["Conclusion"],
        "document_mode": "project",
    }
    return json.dumps(narrative, ensure_ascii=False)


def build_simple_narrative(doc: ParsedDocument, slide_count: int = 8, style: str = "ted_talk") -> str:
    if _contains_project_markers(doc.cleaned_text):
        return _build_project_narrative(doc, slide_count, style)

    title = _normalize_title(doc.filename)
    blocks = _section_blocks(doc)
    document_mode = infer_document_mode(doc.cleaned_text)
    for block in blocks:
        block["section_type"] = classify_section(block["title"], block["content"])

    max_content_slides = max(1, slide_count - 2)
    flow = plan_slide_flow([block["section_type"] for block in blocks], document_mode, slide_count)
    selected_blocks = []
    used_indexes = set()

    for desired_type in flow:
        chosen_index = next(
            (index for index, block in enumerate(blocks) if block["section_type"] == desired_type and index not in used_indexes),
            None,
        )
        if chosen_index is None:
            chosen_index = next((index for index in range(len(blocks)) if index not in used_indexes), None)
        if chosen_index is None:
            break
        used_indexes.add(chosen_index)
        selected_blocks.append(blocks[chosen_index])

    selected_blocks = selected_blocks[:max_content_slides]
    slides = []

    slides.append(
        {
            "slide_number": 1,
            "slide_type": "title",
            "title": title,
            "subtitle": f"Generated from {doc.filename}",
            "bullet_points": [],
            "speaker_notes": f"This presentation summarizes {doc.filename}.",
            "visual_cue": "Opening slide with a crisp overview of the topic",
            "section_type": "introduction",
            "layout": "title_bullets",
            "duration_seconds": 30,
        }
    )

    for index, block in enumerate(selected_blocks, start=2):
        bullets = _fallback_bullets(block["content"])
        section_type = block.get("section_type", "definition")
        visual_cue = {
            "introduction": "Overview layout with strong title and context",
            "problem": "Problem framing visual with highlighted pain points",
            "objective": "Goal slide with focus markers and outcome cues",
            "definition": "Concept illustration with labels or icon support",
            "methodology": "Workflow or two-column process explanation",
            "example": "Example-driven slide with supporting visual or scenario",
            "results": "Outcome summary with emphasis on impact",
            "conclusion": "Closing slide with concise recap",
        }.get(section_type, "Supporting visual for the main content")
        layout = choose_layout(section_type, "visual" in visual_cue.lower() or "workflow" in visual_cue.lower(), len(bullets))

        slides.append(
            {
                "slide_number": index,
                "slide_type": "content",
                "title": block["title"][:80],
                "bullet_points": bullets,
                "speaker_notes": _build_speaker_notes(block["title"][:80], bullets, section_type),
                "visual_cue": visual_cue,
                "duration_seconds": 45,
                "style": style,
                "section_type": section_type,
                "layout": layout,
            }
        )

    keywords = _top_keywords(doc.cleaned_text)
    slides.append(
        {
            "slide_number": len(slides) + 1,
            "slide_type": "closing",
            "title": "Conclusion",
            "bullet_points": _conclusion_bullets(doc.cleaned_text, keywords),
            "speaker_notes": "Close by reinforcing the main takeaway from the document.",
            "visual_cue": "Final takeaway slide with concise summary points",
            "section_type": "conclusion",
            "layout": "visual_focus",
            "duration_seconds": 30,
        }
    )

    slides = [
        _ensure_slide_defaults(slide, next((block["content"] for block in selected_blocks if block["title"][:80] == slide.get("title")), doc.cleaned_text))
        for slide in slides
    ]

    narrative = {
        "title": title,
        "subtitle": f"Simple {style.replace('_', ' ')} presentation",
        "slides": slides,
        "flow": ["Introduction"] + [slide.get("section_type", "content").title() for slide in slides[1:-1]] + ["Conclusion"],
        "document_mode": document_mode,
    }
    return json.dumps(narrative, ensure_ascii=False)
