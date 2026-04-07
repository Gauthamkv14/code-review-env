import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Issue, IssueType, Language, Severity, TaskDifficulty

# --- Task Metadata ---

TASK_NAME = "sql_security_review"
LANGUAGE = Language.sql
DIFFICULTY = TaskDifficulty.medium
MAX_STEPS = 8
DESCRIPTION = (
    "You are a security-focused code review agent. Your task is to analyze the "
    "provided Python/SQLite database access module and identify all security "
    "vulnerabilities. Pay close attention to hardcoded credentials, SQL injection "
    "via string concatenation or f-strings, and improper handling of user-supplied "
    "input. For each vulnerability found, report the affected line range, a clear "
    "description of the risk, and a concrete remediation suggestion. The module "
    "contains exactly 3 security vulnerabilities."
)

# --- Code Under Review ---

CODE = '''\
import sqlite3

# Vulnerability 1: hardcoded credential
DB_PASSWORD = "supersecret123"


def get_connection():
    """Return a connection to the application database."""
    conn = sqlite3.connect("app.db")
    return conn


def get_user_by_username(username):
    """Fetch a user record by username."""
    conn = get_connection()
    # Vulnerability 2: SQL injection via string concatenation
    query = "SELECT * FROM users WHERE username = \'" + username + "\'"
    cursor = conn.execute(query)
    row = cursor.fetchone()
    conn.close()
    return row


def get_orders(user_id, status_filter):
    """Fetch orders for a user filtered by status."""
    conn = get_connection()
    # Vulnerability 3: SQL injection via f-string
    query = f"SELECT * FROM orders WHERE user_id = {user_id} AND status = \'{status_filter}\'"
    cursor = conn.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


def create_user(username, email, hashed_password):
    """Insert a new user record using a parameterised query (safe)."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
        (username, email, hashed_password),
    )
    conn.commit()
    conn.close()
'''

# --- Ground Truth Issues ---

GROUND_TRUTH_ISSUES = [
    Issue(
        issue_type=IssueType.security,
        severity=Severity.major,
        line_start=4,
        line_end=4,
        description=(
            "Hardcoded credential: `DB_PASSWORD = \"supersecret123\"` stores a "
            "sensitive password directly in source code, exposing it to anyone with "
            "repository access and making rotation difficult."
        ),
        suggestion=(
            "Load secrets from environment variables instead: "
            "`DB_PASSWORD = os.environ.get('DB_PASSWORD')`. "
            "Consider using a secrets manager for production deployments."
        ),
    ),
    Issue(
        issue_type=IssueType.security,
        severity=Severity.critical,
        line_start=15,
        line_end=16,
        description=(
            "SQL injection via string concatenation: the `username` parameter is "
            "interpolated directly into the query string with `+` concatenation, "
            "allowing an attacker to break out of the string literal and execute "
            "arbitrary SQL (e.g., `' OR '1'='1`)."
        ),
        suggestion=(
            "Use a parameterised query with a `?` placeholder: "
            "`cursor = conn.execute(\"SELECT * FROM users WHERE username = ?\", (username,))`. "
            "Never build SQL strings from user-supplied data."
        ),
    ),
    Issue(
        issue_type=IssueType.security,
        severity=Severity.critical,
        line_start=25,
        line_end=26,
        description=(
            "SQL injection via f-string: `user_id` and `status_filter` are embedded "
            "directly into the query using an f-string, enabling an attacker to inject "
            "malicious SQL through either parameter (e.g., setting `status_filter` to "
            "`'; DROP TABLE orders; --`)."
        ),
        suggestion=(
            "Replace the f-string with a parameterised query: "
            "`cursor = conn.execute("
            "\"SELECT * FROM orders WHERE user_id = ? AND status = ?\", "
            "(user_id, status_filter))`. "
            "Always use placeholders for every user-controlled value."
        ),
    ),
]
