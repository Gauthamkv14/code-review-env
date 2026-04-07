import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Issue, IssueType, Language, Severity, TaskDifficulty

# --- Task Metadata ---

TASK_NAME = "js_comprehensive_review"
LANGUAGE = Language.javascript
DIFFICULTY = TaskDifficulty.hard
MAX_STEPS = 10
DESCRIPTION = (
    "You are a senior code review agent performing a comprehensive review of a "
    "production Express.js route file. Your task is to identify all bugs, security "
    "vulnerabilities, and performance issues present in the module. Consider SQL "
    "injection, information leakage, missing authentication, async/await misuse, and "
    "inefficient database access patterns. For each issue found, report the affected "
    "line range, a precise description of the problem and its impact, and an "
    "actionable remediation suggestion. The file contains exactly 5 issues."
)

# --- Code Under Review ---
# IMPORTANT: line numbers below are 1-indexed within this string (not the .py file).
# Line 11-16 : N+1 query (performance/major)
# Line 13-14 : SQL injection via concatenation (security/critical)
# Line 20    : error detail leak (security/major)
# Line 24-25 : no auth middleware (security/critical)
# Line 29-33 : missing await on INSERT (bug/critical)

CODE = """\
const express = require('express');
const router  = express.Router();
const db      = require('../db');

// GET /posts — fetch all posts with author details
router.get('/posts', async (req, res) => {
  try {
    const posts   = await db.query('SELECT * FROM posts');
    const results = [];

    for (const post of posts.rows) {                         // N+1: one DB round-trip per post
      const authorQuery =
        'SELECT * FROM users WHERE id = ' + post.author_id;  // SQL injection via concatenation
      const author = await db.query(authorQuery);
      results.push({ ...post, author: author.rows[0] });
    }

    res.json(results);
  } catch (err) {
    res.status(500).send(err);                               // leaks stack trace / internal details
  }
});

// POST /posts — create a new post
router.post('/posts', async (req, res) => {                  // no authentication check
  const { title, content, author_id } = req.body;
  const created_at = new Date().toISOString();

  // Missing await — INSERT runs fire-and-forget; errors are silently swallowed
  db.query(
    'INSERT INTO posts (title, content, author_id, created_at) VALUES ($1, $2, $3, $4)',
    [title, content, author_id, created_at]
  );

  res.status(201).json({ message: 'Post created' });
});

module.exports = router;
"""

# --- Ground Truth Issues ---

GROUND_TRUTH_ISSUES = [
    Issue(
        issue_type=IssueType.performance,
        severity=Severity.major,
        line_start=11,
        line_end=16,
        description=(
            "N+1 query problem: for every post returned by the initial SELECT, a second "
            "database round-trip is made inside the loop to fetch the author. With N posts "
            "this produces N+1 total queries, causing severe latency at scale."
        ),
        suggestion=(
            "Replace the loop with a single JOIN query: "
            "`SELECT posts.*, users.* FROM posts JOIN users ON users.id = posts.author_id`. "
            "This fetches all data in one round-trip regardless of result size."
        ),
    ),
    Issue(
        issue_type=IssueType.security,
        severity=Severity.critical,
        line_start=13,
        line_end=14,
        description=(
            "SQL injection via string concatenation: `post.author_id` is interpolated "
            "directly into the query string using `+`. If `author_id` is ever user-controlled "
            "or sourced from untrusted storage, an attacker can inject arbitrary SQL."
        ),
        suggestion=(
            "Use a parameterised query with a placeholder: "
            "`db.query('SELECT * FROM users WHERE id = $1', [post.author_id])`. "
            "Never build SQL strings by concatenating values."
        ),
    ),
    Issue(
        issue_type=IssueType.security,
        severity=Severity.major,
        line_start=20,
        line_end=20,
        description=(
            "Internal error detail leak: `res.status(500).send(err)` serialises the raw "
            "Error object (including stack trace, file paths, and query strings) and sends "
            "it to the client, providing valuable reconnaissance data to an attacker."
        ),
        suggestion=(
            "Return a generic message instead and log the full error server-side: "
            "`console.error(err); res.status(500).json({ error: 'Internal server error' })`."
        ),
    ),
    Issue(
        issue_type=IssueType.security,
        severity=Severity.critical,
        line_start=24,
        line_end=25,
        description=(
            "Missing authentication: the POST /posts route has no authentication or "
            "authorisation check, allowing any unauthenticated client to create posts "
            "on behalf of any `author_id`."
        ),
        suggestion=(
            "Add an authentication middleware before the handler, e.g.: "
            "`router.post('/posts', requireAuth, async (req, res) => { ... })`. "
            "Also validate that `author_id` matches the authenticated user's identity."
        ),
    ),
    Issue(
        issue_type=IssueType.bug,
        severity=Severity.critical,
        line_start=29,
        line_end=33,
        description=(
            "Missing `await` on the INSERT query: `db.query(...)` returns a Promise that "
            "is never awaited. The response is sent immediately before the insert completes, "
            "meaning the client receives a 201 even when the insert fails, and database "
            "errors are silently swallowed."
        ),
        suggestion=(
            "Await the query inside a try/catch block:\n"
            "  try {\n"
            "    await db.query('INSERT INTO posts ...', [...]);\n"
            "    res.status(201).json({ message: 'Post created' });\n"
            "  } catch (err) {\n"
            "    console.error(err);\n"
            "    res.status(500).json({ error: 'Internal server error' });\n"
            "  }"
        ),
    ),
]
