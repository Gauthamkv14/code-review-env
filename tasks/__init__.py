import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks import task_python_bugs, task_sql_security, task_js_comprehensive

TASK_REGISTRY = {
    task_python_bugs.TASK_NAME: {
        "language":        task_python_bugs.LANGUAGE,
        "difficulty":      task_python_bugs.DIFFICULTY,
        "max_steps":       task_python_bugs.MAX_STEPS,
        "description":     task_python_bugs.DESCRIPTION,
        "code":            task_python_bugs.CODE,
        "ground_truth":    task_python_bugs.GROUND_TRUTH_ISSUES,
    },
    task_sql_security.TASK_NAME: {
        "language":        task_sql_security.LANGUAGE,
        "difficulty":      task_sql_security.DIFFICULTY,
        "max_steps":       task_sql_security.MAX_STEPS,
        "description":     task_sql_security.DESCRIPTION,
        "code":            task_sql_security.CODE,
        "ground_truth":    task_sql_security.GROUND_TRUTH_ISSUES,
    },
    task_js_comprehensive.TASK_NAME: {
        "language":        task_js_comprehensive.LANGUAGE,
        "difficulty":      task_js_comprehensive.DIFFICULTY,
        "max_steps":       task_js_comprehensive.MAX_STEPS,
        "description":     task_js_comprehensive.DESCRIPTION,
        "code":            task_js_comprehensive.CODE,
        "ground_truth":    task_js_comprehensive.GROUND_TRUTH_ISSUES,
    },
}

__all__ = ["TASK_REGISTRY"]
