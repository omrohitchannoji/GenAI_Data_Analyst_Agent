import os
import sys
import pytest

# Ensure backend root is on path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from eval.eval_suite import run_offline_replay

def test_offline_eval_replay_suite():
    """
    Verifies that the offline deterministic benchmark replay executes cleanly
    and matches the corrected benchmark contract and data semantics score.
    """
    passed, total = run_offline_replay()
    assert total == 40, f"Expected 40 evaluation cases, got {total}"
    assert passed == 40, f"Expected 40 passed cases in replay, got {passed}"
    accuracy = (passed / total) * 100
    assert accuracy == 100.0, f"Expected 100.0% replay contract score, got {accuracy}%"
