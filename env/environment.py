import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Set
from models import (
    CodeReviewAction,
    CodeReviewObservation,
    CodeReviewReward,
    EpisodeState,
    StepResult,
)
from tasks import TASK_REGISTRY
from graders import grade_step, compute_episode_score


class CodeReviewEnv:
    """Deterministic code-review reinforcement-learning environment."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, task_name: str) -> None:
        if task_name not in TASK_REGISTRY:
            raise ValueError(
                f"Unknown task '{task_name}'. "
                f"Available tasks: {list(TASK_REGISTRY.keys())}"
            )

        self._task_name = task_name
        self._cfg = TASK_REGISTRY[task_name]

        # Episode state — initialised properly by reset()
        self._step: int = 0
        self._done: bool = False
        self._success: bool = False
        self._cumulative_reward: float = 0.0
        self._last_reward: float = 0.0
        self._issues_found: list = []
        self._matched_gt_indices: Set[int] = set()
        self._last_feedback: str = ""

    # ------------------------------------------------------------------
    # reset
    # ------------------------------------------------------------------

    def reset(self) -> CodeReviewObservation:
        """Reset all episode state and return the initial observation."""
        self._step = 0
        self._done = False
        self._success = False
        self._cumulative_reward = 0.0
        self._last_reward = 0.0
        self._issues_found = []
        self._matched_gt_indices = set()
        self._last_feedback = "Episode started. Begin your code review."

        return self._build_observation()

    # ------------------------------------------------------------------
    # step
    # ------------------------------------------------------------------

    def step(self, action: CodeReviewAction) -> StepResult:
        """Apply an action and return the resulting StepResult."""
        if self._done:
            raise RuntimeError(
                "Episode is already done. Call reset() to start a new episode."
            )

        self._step += 1
        done = action.done or self._step >= self._cfg["max_steps"]

        reward_value, breakdown, updated_matched, feedback = grade_step(
            reported_issues   = action.issues,
            ground_truth      = self._cfg["ground_truth"],
            already_matched   = self._matched_gt_indices,
            done              = done,
            overall_assessment= action.overall_assessment,
        )

        # Update episode state
        self._matched_gt_indices = updated_matched
        self._issues_found.extend(action.issues)
        self._last_reward = reward_value
        self._cumulative_reward += reward_value
        self._done = done
        self._last_feedback = feedback

        reward = CodeReviewReward(
            total     = reward_value,
            breakdown = breakdown,
            feedback  = feedback,
        )

        episode_score = 0.0
        if done:
            episode_score = compute_episode_score(
                self._cumulative_reward,
                self._cfg["ground_truth"],
            )
            self._success = episode_score >= 0.5

        info = {
            "episode_score":   episode_score,
            "matched_indices": list(self._matched_gt_indices),
            "total_gt_issues": len(self._cfg["ground_truth"]),
        }

        return StepResult(
            observation = self._build_observation(),
            reward      = reward,
            done        = done,
            info        = info,
        )

    # ------------------------------------------------------------------
    # state
    # ------------------------------------------------------------------

    def state(self) -> EpisodeState:
        """Return the full current episode state."""
        return EpisodeState(
            task_name         = self._task_name,
            language          = self._cfg["language"],
            difficulty        = self._cfg["difficulty"],
            step              = self._step,
            max_steps         = self._cfg["max_steps"],
            code              = self._cfg["code"],
            ground_truth_issues = self._cfg["ground_truth"],
            issues_found      = list(self._issues_found),
            cumulative_reward = self._cumulative_reward,
            done              = self._done,
            success           = self._success,
        )

    # ------------------------------------------------------------------
    # close
    # ------------------------------------------------------------------

    def close(self) -> None:
        """No-op. Included for API compatibility."""
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_observation(self) -> CodeReviewObservation:
        return CodeReviewObservation(
            code              = self._cfg["code"],
            language          = self._cfg["language"],
            task_description  = self._cfg["description"],
            step              = self._step,
            max_steps         = self._cfg["max_steps"],
            issues_found_so_far = list(self._issues_found),
            last_reward       = self._last_reward,
            cumulative_reward = self._cumulative_reward,
            done              = self._done,
            message           = self._last_feedback,
        )
