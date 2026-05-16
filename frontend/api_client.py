"""
Frontend API helpers for the Streamlit UI.
"""

from typing import Any, Dict, List

import requests

from frontend.config import API_BASE_URL


def _raise_for_status(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = None
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = response.text or str(exc)
        raise requests.HTTPError(detail, response=response) from exc


def get_styles_metadata() -> Dict[str, Any]:
    try:
        response = requests.get(f"{API_BASE_URL}/api/styles", timeout=10)
        _raise_for_status(response)
        return response.json()
    except Exception:
        return {
            "presentation_styles": {},
            "themes": ["vibrant", "ocean", "sunset", "forest", "royal"],
        }


def upload_document(file) -> Dict[str, Any]:
    files = {"file": (file.name, file.getvalue())}
    response = requests.post(f"{API_BASE_URL}/api/upload", files=files, timeout=60)
    _raise_for_status(response)
    return response.json()


def generate_outline(file_id: str, style: str, slide_count: int, use_ollama: bool) -> Dict[str, Any]:
    payload = {
        "file_id": file_id,
        "style": style,
        "slide_count": slide_count,
        "use_ollama": use_ollama,
    }
    response = requests.post(f"{API_BASE_URL}/api/outline", json=payload, timeout=180)
    _raise_for_status(response)
    return response.json()


def generate_presentation(
    file_id: str,
    style: str,
    theme: str,
    slide_count: int,
    use_ollama: bool,
    image_mode: bool,
    diagram_mode: bool,
    include_speaker_notes: bool,
    export_formats: List[str],
) -> Dict[str, Any]:
    payload = {
        "file_id": file_id,
        "style": style,
        "theme": theme,
        "slide_count": slide_count,
        "use_ollama": use_ollama,
        "image_mode": image_mode,
        "diagram_mode": diagram_mode,
        "include_speaker_notes": include_speaker_notes,
        "export_formats": export_formats,
    }
    response = requests.post(f"{API_BASE_URL}/api/generate", json=payload, timeout=300)
    _raise_for_status(response)
    return response.json()


def generate_from_outline(
    file_id: str,
    theme: str,
    image_mode: bool,
    diagram_mode: bool,
    include_speaker_notes: bool,
    export_formats: List[str],
    narrative_json: Dict[str, Any],
    doc_summary: Any,
) -> Dict[str, Any]:
    payload = {
        "file_id": file_id,
        "theme": theme,
        "image_mode": image_mode,
        "diagram_mode": diagram_mode,
        "include_speaker_notes": include_speaker_notes,
        "export_formats": export_formats or None,
        "narrative_json": narrative_json,
        "doc_summary": doc_summary,
    }
    response = requests.post(f"{API_BASE_URL}/api/generate_from_outline", json=payload, timeout=300)
    _raise_for_status(response)
    return response.json()


def run_slide_action(action: str, slide: Dict[str, Any], presentation_title: str) -> Dict[str, Any]:
    payload = {
        "action": action,
        "slide": slide,
        "presentation_title": presentation_title,
    }
    response = requests.post(f"{API_BASE_URL}/api/slide_action", json=payload, timeout=180)
    _raise_for_status(response)
    return response.json()


def chat_with_slide(question: str, slide: Dict[str, Any], presentation_title: str) -> Dict[str, Any]:
    payload = {
        "question": question,
        "slide": slide,
        "presentation_title": presentation_title,
    }
    response = requests.post(f"{API_BASE_URL}/api/chat_with_slide", json=payload, timeout=180)
    _raise_for_status(response)
    return response.json()


def download_file(kind: str, file_id: str) -> bytes:
    response = requests.get(f"{API_BASE_URL}/api/download/{kind}/{file_id}", timeout=120)
    _raise_for_status(response)
    return response.content
