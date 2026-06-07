import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.streamlit_design import _render_top_nav


def test_nav_has_three_sections():
    html = _render_top_nav("home")
    assert ">Writing<" in html
    assert ">Reading<" in html
    assert ">Flashcards<" in html


def test_nav_writing_link_uses_goto():
    assert 'href="/?goto=writing"' in _render_top_nav("home")


def test_nav_reading_link_to_page():
    assert 'href="/Reading_Comprehension"' in _render_top_nav("home")


def test_nav_flashcards_external():
    assert "http://localhost:5002" in _render_top_nav("home")


def test_nav_active_highlight_reading():
    html = _render_top_nav("reading")
    assert 'class="sle-nav-link active" href="/Reading_Comprehension"' in html


def test_nav_active_highlight_writing():
    html = _render_top_nav("writing")
    assert 'class="sle-nav-link active" href="/?goto=writing"' in html


def test_nav_hides_sidebar_pagelist():
    assert "stSidebarNav" in _render_top_nav("home")
