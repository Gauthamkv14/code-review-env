# Context Transfer: Code Review RL Environment

## Project Goal
The primary objective of this project is to build an iterative, RL-style (Reinforcement Learning) autonomous code review agent. 
- A large language model (e.g., Qwen2.5-72B-Instruct) attempts to find bugs, security vulnerabilities, and style issues in code snippets (Python, SQL, JS).
- An evaluation server (`server.py`) with a dedicated grading logic (`graders/grader.py`) evaluates the LLM's findings and returns a reward back to the LLM agent.
- The LLM can take multiple steps to refine its review until it has discovered all issues and sets `done=true`.

## Key Implementations & Enhancements

1. **Multi-Step Pacing via Prompting (`inference.py`)** 
   - Instructed the LLM to take its time, explicitly telling it to evaluate code over multiple turns (1-2 issues per step) and NOT exit out early.

2. **Issue History & Deduplication Tracking (`inference.py`)**
   - The script now tracks "credited" issues (issues that received a positive reward) and injects them into the user prompt. This stops the model from continuously repeating the same bugs and forces it to search for new edge cases.

3. **Payload Sanitisation & Robust Parsing (`inference.py`)**
   - Fallback mechanisms intercept LLM hallucinations for enums (e.g., issue severity types, issue categories) so that the payload always complies with the expected formatting constraints before reaching the grading server.

4. **Fuzzy Line Match Tolerance (`graders/grader.py`)**
   - Line matching is no longer rigidly exact. Implemented a `tolerance=2` parameter in the `_ranges_overlap` bounds checking to make grading more forgiving for slightly offset line references by the LLM.

5. **Reduced Temperature (`inference.py`)**
   - Lowered the inference temperature from 0.2 to 0.1 for more stable and focused responses.

## Example Output Logs

```text
python inference.py
[START] task=python_bug_detection env=code_review model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action='{   "issues": [     {       "issue_type": "bug",       "severity": "major",       "line_start": 3,       "line_end": 5, ' reward=0.12 done=true error=null
[END] success=false steps=1 score=0.000 rewards=0.12

[START] task=sql_security_review env=code_review model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action='{   "issues": [     {       "issue_type": "security",       "severity": "critical",       "line_start": 5,       "line_e' reward=-0.20 done=false error=null
[STEP] step=2 action='{   "issues": [     {       "issue_type": "security",       "severity": "critical",       "line_start": 23,       "line_' reward=-0.10 done=false error=null
[STEP] step=3 action='{   "issues": [     {       "issue_type": "security",       "severity": "critical",       "line_start": 14,       "line_' reward=-0.20 done=false error=null
[STEP] step=4 action='{   "issues": [     {       "issue_type": "security",       "severity": "critical",       "line_start": 5,       "line_e' reward=-0.10 done=false error=null
[STEP] step=5 action='{   "issues": [     {       "issue_type": "security",       "severity": "critical",       "line_start": 14,       "line_' reward=-0.10 done=false error=null
[STEP] step=6 action='{   "issues": [     {       "issue_type": "security",       "severity": "critical",       "line_start": 23,       "line_' reward=-0.10 done=false error=null
[STEP] step=7 action='{   "issues": [],   "overall_assessment": "All identified security vulnerabilities have been reported. No new issues fou' reward=-0.25 done=true error=null
[END] success=false steps=7 score=0.000 rewards=-0.20,-0.10,-0.20,-0.10,-0.10,-0.10,-0.25

[START] task=js_comprehensive_review env=code_review model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action='{   "issues": [     {       "issue_type": "security",       "severity": "critical",       "line_start": 12,       "line_' reward=0.25 done=false error=null
[STEP] step=2 action='' reward=0.00 done=true error=Error code: 402 - {'error': 'You have depleted your monthly included credits. Purchase pre-paid credits to continue usin
[END] success=false steps=2 score=0.000 rewards=0.25
```
