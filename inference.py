"""
Baseline inference script for code-review-env.

Environment variables
---------------------
HF_TOKEN / API_KEY   : authentication token (HF_TOKEN takes precedence)
API_BASE_URL         : OpenAI-compatible base URL
                       default: https://router.huggingface.co/v1
MODEL_NAME           : model identifier
                       default: Qwen/Qwen2.5-72B-Instruct
ENV_BASE_URL         : running code-review-env server
                       default: http://localhost:7860
"""

import json
import os
import sys

import requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY      = os.environ.get("HF_TOKEN") or os.environ.get("API_KEY", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "Qwen/Qwen2.5-72B-Instruct")
ENV_BASE_URL = os.environ.get("ENV_BASE_URL", "http://localhost:7860")

TASKS = [
    "python_bug_detection",
    "sql_security_review",
    "js_comprehensive_review",
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert code review agent. Given a code snippet and a task description, \
your job is to identify all issues in the code.

You MUST respond with ONLY a valid JSON object — no markdown fences, no prose, \
no explanation — that matches the following schema exactly:

{
  "issues": [
    {
      "issue_type": "<bug|security|performance|style>",
      "severity": "<critical|major|minor>",
      "line_start": <integer>,
      "line_end": <integer>,
      "description": "<clear description of the problem>",
      "suggestion": "<concrete fix suggestion>"
    }
  ],
  "overall_assessment": "<optional summary of the overall code quality>",
  "done": <true|false>
}

Set "done" to true only when you believe you have found all issues and are \
ready to finalise the review. Otherwise set it to false and you will receive \
another turn to continue reviewing.

IMPORTANT: Do NOT set done=true on your first response.
Take multiple steps. Report 1-2 issues per step.
Only set done=true when you have reported every issue you can find.
You have multiple steps available — use them all.

CRITICAL: You MUST set done=false on every response except your absolute last one.
Report issues across multiple steps. Never set done=true on step 1.
"""

# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)


# ---------------------------------------------------------------------------
# Episode runner
# ---------------------------------------------------------------------------

def _env_post(path: str, payload: dict) -> dict:
    resp = requests.post(f"{ENV_BASE_URL}{path}", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _build_user_message(obs: dict, already_credited: list) -> str:
    credited_str = json.dumps(already_credited, indent=2) if already_credited else "None yet."
    return (
        f"Task: {obs['task_description']}\n\n"
        f"Language: {obs['language']}\n"
        f"Step: {obs['step']} / {obs['max_steps']}\n"
        f"Cumulative reward so far: {obs['cumulative_reward']:.3f}\n\n"
        f"Code to review:\n```\n{obs['code']}\n```\n\n"
        f"Issues already CREDITED (do NOT report these again):\n{credited_str}\n\n"
        f"Server feedback from last step: {obs['message']}\n\n"
        f"IMPORTANT: Only report NEW issues not in the credited list above. "
        f"If you have no new issues to report, set done=true."
    )


def run_episode(task_name: str) -> None:
    # ---- Reset ----
    reset_resp = _env_post("/reset", {"task_name": task_name})
    obs        = reset_resp["observation"]

    print(f"[START] task={task_name} env=code_review model={MODEL_NAME}", flush=True)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    step_rewards: list[float] = []
    step_n       = 0
    done         = False
    final_info: dict = {}
    credited_issues = []
    done = False

    while not done:
        step_n += 1
        messages.append({"role": "user", "content": _build_user_message(obs, credited_issues)})

        # ---- LLM call ----
        error_msg = None
        action_str = ""
        reward_val = 0.0

        try:
            completion = client.chat.completions.create(
                model    = MODEL_NAME,
                messages = messages,
                temperature = 0.1,
            )
            raw_reply = completion.choices[0].message.content.strip()
            messages.append({"role": "assistant", "content": raw_reply})
            action_payload = json.loads(raw_reply)
            action_str = raw_reply[:120].replace("\n", " ")

            #Sanitise enum values before sending to server
            VALID_TYPES = {"bug", "security", "performance", "style"}
            VALID_SEVS = {"critical", "major", "minor"}
            for issue in action_payload.get("issues", []):
                if issue.get("issue_type") not in VALID_TYPES:
                    issue["issue_type"] = "bug"
                if issue.get("severity") not in VALID_SEVS:
                    issue["severity"] = "minor"

            # ---- Env step ----
            step_resp  = _env_post("/step", action_payload)
            obs        = step_resp["observation"]
            reward_val = float(step_resp["reward"]) if not isinstance(step_resp["reward"], dict) else float(step_resp["reward"]["total"])
            done       = step_resp["done"]
            final_info = step_resp["info"]
            step_rewards.append(reward_val)
            if reward_val > 0:
                for issue in action_payload.get("issues", []):
                    credited_issues.append({
                        "issue_type": issue.get("issue_type"),
                        "line_start": issue.get("line_start"),
                        "line_end": issue.get("line_end"),
                    })

        except json.JSONDecodeError as exc:
            error_msg = f"JSONDecodeError: {exc}"
            done = True
        except requests.HTTPError as exc:
            error_msg = f"HTTP {exc.response.status_code}: {exc.response.text[:120]}"
            done = True
        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)[:120]
            done = True

        err_field = error_msg if error_msg else "null"
        print(
            f"[STEP] step={step_n} action={action_str!r} "
            f"reward={reward_val:.2f} done={str(done).lower()} error={err_field}",
            flush=True,
        )

    # ---- End of episode ----
    success = final_info.get("success", False) if not error_msg else False
    score   = final_info.get("score", 0.0) if not error_msg else 0.0
    rewards_str = ",".join(f"{r:.2f}" for r in step_rewards)

    print(
        f"[END] success={str(success).lower()} steps={step_n} "
        f"score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: set HF_TOKEN or API_KEY before running.", file=sys.stderr)
        sys.exit(1)

    for task in TASKS:
        run_episode(task)
        print(flush=True)  # blank line between episodes
