"""Testes para templates HTML extraídos das views de grafo e PDF."""

import re

import pytest

from src.views.knowledge.graph_template import generate_graph_html
from src.views.pdf_reader.pdf_template import generate_pdf_viewer_html


def test_graph_template_loaded_from_assets_and_has_structure():
    html = generate_graph_html({"nodes": [], "links": [], "clusters": []})
    assert "<!DOCTYPE html>" in html
    assert "d3" in html.lower()
    assert "Estruturas de Saber" in html


def test_pdf_template_loaded_from_assets_and_has_structure():
    html = generate_pdf_viewer_html("aGVsbG8=", "Obra de teste")
    assert "<!DOCTYPE html>" in html
    assert "pdf.js" in html.lower()
    assert "Leitor Hupomnemata" in html


@pytest.mark.parametrize("template_func,kwargs", [
    (generate_graph_html, {"graph_data": {"nodes": [], "links": [], "clusters": []}}),
    (generate_pdf_viewer_html, {"pdf_base64": "aGVsbG8=", "title": "T"}),
])
def test_no_placeholder_remains(template_func, kwargs):
    html = template_func(**kwargs)
    assert not re.search(r"__[A-Z_]+__", html), "Placeholder remanescente encontrado no HTML"


@pytest.mark.parametrize("theme_mode,expected_bg", [
    ("dark", "#121212"),
    ("light", "#F9F9FB"),
])
def test_graph_theme_mode_reflected(theme_mode, expected_bg):
    html = generate_graph_html({"nodes": [], "links": [], "clusters": []}, theme_mode=theme_mode)
    assert f'data-theme="{theme_mode}"' in html
    assert f"background-color: {expected_bg}" in html


@pytest.mark.parametrize("theme_mode,expected_bg", [
    ("dark", "#121212"),
    ("light", "#F9F9FB"),
])
def test_pdf_theme_mode_reflected(theme_mode, expected_bg):
    html = generate_pdf_viewer_html("aGVsbG8=", "T", theme_mode=theme_mode)
    assert f'data-theme="{theme_mode}"' in html
    assert f"background-color: {expected_bg}" in html


def test_pdf_title_with_script_tag_is_escaped():
    malicious_title = "<script>alert('xss')</script>"
    html = generate_pdf_viewer_html("aGVsbG8=", malicious_title)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "</title>" in html


def test_graph_node_label_with_script_closing_tag_is_escaped():
    payload = "</script><script>alert('xss')</script>"
    data = {
        "nodes": [
            {"id": "fragment_1", "label": payload, "type": "fragment"},
        ],
        "links": [],
        "clusters": [],
    }
    html = generate_graph_html(data)
    # JSON string literal containing the raw closing script tag must not exist
    assert '"</script>"' not in html
    # The escaped sequence must be present in the injected JSON
    assert r"<\/script>" in html
    # The original node id is still reachable
    assert "fragment_1" in html


def test_graph_payload_containing_placeholder_token_is_not_replaced():
    data = {"nodes": [{"id": "n1", "label": "__THEME_MODE__"}]}
    html = generate_graph_html(data, theme_mode="light")
    assert '"__THEME_MODE__"' in html


def test_pdf_annotations_cannot_break_script_tag():
    annotations = [
        {"id": 1, "note": "</script><script>alert('xss')</script>"}
    ]
    html = generate_pdf_viewer_html("aGVsbG8=", "Título", annotations=annotations)
    assert '"</script>"' not in html
    assert r"<\/script>" in html


def test_pdf_title_does_not_collide_with_placeholders():
    html = generate_pdf_viewer_html("aGVsbG8=", "__THEME_MODE__")
    assert "&quot;__THEME_MODE__&quot;" in html or "__THEME_MODE__" in html
    assert 'data-theme="dark"' in html
