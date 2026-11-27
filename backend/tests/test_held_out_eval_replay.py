import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from eval.eval_suite import run_held_out_replay


def test_held_out_eval_replay_suite():
    """
    Offline regression test exercising the 20-case frozen held-out benchmark.
    Tests AST query security, tabular execution against fixtures, and
    strict semantic boundaries without live external API dependencies.
    """
    total_passed, total_cases = run_held_out_replay()
    assert total_cases == 20
    assert total_passed == 20, f"Expected 20/20 held-out cases to pass, got {total_passed}"
