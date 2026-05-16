"""
Outline editing, slide actions, and generation UI.
"""

import json
from copy import deepcopy

import streamlit as st

from frontend.api_client import (
    chat_with_slide,
    download_file,
    generate_from_outline,
    generate_outline,
    run_slide_action,
    upload_document,
)


st.set_page_config(page_title="newd2p - Slide Studio", page_icon="🪄", layout="wide")


def _load_css() -> None:
    st.markdown(
        """
        <style>
        .slide-card {
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 18px;
            padding: 1rem 1rem 0.4rem 1rem;
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.04), rgba(15, 23, 42, 0.01));
            margin-bottom: 1rem;
        }
        .slide-meta {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin: 0.35rem 0 0.9rem 0;
        }
        .slide-chip {
            font-size: 0.78rem;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            background: #e2e8f0;
            color: #0f172a;
            font-weight: 600;
        }
        .chat-answer {
            border-left: 4px solid #0ea5e9;
            padding: 0.75rem 0.9rem;
            background: #f8fafc;
            border-radius: 0 12px 12px 0;
            margin-top: 0.4rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalize_slide(slide: dict, slide_number: int) -> dict:
    normalized = deepcopy(slide)
    normalized["slide_number"] = slide_number
    normalized["title"] = normalized.get("title", f"Slide {slide_number}")
    normalized["slide_type"] = normalized.get("slide_type", "content")
    normalized["bullet_points"] = normalized.get("bullet_points", [])
    normalized["speaker_notes"] = normalized.get("speaker_notes", "")
    normalized["visual_cue"] = normalized.get("visual_cue", "")
    normalized["section_type"] = normalized.get("section_type", "")
    normalized["layout"] = normalized.get("layout", "title_bullets")
    normalized["duration_seconds"] = int(normalized.get("duration_seconds", 45) or 45)
    return normalized


def _store_narrative(narrative: dict) -> None:
    slides = []
    for index, slide in enumerate(narrative.get("slides", []), start=1):
        slides.append(_normalize_slide(slide, index))
    narrative["slides"] = slides
    st.session_state["outline_narrative"] = narrative


def _move_slide(index: int, direction: int) -> None:
    narrative = deepcopy(st.session_state["outline_narrative"])
    slides = narrative.get("slides", [])
    target = index + direction
    if target < 0 or target >= len(slides):
        return
    slides[index], slides[target] = slides[target], slides[index]
    for slide_number, slide in enumerate(slides, start=1):
        slide["slide_number"] = slide_number
    _store_narrative(narrative)


def _update_slide_field(index: int, field: str, value) -> None:
    narrative = deepcopy(st.session_state["outline_narrative"])
    narrative["slides"][index][field] = value
    _store_narrative(narrative)


def _apply_slide_action(index: int, action: str) -> None:
    narrative = deepcopy(st.session_state["outline_narrative"])
    slide = narrative["slides"][index]
    response = run_slide_action(action, slide, narrative.get("title", "Presentation"))
    narrative["slides"][index] = _normalize_slide(response["slide"], slide["slide_number"])
    _store_narrative(narrative)
    st.success(f"Slide {slide['slide_number']} updated with `{action}`.")


def _render_slide_card(index: int, slide: dict) -> None:
    slide_number = slide["slide_number"]
    header = f"Slide {slide_number}: {slide.get('title', f'Slide {slide_number}')}"
    with st.expander(header, expanded=index < 2):
        st.markdown("<div class='slide-card'>", unsafe_allow_html=True)
        st.markdown(
            (
                "<div class='slide-meta'>"
                f"<span class='slide-chip'>{slide.get('slide_type', 'content')}</span>"
                f"<span class='slide-chip'>{slide.get('section_type', 'unclassified') or 'unclassified'}</span>"
                f"<span class='slide-chip'>{slide.get('layout', 'title_bullets')}</span>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        title_col, type_col = st.columns([3, 1.2])
        with title_col:
            title = st.text_input("Title", value=slide.get("title", ""), key=f"title_{slide_number}")
        with type_col:
            slide_type = st.selectbox(
                "Type",
                ["title", "content", "transition", "chart", "closing"],
                index=["title", "content", "transition", "chart", "closing"].index(slide.get("slide_type", "content"))
                if slide.get("slide_type", "content") in ["title", "content", "transition", "chart", "closing"]
                else 1,
                key=f"type_{slide_number}",
            )

        meta_col1, meta_col2, meta_col3 = st.columns(3)
        with meta_col1:
            section_type = st.selectbox(
                "Section Type",
                ["introduction", "problem", "objective", "definition", "methodology", "example", "results", "conclusion"],
                index=max(
                    0,
                    ["introduction", "problem", "objective", "definition", "methodology", "example", "results", "conclusion"].index(slide.get("section_type"))
                    if slide.get("section_type") in ["introduction", "problem", "objective", "definition", "methodology", "example", "results", "conclusion"]
                    else 0,
                ),
                key=f"section_{slide_number}",
            )
        with meta_col2:
            layout = st.selectbox(
                "Layout",
                ["title_bullets", "two_column", "visual_focus", "title_big_number"],
                index=["title_bullets", "two_column", "visual_focus", "title_big_number"].index(slide.get("layout", "title_bullets"))
                if slide.get("layout", "title_bullets") in ["title_bullets", "two_column", "visual_focus", "title_big_number"]
                else 0,
                key=f"layout_{slide_number}",
            )
        with meta_col3:
            duration = st.number_input(
                "Duration (sec)",
                min_value=15,
                max_value=180,
                value=int(slide.get("duration_seconds", 45) or 45),
                step=5,
                key=f"duration_{slide_number}",
            )

        bullets_text = st.text_area(
            "Bullets",
            value="\n".join(slide.get("bullet_points", [])),
            height=120,
            help="One bullet per line.",
            key=f"bullets_{slide_number}",
        )
        visual_cue = st.text_area(
            "Visual Direction",
            value=slide.get("visual_cue", ""),
            height=90,
            key=f"visual_{slide_number}",
        )
        speaker_notes = st.text_area(
            "Explanation / Speaker Notes",
            value=slide.get("speaker_notes", ""),
            height=110,
            key=f"notes_{slide_number}",
        )

        bullet_points = [line.strip() for line in bullets_text.splitlines() if line.strip()]
        _update_slide_field(index, "title", title)
        _update_slide_field(index, "slide_type", slide_type)
        _update_slide_field(index, "section_type", section_type)
        _update_slide_field(index, "layout", layout)
        _update_slide_field(index, "duration_seconds", duration)
        _update_slide_field(index, "bullet_points", bullet_points)
        _update_slide_field(index, "visual_cue", visual_cue)
        _update_slide_field(index, "speaker_notes", speaker_notes)

        action_col1, action_col2, action_col3, action_col4, action_col5 = st.columns(5)
        with action_col1:
            if st.button("Regenerate Slide", key=f"regen_{slide_number}", use_container_width=True):
                _apply_slide_action(index, "regenerate")
                st.rerun()
        with action_col2:
            if st.button("Improve Bullets", key=f"improve_{slide_number}", use_container_width=True):
                _apply_slide_action(index, "improve_bullets")
                st.rerun()
        with action_col3:
            if st.button("Simplify", key=f"simplify_{slide_number}", use_container_width=True):
                _apply_slide_action(index, "simplify")
                st.rerun()
        with action_col4:
            if st.button("Move Up", key=f"up_{slide_number}", use_container_width=True):
                _move_slide(index, -1)
                st.rerun()
        with action_col5:
            if st.button("Move Down", key=f"down_{slide_number}", use_container_width=True):
                _move_slide(index, 1)
                st.rerun()

        question = st.text_input(
            "Chat with this slide",
            value="",
            placeholder="Ask: Explain this slide, simplify it, or tell me the key idea.",
            key=f"question_{slide_number}",
        )
        if st.button("Ask", key=f"ask_{slide_number}"):
            response = chat_with_slide(
                question or "Explain this slide simply.",
                st.session_state["outline_narrative"]["slides"][index],
                st.session_state["outline_narrative"].get("title", "Presentation"),
            )
            st.session_state[f"answer_{slide_number}"] = response["answer"]

        answer = st.session_state.get(f"answer_{slide_number}")
        if answer:
            st.markdown(f"<div class='chat-answer'>{answer}</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


_load_css()

st.title("Slide Studio")
st.caption("Build a stronger narrative, tune each slide, and generate the final deck when the structure feels right.")
st.markdown("---")

col_left, col_right = st.columns([1.15, 1])

with col_left:
    st.subheader("Document")
    uploaded_file = st.file_uploader(
        "Upload a document or use an existing file ID",
        type=["pdf", "docx", "doc", "txt"],
    )
    file_id_input = st.text_input("Existing file ID", value=st.session_state.get("outline_file_id", ""))
    if uploaded_file and st.button("Upload Document", use_container_width=True):
        with st.spinner("Uploading document..."):
            data = upload_document(uploaded_file)
        st.session_state["outline_file_id"] = data["file_id"]
        st.success(f"Uploaded. File ID: {data['file_id']}")

with col_right:
    st.subheader("Outline Setup")
    style = st.selectbox(
        "Presentation style",
        ["ted_talk", "executive_summary", "training", "storytelling", "pitch_deck"],
        format_func=lambda value: value.replace("_", " ").title(),
    )
    slide_count = st.slider("Target slides", 6, 15, 8)
    use_ollama = st.toggle("Use LLM when available", value=True)

file_id = st.session_state.get("outline_file_id") or file_id_input.strip()

if file_id:
    st.info(f"Working with file ID: {file_id}")

    if st.button("Generate Smart Outline", type="primary"):
        with st.spinner("Creating outline with classification and structured flow..."):
            data = generate_outline(file_id, style, slide_count, use_ollama)
        narrative = json.loads(data["narrative"])
        _store_narrative(narrative)
        st.session_state["outline_file_id"] = file_id
        st.session_state["outline_doc_summary"] = data.get("document_summary", "")
        st.success("Outline ready. You can now edit the slides like a mini slide editor.")

narrative = st.session_state.get("outline_narrative")
doc_summary = st.session_state.get("outline_doc_summary")

if narrative:
    st.markdown("---")
    top_col1, top_col2 = st.columns([2.2, 1])
    with top_col1:
        st.subheader(narrative.get("title", "Presentation"))
        flow = narrative.get("flow", [])
        if flow:
            st.caption("Structured flow: " + " → ".join(flow))
    with top_col2:
        st.metric("Slides", len(narrative.get("slides", [])))

    for index, slide in enumerate(narrative.get("slides", [])):
        _render_slide_card(index, slide)

    st.markdown("---")
    st.subheader("Generate Presentation")
    settings_col1, settings_col2, settings_col3 = st.columns(3)
    with settings_col1:
        theme = st.selectbox("Theme", ["vibrant", "ocean", "sunset", "forest", "royal"], index=1)
    with settings_col2:
        image_mode = st.checkbox("Generate images", value=False)
    with settings_col3:
        diagram_mode = st.checkbox("Enable diagrams", value=True)

    export_pdf = st.checkbox("Export PDF", value=False)
    export_markdown = st.checkbox("Export Markdown", value=False)

    if st.button("Generate Final Deck", type="primary", use_container_width=True):
        export_formats = []
        if export_pdf:
            export_formats.append("pdf")
        if export_markdown:
            export_formats.append("markdown")

        with st.spinner("Building presentation from the edited outline..."):
            response = generate_from_outline(
                file_id=file_id,
                theme=theme,
                image_mode=image_mode,
                diagram_mode=diagram_mode,
                include_speaker_notes=True,
                export_formats=export_formats,
                narrative_json=st.session_state["outline_narrative"],
                doc_summary=doc_summary or "",
            )

        st.success("Presentation generated.")
        download_col1, download_col2 = st.columns(2)
        with download_col1:
            ppt_bytes = download_file("ppt", file_id)
            st.download_button(
                "Download PPT",
                data=ppt_bytes,
                file_name=f"{file_id}_presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )
        with download_col2:
            json_bytes = download_file("json", file_id)
            st.download_button(
                "Download JSON",
                data=json_bytes,
                file_name=f"{file_id}_handover.json",
                mime="application/json",
                use_container_width=True,
            )
