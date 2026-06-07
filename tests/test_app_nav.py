import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _resolve_initial_stage


def test_goto_writing_from_welcome_enters_setup():
    assert _resolve_initial_stage("welcome", {"goto": "writing"}) == "setup"


def test_no_param_keeps_welcome():
    assert _resolve_initial_stage("welcome", {}) == "welcome"


def test_goto_does_not_override_midflow():
    assert _resolve_initial_stage("results", {"goto": "writing"}) == "results"


def test_unknown_goto_value_ignored():
    assert _resolve_initial_stage("welcome", {"goto": "nope"}) == "welcome"
