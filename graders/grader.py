import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional, Set, Tuple
from models import Issue, RewardBreakdown, CodeReviewReward, Severity

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {
    Severity.critical: 0.40,
    Severity.major:    0.25,
    Severity.minor:    0.10,
}

# Ordered from highest to lowest for distance calculations
_SEVERITY_ORDER = [Severity.critical, Severity.major, Severity.minor]

SEVERITY_MODIFIERS = {0: 1.0, 1: 0.6, 2: 0.3}

FIX_BONUS            =  0.05
SEVERITY_BONUS_BASE  =  0.05
FALSE_POSITIVE_PEN   = -0.10
MISSED_CRITICAL_PEN  = -0.15
ASSESSMENT_BONUS     =  0.05
SUGGESTION_MIN_LEN   =  20
ASSESSMENT_MIN_LEN   =  30


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _severity_distance(a: Severity, b: Severity) -> int:
    return abs(_SEVERITY_ORDER.index(a) - _SEVERITY_ORDER.index(b))


def _ranges_overlap(s1: int, e1: int, s2: int, e2: int, tolerance: int = 2) -> bool:
    return s1 <= e2 + tolerance and s2 <= e1 + tolerance


def _find_match(
    reported: Issue,
    ground_truth: List[Issue],
    already_matched: Set[int],
) -> Optional[int]:
    """Return the index of the best unmatched ground-truth issue, or None."""
    for idx, gt in enumerate(ground_truth):
        if idx in already_matched:
            continue
        if reported.issue_type != gt.issue_type:
            continue
        if not _ranges_overlap(reported.line_start, reported.line_end,
                               gt.line_start, gt.line_end):
            continue
        return idx
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def grade_step(
    reported_issues: List[Issue],
    ground_truth: List[Issue],
    already_matched: Set[int],
    done: bool,
    overall_assessment: Optional[str] = None,
) -> Tuple[float, RewardBreakdown, Set[int], str]:
    """
    Score one environment step.

    Returns
    -------
    total_reward      : float clamped to [-1.0, 1.0]
    breakdown         : RewardBreakdown
    updated_matched   : updated set of matched ground-truth indices
    feedback          : human-readable feedback string
    """
    matched = set(already_matched)  # copy so caller's set is not mutated

    tp_score          = 0.0
    fix_quality       = 0.0
    sev_accuracy      = 0.0
    fp_penalty        = 0.0
    missed_penalty    = 0.0
    assess_bonus      = 0.0
    feedback_parts: List[str] = []

    # --- Evaluate each reported issue ---
    for reported in reported_issues:
        match_idx = _find_match(reported, ground_truth, matched)

        if match_idx is not None:
            gt = ground_truth[match_idx]
            matched.add(match_idx)

            dist     = _severity_distance(reported.severity, gt.severity)
            sev_mod  = SEVERITY_MODIFIERS.get(dist, 0.3)
            weight   = SEVERITY_WEIGHTS[gt.severity]

            issue_score   = weight * sev_mod
            fix_b         = FIX_BONUS if (reported.suggestion and len(reported.suggestion) > SUGGESTION_MIN_LEN) else 0.0
            sev_b         = SEVERITY_BONUS_BASE * sev_mod

            tp_score    += issue_score
            fix_quality += fix_b
            sev_accuracy += sev_b

            feedback_parts.append(
                f"✓ Matched GT issue #{match_idx} ({gt.issue_type.value} L{gt.line_start}-{gt.line_end}) "
                f"[score={issue_score:.2f}, sev_mod={sev_mod}]."
            )
        else:
            fp_penalty += FALSE_POSITIVE_PEN
            feedback_parts.append(
                f"✗ False positive: {reported.issue_type.value} L{reported.line_start}-{reported.line_end} "
                f"(penalty={FALSE_POSITIVE_PEN})."
            )

    # --- End-of-episode bonuses / penalties ---
    if done:
        for idx, gt in enumerate(ground_truth):
            if idx not in matched and gt.severity == Severity.critical:
                missed_penalty += MISSED_CRITICAL_PEN
                feedback_parts.append(
                    f"✗ Missed critical issue #{idx}: {gt.issue_type.value} L{gt.line_start}-{gt.line_end} "
                    f"(penalty={MISSED_CRITICAL_PEN})."
                )

        if overall_assessment and len(overall_assessment) > ASSESSMENT_MIN_LEN:
            assess_bonus = ASSESSMENT_BONUS
            feedback_parts.append(f"✓ Assessment bonus (+{ASSESSMENT_BONUS}).")

    # --- Aggregate and clamp ---
    raw_total = tp_score + fix_quality + sev_accuracy + fp_penalty + missed_penalty + assess_bonus
    total     = max(-1.0, min(1.0, raw_total))

    breakdown = RewardBreakdown(
        true_positive_score    = round(tp_score,     4),
        fix_quality_score      = round(fix_quality,  4),
        severity_accuracy_score= round(sev_accuracy, 4),
        false_positive_penalty = round(fp_penalty,   4),
        missed_critical_penalty= round(missed_penalty, 4),
        assessment_bonus       = round(assess_bonus, 4),
    )

    feedback = " | ".join(feedback_parts) if feedback_parts else "No issues reported this step."

    return total, breakdown, matched, feedback


def compute_episode_score(
    cumulative_reward: float,
    ground_truth: List[Issue],
) -> float:
    """
    Normalise cumulative_reward against the theoretical maximum achievable score.

    Max per GT issue = weight + FIX_BONUS + SEVERITY_BONUS_BASE
    Plus a single ASSESSMENT_BONUS for the episode.

    Returns a float in [0.0, 1.0].
    """
    max_possible = sum(
        SEVERITY_WEIGHTS[gt.severity] + FIX_BONUS + SEVERITY_BONUS_BASE
        for gt in ground_truth
    ) + ASSESSMENT_BONUS

    if max_possible <= 0:
        return 0.0

    return max(0.0, min(1.0, cumulative_reward / max_possible))
