import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Issue, IssueType, Language, Severity, TaskDifficulty

# --- Task Metadata ---

TASK_NAME = "python_bug_detection"
LANGUAGE = Language.python
DIFFICULTY = TaskDifficulty.easy
MAX_STEPS = 6
DESCRIPTION = (
    "You are a code review agent. Your task is to carefully analyze the provided "
    "Python code snippet and identify all bugs present. Focus on logic errors, "
    "edge-case failures, and runtime exceptions. For each bug found, report the "
    "affected line range, a clear description of the problem, and a concrete "
    "suggestion on how to fix it. The snippet contains exactly 2 bugs."
)

# --- Code Under Review ---

CODE = '''\
def calculate_average(numbers):
    total = 0
    # Bug 1: range starts at 1, skipping numbers[0]
    for i in range(1, len(numbers)):
        total += numbers[i]
    # Bug 2: crashes with ZeroDivisionError when numbers is empty
    return total / len(numbers)


def find_max_index(items):
    """Return the index of the largest element in the list."""
    if not items:
        return -1
    max_idx = 0
    for i in range(1, len(items)):
        if items[i] > items[max_idx]:
            max_idx = i
    return max_idx


def reverse_string(s):
    """Return the reverse of the given string."""
    return s[::-1]
'''

# --- Ground Truth Issues ---

GROUND_TRUTH_ISSUES = [
    Issue(
        issue_type=IssueType.bug,
        severity=Severity.critical,
        line_start=4,
        line_end=4,
        description=(
            "Off-by-one error: `range(1, len(numbers))` starts iteration at index 1, "
            "causing the first element (`numbers[0]`) to always be skipped when "
            "computing the total."
        ),
        suggestion="Change `range(1, len(numbers))` to `range(len(numbers))` so all elements are included.",
    ),
    Issue(
        issue_type=IssueType.bug,
        severity=Severity.critical,
        line_start=6,
        line_end=6,
        description=(
            "`return total / len(numbers)` raises a `ZeroDivisionError` when an "
            "empty list is passed because `len(numbers)` evaluates to 0."
        ),
        suggestion=(
            "Add an empty-list guard before the division, e.g.: "
            "`if not numbers: return 0.0` (or raise a descriptive ValueError)."
        ),
    ),
]
