"""
tests/test_environment.py
Unit tests for CodeReviewEnv and the grading engine.
Run with:  python -m pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from env import CodeReviewEnv
from models import CodeReviewAction, Issue, IssueType, Severity
from tasks import TASK_REGISTRY
from tasks import task_python_bugs, task_sql_security, task_js_comprehensive

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_action(issues=None, overall_assessment=None, done=False):
    return CodeReviewAction(
        issues=issues or [],
        overall_assessment=overall_assessment,
        done=done,
    )


def _correct_python_issue_0():
    """Exact match for python_bug_detection GT issue 0 (off-by-one)."""
    gt = task_python_bugs.GROUND_TRUTH_ISSUES[0]
    return Issue(
        issue_type=gt.issue_type,
        severity=gt.severity,
        line_start=gt.line_start,
        line_end=gt.line_end,
        description=gt.description,
        suggestion=gt.suggestion,
    )


def _correct_sql_issue_1():
    """Exact match for sql_security_review GT issue 1 (SQL injection concat)."""
    gt = task_sql_security.GROUND_TRUTH_ISSUES[1]
    return Issue(
        issue_type=gt.issue_type,
        severity=gt.severity,
        line_start=gt.line_start,
        line_end=gt.line_end,
        description=gt.description,
        suggestion=gt.suggestion,
    )


def _correct_js_issue_4():
    """Exact match for js_comprehensive_review GT issue 4 (missing await)."""
    gt = task_js_comprehensive.GROUND_TRUTH_ISSUES[4]
    return Issue(
        issue_type=gt.issue_type,
        severity=gt.severity,
        line_start=gt.line_start,
        line_end=gt.line_end,
        description=gt.description,
        suggestion=gt.suggestion,
    )


def _false_positive():
    """An issue that matches no ground-truth entry in any task."""
    return Issue(
        issue_type=IssueType.style,
        severity=Severity.minor,
        line_start=999,
        line_end=999,
        description="Non-existent style issue on a line that does not exist.",
        suggestion="This is a fabricated issue with a long suggestion string.",
    )


# ---------------------------------------------------------------------------
# 1. All 3 tasks initialise without error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("task_name", list(TASK_REGISTRY.keys()))
def test_all_tasks_initialise(task_name):
    env = CodeReviewEnv(task_name)
    assert env is not None


# ---------------------------------------------------------------------------
# 2. Unknown task name raises ValueError
# ---------------------------------------------------------------------------

def test_unknown_task_raises():
    with pytest.raises(ValueError, match="Unknown task"):
        CodeReviewEnv("nonexistent_task_xyz")


# ---------------------------------------------------------------------------
# 3. reset() clears all state back to zero
# ---------------------------------------------------------------------------

def test_reset_clears_state():
    env = CodeReviewEnv("python_bug_detection")
    obs = env.reset()

    # Take a step to dirty the state
    env.step(_make_action(issues=[_correct_python_issue_0()]))

    # Reset and inspect
    obs = env.reset()
    assert obs.step == 0
    assert obs.cumulative_reward == 0.0
    assert obs.last_reward == 0.0
    assert obs.issues_found_so_far == []
    assert obs.done is False

    state = env.state()
    assert state.step == 0
    assert state.cumulative_reward == 0.0
    assert state.issues_found == []
    assert state.done is False
    assert state.success is False


# ---------------------------------------------------------------------------
# 4. Correct critical issue → positive reward
# ---------------------------------------------------------------------------

def test_correct_critical_issue_positive_reward():
    env = CodeReviewEnv("python_bug_detection")
    env.reset()
    result = env.step(_make_action(issues=[_correct_python_issue_0()]))
    assert result.reward.total > 0.0


# ---------------------------------------------------------------------------
# 5. False positive → negative reward
# ---------------------------------------------------------------------------

def test_false_positive_negative_reward():
    env = CodeReviewEnv("python_bug_detection")
    env.reset()
    result = env.step(_make_action(issues=[_false_positive()]))
    assert result.reward.total < 0.0
    assert result.reward.breakdown.false_positive_penalty < 0.0


# ---------------------------------------------------------------------------
# 6. done=True without finding critical issues → missed penalty applied
# ---------------------------------------------------------------------------

def test_missed_critical_penalty_on_done():
    env = CodeReviewEnv("python_bug_detection")
    env.reset()
    # End episode immediately without reporting anything
    result = env.step(_make_action(done=True))
    assert result.reward.breakdown.missed_critical_penalty < 0.0


# ---------------------------------------------------------------------------
# 7. Reward is always clamped to [-1.0, 1.0]
# ---------------------------------------------------------------------------

def test_reward_clamped():
    env = CodeReviewEnv("python_bug_detection")
    env.reset()
    # Flood with false positives to try to push reward below -1.0
    many_fps = [_false_positive() for _ in range(20)]
    result = env.step(_make_action(issues=many_fps, done=True))
    assert -1.0 <= result.reward.total <= 1.0


# ---------------------------------------------------------------------------
# 8. SQL injection correctly identified → positive reward
# ---------------------------------------------------------------------------

def test_sql_injection_positive_reward():
    env = CodeReviewEnv("sql_security_review")
    env.reset()
    result = env.step(_make_action(issues=[_correct_sql_issue_1()]))
    assert result.reward.total > 0.0


# ---------------------------------------------------------------------------
# 9. JS missing await correctly identified → positive reward
# ---------------------------------------------------------------------------

def test_js_missing_await_positive_reward():
    env = CodeReviewEnv("js_comprehensive_review")
    env.reset()
    result = env.step(_make_action(issues=[_correct_js_issue_4()]))
    assert result.reward.total > 0.0


# ---------------------------------------------------------------------------
# 10. state() reflects step count and issues found
# ---------------------------------------------------------------------------

def test_state_reflects_progress():
    env = CodeReviewEnv("python_bug_detection")
    env.reset()

    issue = _correct_python_issue_0()
    env.step(_make_action(issues=[issue]))

    state = env.state()
    assert state.step == 1
    assert len(state.issues_found) == 1
    assert state.issues_found[0].issue_type == issue.issue_type


# ---------------------------------------------------------------------------
# 11. Episode ends at max_steps even without done=True in action
# ---------------------------------------------------------------------------

def test_episode_ends_at_max_steps():
    env = CodeReviewEnv("python_bug_detection")
    env.reset()
    max_steps = TASK_REGISTRY["python_bug_detection"]["max_steps"]

    result = None
    for _ in range(max_steps):
        result = env.step(_make_action())

    assert result.done is True
    assert env.state().done is True


# ---------------------------------------------------------------------------
# 12. Calling step() after done=True raises RuntimeError
# ---------------------------------------------------------------------------

def test_step_after_done_raises():
    env = CodeReviewEnv("python_bug_detection")
    env.reset()
    env.step(_make_action(done=True))

    with pytest.raises(RuntimeError, match="already done"):
        env.step(_make_action())
