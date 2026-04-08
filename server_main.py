import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from env import CodeReviewEnv
from models import CodeReviewAction, CodeReviewObservation, EpisodeState
from tasks import TASK_REGISTRY

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Code Review Environment", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global environment state (one instance per server process)
# ---------------------------------------------------------------------------

_env: Optional[CodeReviewEnv] = None

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ResetRequest(BaseModel):
    task_name: Optional[str] = None


class ResetResponse(BaseModel):
    task_name: str
    observation: CodeReviewObservation


class StepResponse(BaseModel):
    observation: CodeReviewObservation
    reward: Dict[str, Any]
    done: bool
    info: Dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/tasks")
def list_tasks() -> Dict[str, Any]:
    """Return metadata for every registered task."""
    return {
        name: {
            "language":             cfg["language"].value,
            "difficulty":           cfg["difficulty"].value,
            "max_steps":            cfg["max_steps"],
            "description":          cfg["description"],
            "num_ground_truth_issues": len(cfg["ground_truth"]),
        }
        for name, cfg in TASK_REGISTRY.items()
    }


@app.post("/reset", response_model=ResetResponse)
def reset(body: ResetRequest = ResetRequest()) -> ResetResponse:
    """
    Create (or re-create) the global environment for the requested task and
    return the initial observation.  If task_name is omitted the first
    registered task is used.
    """
    global _env

    task_name = body.task_name or next(iter(TASK_REGISTRY))

    try:
        _env = CodeReviewEnv(task_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    observation = _env.reset()
    return ResetResponse(task_name=task_name, observation=observation)


@app.post("/step", response_model=StepResponse)
def step(action: CodeReviewAction) -> StepResponse:
    """
    Apply one action to the current environment and return the result.
    Returns HTTP 400 if the episode is already done or /reset was never called.
    """
    global _env

    if _env is None:
        raise HTTPException(status_code=400, detail="No active episode. Call /reset first.")

    try:
        result = _env.step(action)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return StepResponse(
        observation = result.observation,
        reward      = result.reward.model_dump(),
        done        = result.done,
        info        = result.info,
    )


@app.get("/state", response_model=EpisodeState)
def state() -> EpisodeState:
    """Return the full current episode state."""
    if _env is None:
        raise HTTPException(status_code=400, detail="No active episode. Call /reset first.")
    return _env.state()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("server_main:app", host="0.0.0.0", port=port, reload=False)
