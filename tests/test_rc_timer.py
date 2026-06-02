import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.streamlit_design import _timer_html


def test_start_ts_embedded():
    html = _timer_html(total_seconds=450, start_ts=1717234567.0)
    assert "1717234567.0" in html


def test_total_seconds_embedded():
    html = _timer_html(total_seconds=450, start_ts=1717234567.123)
    assert "var TOTAL_SECS = 450" in html


def test_sticky_bar_present():
    html = _timer_html(total_seconds=450, start_ts=1717234567.123)
    assert "rc-timer-bar" in html


def test_modal_present():
    html = _timer_html(total_seconds=450, start_ts=1717234567.0)
    assert "rc-timer-modal" in html


def test_uses_parent_document():
    html = _timer_html(total_seconds=450, start_ts=1717234567.0)
    assert "window.parent" in html


def test_interval_guard_present():
    html = _timer_html(total_seconds=450, start_ts=1717234567.123)
    assert "__rcTimerIntervalId" in html


def test_urgency_threshold_present():
    html = _timer_html(total_seconds=450, start_ts=1717234567.123)
    assert "<= 30" in html
