from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


# --- Enums ---

class Language(str, Enum):
    python = "python"
    javascript = "javascript"
    sql = "sql"


class IssueType(str, Enum):
    bug = "bug"
    security = "security"
    performance = "performance"
    style = "style"


class Severity(str, Enum):
    critical = "critical"
    major = "major"
    minor = "minor"


class TaskDifficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


# --- Models ---

class Issue(BaseModel):
    issue_type: IssueType
    severity: Severity
    line_start: int
    line_end: int
    description: str
    suggestion: Optional[str] = None


class CodeReviewObservation(BaseModel):
    code: str
    language: Language
    task_description: str
    step: int
    max_steps: int
    issues_found_so_far: List[Issue]
    last_reward: float
    cumulative_reward: float
    done: bool
    message: str


class CodeReviewAction(BaseModel):
    issues: List[Issue]
    overall_assessment: Optional[str] = None
    done: bool


class RewardBreakdown(BaseModel):
    true_positive_score: float
    fix_quality_score: float
    severity_accuracy_score: float
    false_positive_penalty: float
    missed_critical_penalty: float
    assessment_bonus: float


class CodeReviewReward(BaseModel):
    total: float
    breakdown: RewardBreakdown
    feedback: str


class EpisodeState(BaseModel):
    task_name: str
    language: Language
    difficulty: TaskDifficulty
    step: int
    max_steps: int
    code: str
    ground_truth_issues: List[Issue]
    issues_found: List[Issue]
    cumulative_reward: float
    done: bool
    success: bool


class StepResult(BaseModel):
    observation: CodeReviewObservation
    reward: CodeReviewReward
    done: bool
    info: dict
