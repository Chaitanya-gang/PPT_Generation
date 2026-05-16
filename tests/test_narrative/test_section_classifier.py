from src.narrative.section_classifier import (
    choose_layout,
    classify_section,
    plan_slide_flow,
    summarize_to_bullets,
)


def test_classify_section_detects_problem():
    label = classify_section(
        "Problem Statement",
        "The current workflow is slow and creates a major challenge for users.",
    )
    assert label == "problem"


def test_plan_slide_flow_prefers_structured_order():
    flow = plan_slide_flow(
        ["results", "introduction", "methodology", "conclusion", "problem"],
        document_mode="project",
        slide_count=7,
    )
    assert flow[:4] == ["introduction", "problem", "methodology", "results"]


def test_summarize_to_bullets_fills_missing_content():
    bullets = summarize_to_bullets("This system automates slide creation. It improves consistency for users.")
    assert len(bullets) >= 1
    assert bullets[0]


def test_choose_layout_varies_for_visual_content():
    assert choose_layout("methodology", has_visual=True, bullet_count=3) == "two_column"
    assert choose_layout("results", has_visual=False, bullet_count=2) == "title_big_number"
