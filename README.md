---
title: Code Review Environment
emoji: 🔍
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
---


# code-review-env

A deterministic reinforcement-learning environment in which an AI agent performs multi-step code reviews across Python, SQL, and JavaScript. Built for the [OpenEnv](https://openenv.ai) standard.

---

## Overview

`code-review-env` presents an agent with a snippet of source code and asks it to identify bugs, security vulnerabilities, and performance issues over several turns. Each finding is scored against a ground-truth issue set using a deterministic grader — no LLM judge required. Partial credit is awarded for correct issue type and overlapping line ranges; severity accuracy, fix quality, and a holistic assessment earn bonus points.

---

## Tasks

| Task Name | Language | Difficulty | Max Steps | Ground-Truth Issues |
|---|---|---|---|---|
| `python_bug_detection` | Python | Easy | 6 | 2 |
| `sql_security_review` | SQL / Python | Medium | 8 | 3 |
| `js_comprehensive_review` | JavaScript | Hard | 10 | 5 |

### python_bug_detection
Find two bugs in a Python utility module:
- **Line 4** — off-by-one: `range(1, len(numbers))` skips `numbers[0]`
- **Line 6** — `ZeroDivisionError` on empty list

### sql_security_review
Identify three security vulnerabilities in a Python/SQLite module:
- **Line 4** — hardcoded credential
- **Lines 15–16** — SQL injection via string concatenation
- **Lines 25–26** — SQL injection via f-string

### js_comprehensive_review
Comprehensive review of an Express.js router with five issues:
- **Lines 11–16** — N+1 query (performance)
- **Lines 13–14** — SQL injection via concatenation (security)
- **Line 20** — internal error leakage (security)
- **Lines 24–25** — missing authentication (security)
- **Lines 29–33** — missing `await` on INSERT (bug)

---

## Action Space

The agent submits a JSON object on every turn:

```json
{
  "issues": [
    {
      "issue_type": "bug | security | performance | style",
      "severity":   "critical | major | minor",
      "line_start": 4,
      "line_end":   4,
      "description": "Clear description of the problem.",
      "suggestion":  "Concrete fix (optional but scored)."
    }
  ],
  "overall_assessment": "Optional holistic summary (scored at done).",
  "done": false
}
```

Set `done: true` when the review is complete. The episode also ends automatically when `step == max_steps`.

---

## Observation Space

```json
{
  "code":                "string  — full source code under review",
  "language":            "python | javascript | sql",
  "task_description":    "string  — natural-language instructions",
  "step":                0,
  "max_steps":           6,
  "issues_found_so_far": [],
  "last_reward":         0.0,
  "cumulative_reward":   0.0,
  "done":                false,
  "message":             "string  — server feedback from previous step"
}
```

---

## Reward Function

Rewards are computed deterministically each step and summed to a cumulative reward. The final episode score is `cumulative_reward / max_possible_reward` clamped to `[0.0, 1.0]`.

| Event | Value |
|---|---|
| True positive — critical issue | `+0.40 × severity_modifier` |
| True positive — major issue | `+0.25 × severity_modifier` |
| True positive — minor issue | `+0.10 × severity_modifier` |
| Severity modifier — exact match | `1.0` |
| Severity modifier — off by one level | `0.6` |
| Severity modifier — off by two levels | `0.3` |
| Fix quality bonus (suggestion > 20 chars) | `+0.05` per issue |
| Severity accuracy bonus | `+0.05 × severity_modifier` per issue |
| False positive (no GT match) | `−0.10` per issue |
| Missed critical issue (at `done`) | `−0.15` per issue |
| Assessment bonus (> 30 chars, at `done`) | `+0.05` |
| **Total clamped to** | `[−1.0, 1.0]` |

**Success threshold**: episode score ≥ `0.50`.

---

## Setup & Usage

### Local Development

```bash
# 1. Clone and enter the project
git clone https://github.com/your-org/code-review-env
cd code-review-env

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
python -m uvicorn server:app --host 0.0.0.0 --port 7860

# 5. Run the test suite
python -m pytest tests/ -v
```

### Docker

```bash
# Build
docker build -t code-review-env .

# Run
docker run -p 7860:7860 code-review-env

# Run with custom port
docker run -e PORT=8000 -p 8000:8000 code-review-env
```

### API Examples

```bash
# Health check
curl http://localhost:7860/health

# List all tasks
curl http://localhost:7860/tasks

# Start a new episode
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_name": "python_bug_detection"}'

# Submit an action
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{
    "issues": [{
      "issue_type": "bug",
      "severity": "critical",
      "line_start": 4,
      "line_end": 4,
      "description": "range(1, len(numbers)) skips the first element.",
      "suggestion": "Change to range(len(numbers))."
    }],
    "done": false
  }'

# Inspect full episode state
curl http://localhost:7860/state
```

### Running the Inference Script

```bash
export HF_TOKEN=hf_...
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct   # optional
export ENV_BASE_URL=http://localhost:7860       # optional

python inference.py
```

Sample output:
```
[START] task=python_bug_detection env=code_review model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action='{"issues": [...], "done": false}' reward=0.45 done=false error=null
[END] success=true steps=3 score=0.872 rewards=0.45,0.35,0.10
```

---

## Baseline Scores

Scores achieved by `Qwen/Qwen2.5-72B-Instruct` via the HuggingFace Inference Router:

| Task | Episode Score | Steps Used | Notes |
|---|---|---|---|
| `python_bug_detection` | ~0.85 | 2–3 | Both bugs reliably found in early steps |
| `sql_security_review` | ~0.72 | 4–5 | Hardcoded credential occasionally missed |
| `js_comprehensive_review` | ~0.58 | 7–9 | N+1 query and missing `await` are most often missed |

---

## Project Structure

```
code-review-env/
├── models.py                   # Pydantic enums and data models
├── server.py                   # FastAPI app (5 endpoints)
├── inference.py                # Baseline inference script
├── openenv.yaml                # OpenEnv metadata
├── requirements.txt
├── Dockerfile
├── README.md
├── env/
│   ├── __init__.py
│   └── environment.py          # CodeReviewEnv class
├── tasks/
│   ├── __init__.py             # TASK_REGISTRY
│   ├── task_python_bugs.py     # Easy — Python bug detection
│   ├── task_sql_security.py    # Medium — SQL security review
│   └── task_js_comprehensive.py# Hard — JS comprehensive review
├── graders/
│   ├── __init__.py
│   └── grader.py               # grade_step + compute_episode_score
└── tests/
    ├── __init__.py
    └── test_environment.py     # 12 pytest test cases
```

---

## Design Decisions

### Why partial rewards?
A binary success/failure signal makes learning extremely sparse — the agent receives no gradient until it finds every single issue perfectly. Partial credit for each true positive enables meaningful reward signal from the very first step, allowing gradient-based methods and RLHF techniques to converge from early in training.

### Why Python, SQL, and JavaScript?
These three languages cover the most common vulnerability classes in practice while keeping ground-truth annotation tractable:
- **Python** — logic/runtime errors (off-by-one, ZeroDivisionError)
- **SQL** — injection and credential hygiene, the most severe real-world attack vectors
- **JavaScript** — async bugs, auth gaps, and info leakage that are endemic in web backends

They also stress-test tokenisation and language-switching in LLMs that may be stronger in one than another.

### Why a deterministic grader?
LLM-as-judge scoring is non-reproducible: the same model, same weights, different run → different scores. A deterministic grader based on line-range overlap and enum matching gives bit-identical results across every evaluation, making leaderboard comparisons meaningful and debugging straightforward. The cost is that the grader cannot credit paraphrased-but-correct descriptions — that trade-off is intentional.

**Why severity weighting?**
Not all issues are equal. A missing `await` that silently swallows errors is more dangerous than a style inconsistency. The reward function teaches agents to prioritise correctly.

---

## 📄 License

MIT
