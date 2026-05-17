"""
newd2p - Generate Endpoint
"""

import json
from pathlib import Path
from typing import List, Optional, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import get_settings
from src.llm.prompt_templates import (
    EXPLAIN_SLIDE_PROMPT,
    NARRATIVE_PROMPT,
    SLIDE_ACTION_PROMPT,
    SLIDE_CHAT_PROMPT,
    SUMMARY_PROMPT,
    SYSTEM_PROMPT,
)
from src.llm.provider_factory import get_llm_provider
from src.narrative.section_classifier import choose_layout, classify_section, summarize_to_bullets
from src.output.exporter import convert_ppt_to_pdf
from src.output.json_builder import build_handover_json
from src.output.markdown_builder import build_markdown_from_narrative
from src.parsers.parser_factory import parse_document
from src.ppt.builder import PPTBuilder
from src.rag.pipeline import RAGPipeline
from src.simple_generation import build_simple_narrative, build_simple_summary
from src.utils.logger import get_logger

logger = get_logger("api_generate")
router = APIRouter()
settings = get_settings()


class GenerateRequest(BaseModel):
    file_id: str
    style: str = "ted_talk"
    theme: str = "vibrant"
    slide_count: int = 8
    use_ollama: bool = True
    image_mode: bool = False
    diagram_mode: bool = False
    include_speaker_notes: bool = True
    export_formats: Optional[List[str]] = None


class OutlineRequest(BaseModel):
    file_id: str
    style: str = "ted_talk"
    slide_count: int = 8
    use_ollama: bool = True


class GenerateFromOutlineRequest(BaseModel):
    file_id: str
    theme: str = "vibrant"
    image_mode: bool = False
    diagram_mode: bool = False
    include_speaker_notes: bool = True
    export_formats: Optional[List[str]] = None
    narrative_json: dict
    doc_summary: Any


class ExplainSlideRequest(BaseModel):
    file_id: str
    slide_number: int


class SlideActionRequest(BaseModel):
    action: str
    slide: dict
    presentation_title: str = "Presentation"


class SlideChatRequest(BaseModel):
    question: str
    slide: dict
    presentation_title: str = "Presentation"


ALLOWED_SLIDE_ACTIONS = {"regenerate", "improve_bullets", "simplify"}


def _get_uploaded_file(file_id: str) -> tuple[str, str, str]:
    upload_dir = Path(settings.upload_dir) / file_id
    if not upload_dir.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    files = list(upload_dir.iterdir())
    if not files:
        raise HTTPException(status_code=404, detail="No file found in upload directory")

    file_path = str(files[0])
    file_ext = files[0].suffix.lower()
    filename = files[0].name
    return file_path, file_ext, filename


def _build_local_presentation(
    *,
    file_id: str,
    filename: str,
    narrative: str,
    summary: str,
    theme: str,
    image_mode: bool,
    diagram_mode: bool,
    include_speaker_notes: bool,
    export_formats: Optional[List[str]],
) -> dict:
    ppt_path = f"{settings.ppt_output_dir}/{file_id}_presentation.pptx"
    builder = PPTBuilder(
        theme_name=theme,
        image_mode=image_mode,
        diagram_mode=diagram_mode,
        include_speaker_notes=include_speaker_notes,
    )
    builder.build_from_json(narrative, ppt_path)

    json_path = f"{settings.json_output_dir}/{file_id}_handover.json"
    build_handover_json(
        narrative_json=narrative,
        doc_summary=summary,
        file_id=file_id,
        filename=filename,
        output_path=json_path,
    )

    response = {
        "status": "completed",
        "file_id": file_id,
        "ppt_path": ppt_path,
        "json_path": json_path,
        "document_summary": json.loads(summary) if summary.startswith("{") else summary,
        "theme": theme,
    }

    export_formats = export_formats or []
    if "markdown" in export_formats:
        markdown_output = f"{settings.markdown_output_dir}/{file_id}_presentation.md"
        response["markdown_path"] = build_markdown_from_narrative(narrative, markdown_output)

    if "pdf" in export_formats:
        pdf_output = f"{settings.pdf_output_dir}/{file_id}_presentation.pdf"
        pdf_path = convert_ppt_to_pdf(ppt_path, pdf_output)
        if pdf_path:
            response["pdf_path"] = pdf_path

    return response


def _extract_json_object(raw_text: str, fallback: str) -> str:
    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(raw_text[start:end])
            return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        pass
    return fallback


def _safe_json_loads(raw_text: str, fallback):
    try:
        return json.loads(raw_text)
    except Exception:
        try:
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw_text[start:end])
        except Exception:
            pass
    return fallback


def _complete_slide(slide: dict) -> dict:
    completed = dict(slide)
    completed["title"] = (completed.get("title") or "Untitled Slide").strip()
    completed["slide_type"] = completed.get("slide_type", "content")
    completed["slide_number"] = int(completed.get("slide_number", 1) or 1)
    section_type = completed.get("section_type") or classify_section(
        completed["title"], " ".join(completed.get("bullet_points", []))
    )
    completed["section_type"] = section_type

    if completed["slide_type"] == "title":
        completed["bullet_points"] = []
    else:
        source_text = " ".join(
            [
                completed.get("title", ""),
                " ".join(completed.get("bullet_points", [])),
                completed.get("speaker_notes", ""),
                completed.get("visual_cue", ""),
            ]
        )
        completed["bullet_points"] = summarize_to_bullets(source_text, limit=4, max_chars=90)

    if not completed.get("speaker_notes"):
        bullet_summary = " ".join(completed.get("bullet_points", [])[:2])
        completed["speaker_notes"] = f"Explain {completed['title']} clearly. {bullet_summary}".strip()
    if not completed.get("visual_cue"):
        completed["visual_cue"] = f"Supporting visual for {completed['title']}"

    completed["duration_seconds"] = int(completed.get("duration_seconds", 45) or 45)
    completed["layout"] = completed.get("layout") or choose_layout(
        section_type,
        any(token in completed.get("visual_cue", "").lower() for token in ("diagram", "image", "visual", "workflow")),
        len(completed.get("bullet_points", [])),
    )
    return completed


def _apply_slide_action_fallback(action: str, slide: dict) -> dict:
    current = _complete_slide(slide)
    bullets = current.get("bullet_points", [])

    if action == "improve_bullets":
        improved = []
        for bullet in bullets:
            cleaned = bullet.rstrip(".")
            if len(cleaned) > 70:
                cleaned = cleaned[:67].rstrip(" ,;:") + "..."
            improved.append(cleaned)
        current["bullet_points"] = improved or summarize_to_bullets(current.get("speaker_notes", ""), limit=4)
    elif action == "simplify":
        simplified = []
        for bullet in bullets:
            words = bullet.split()
            simplified.append(" ".join(words[:8]))
        current["bullet_points"] = simplified or summarize_to_bullets(current.get("speaker_notes", ""), limit=3, max_chars=70)
        current["speaker_notes"] = "Explain this in simple terms and keep the language easy to follow."
    else:
        source = " ".join([current.get("title", ""), current.get("speaker_notes", ""), current.get("visual_cue", "")])
        current["bullet_points"] = summarize_to_bullets(source, limit=4)
        if current["slide_type"] != "title":
            current["title"] = current["title"] if len(current["title"]) <= 60 else current["title"][:57].rstrip() + "..."
            current["speaker_notes"] = f"Present {current['title']} as a refreshed, clearer slide."

    return _complete_slide(current)


def _llm_available() -> bool:
    try:
        llm = get_llm_provider()
        return not hasattr(llm, "is_available") or llm.is_available()
    except Exception:
        return False


def _generate_with_ollama(doc, style: str, slide_count: int) -> tuple[str, str]:
    llm = get_llm_provider()
    if hasattr(llm, "is_available") and not llm.is_available():
        raise RuntimeError("Ollama is not available")

    rag = RAGPipeline()
    result = rag.process_document(doc)
    
    summary_raw = result["summary"]
    narrative_raw = rag.generate_narrative(
        context=result["context"],
        style=style,
        slide_count=slide_count,
    )

    fallback_summary = build_simple_summary(doc)
    fallback_narrative = build_simple_narrative(doc, slide_count, style)
    summary = _extract_json_object(summary_raw, fallback_summary)
    narrative = _extract_json_object(narrative_raw, fallback_narrative)
    return narrative, summary


@router.post("/outline")
async def generate_outline(req: OutlineRequest):
    file_path, file_ext, _ = _get_uploaded_file(req.file_id)

    try:
        doc = parse_document(file_path, req.file_id, file_ext)
        generation_mode = "simple"
        ollama_model = None
        if req.use_ollama:
            try:
                narrative, summary = _generate_with_ollama(doc, req.style, req.slide_count)
                generation_mode = "ollama"
                ollama_model = settings.ollama_model
            except Exception as exc:
                logger.warning(f"Ollama outline generation failed, using simple fallback: {exc}")
                narrative = build_simple_narrative(doc, req.slide_count, req.style)
                summary = build_simple_summary(doc)
        else:
            narrative = build_simple_narrative(doc, req.slide_count, req.style)
            summary = build_simple_summary(doc)

        return {
            "file_id": req.file_id,
            "narrative": narrative,
            "document_summary": summary,
            "style": req.style,
            "slide_count": req.slide_count,
            "generation_mode": generation_mode,
            "ollama_model": ollama_model,
        }
    except Exception as e:
        logger.error(f"Outline generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate_from_outline")
async def generate_from_outline(req: GenerateFromOutlineRequest):
    file_path, file_ext, filename = _get_uploaded_file(req.file_id)

    try:
        parse_document(file_path, req.file_id, file_ext)
        narrative_str = json.dumps(req.narrative_json)
        summary = req.doc_summary if isinstance(req.doc_summary, str) else json.dumps(req.doc_summary)
        return _build_local_presentation(
            file_id=req.file_id,
            filename=filename,
            narrative=narrative_str,
            summary=summary,
            theme=req.theme,
            image_mode=req.image_mode,
            diagram_mode=req.diagram_mode,
            include_speaker_notes=req.include_speaker_notes,
            export_formats=req.export_formats,
        )
    except Exception as e:
        logger.error(f"Generate from outline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain_slide")
async def explain_slide(req: ExplainSlideRequest):
    handover_path = Path(settings.json_output_dir) / f"{req.file_id}_handover.json"
    if not handover_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Handover JSON not found for file_id {req.file_id}. Generate a presentation first.",
        )

    try:
        with handover_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read handover JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to read handover JSON")

    slides = data.get("slides", [])
    slide = next((s for s in slides if s.get("slide_number") == req.slide_number), None)
    if slide is None:
        raise HTTPException(
            status_code=404,
            detail=f"Slide {req.slide_number} not found for file_id {req.file_id}",
        )

    title = slide.get("title", "")
    bullets = slide.get("bullet_points", [])
    speaker_notes = slide.get("speaker_notes", "")

    llm = get_llm_provider()
    prompt = EXPLAIN_SLIDE_PROMPT.format(
        title=title,
        bullets=json.dumps(bullets, ensure_ascii=False),
        speaker_notes=speaker_notes or "",
    )

    try:
        explanation = llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
    except Exception as e:
        logger.error(f"Explain slide LLM call failed: {e}")
        raise HTTPException(status_code=500, detail="LLM explanation failed")

    return {
        "file_id": req.file_id,
        "slide_number": req.slide_number,
        "title": title,
        "explanation": explanation.strip(),
    }


@router.post("/slide_action")
async def slide_action(req: SlideActionRequest):
    if req.action not in ALLOWED_SLIDE_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {req.action}")

    fallback_slide = _apply_slide_action_fallback(req.action, req.slide)

    if not _llm_available():
        return {"slide": fallback_slide, "mode": "fallback"}

    try:
        llm = get_llm_provider()
        llm_result = llm.generate(
            SLIDE_ACTION_PROMPT.format(
                action=req.action,
                slide_json=json.dumps(_complete_slide(req.slide), ensure_ascii=False, indent=2),
            ),
            system_prompt=SYSTEM_PROMPT,
        )
        updated_slide = _safe_json_loads(llm_result, fallback_slide)
        return {"slide": _complete_slide(updated_slide), "mode": "llm"}
    except Exception as exc:
        logger.warning(f"Slide action fallback used for {req.action}: {exc}")
        return {"slide": fallback_slide, "mode": "fallback"}


@router.post("/chat_with_slide")
async def chat_with_slide(req: SlideChatRequest):
    completed_slide = _complete_slide(req.slide)

    if not _llm_available():
        bullets = completed_slide.get("bullet_points", [])
        summary = " ".join(bullets[:3]) or completed_slide.get("speaker_notes", "")
        return {
            "answer": f"Based on this slide, the key idea is: {summary}",
            "mode": "fallback",
        }

    try:
        llm = get_llm_provider()
        answer = llm.generate(
            SLIDE_CHAT_PROMPT.format(
                presentation_title=req.presentation_title,
                slide_json=json.dumps(completed_slide, ensure_ascii=False, indent=2),
                question=req.question,
            ),
            system_prompt=SYSTEM_PROMPT,
        )
        return {"answer": answer.strip(), "mode": "llm"}
    except Exception as exc:
        logger.warning(f"Slide chat fallback used: {exc}")
        bullets = completed_slide.get("bullet_points", [])
        summary = " ".join(bullets[:3]) or completed_slide.get("speaker_notes", "")
        return {
            "answer": f"Based on this slide, the key idea is: {summary}",
            "mode": "fallback",
        }


@router.post("/generate")
async def generate_presentation(req: GenerateRequest):
    file_path, file_ext, filename = _get_uploaded_file(req.file_id)

    try:
        logger.info(f"Parsing: {filename}")
        doc = parse_document(file_path, req.file_id, file_ext)
        generation_mode = "simple"
        ollama_model = None
        if req.use_ollama:
            try:
                narrative, summary = _generate_with_ollama(doc, req.style, req.slide_count)
                generation_mode = "ollama"
                ollama_model = settings.ollama_model
            except Exception as exc:
                logger.warning(f"Ollama generation failed, using simple fallback: {exc}")
                narrative = build_simple_narrative(doc, req.slide_count, req.style)
                summary = build_simple_summary(doc)
        else:
            narrative = build_simple_narrative(doc, req.slide_count, req.style)
            summary = build_simple_summary(doc)

        response = _build_local_presentation(
            file_id=req.file_id,
            filename=filename,
            narrative=narrative,
            summary=summary,
            theme=req.theme,
            image_mode=req.image_mode,
            diagram_mode=req.diagram_mode,
            include_speaker_notes=req.include_speaker_notes,
            export_formats=req.export_formats,
        )
        response["slides_generated"] = req.slide_count
        response["style"] = req.style
        response["generation_mode"] = generation_mode
        response["ollama_model"] = ollama_model
        return response
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
