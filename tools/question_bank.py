"""
SLE Question Bank

Caches validated exam contexts in a local SQLite database for instant
exam assembly. Contexts (including explanations) are stored after passing
quality review. Reviewed contexts upgrade to battle_tested after a
successful exam cycle.
"""

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "question_bank.db")


def _get_conn() -> sqlite3.Connection:
    """Get a SQLite connection to the question bank database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the question bank database and table if they don't exist.
    Detects old schema (missing user_flags) and recreates from scratch."""
    conn = _get_conn()
    try:
        # Check if table exists and has correct schema
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contexts'"
        )
        if cursor.fetchone():
            cols = {row[1] for row in conn.execute("PRAGMA table_info(contexts)").fetchall()}
            if "user_flags" not in cols:
                conn.execute("DROP TABLE contexts")
                conn.commit()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS contexts (
                context_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                passage TEXT NOT NULL,
                questions_json TEXT NOT NULL,
                num_questions INTEGER NOT NULL,
                grammar_topics TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'reviewed',
                source_session TEXT NOT NULL,
                created_at TEXT NOT NULL,
                times_served INTEGER NOT NULL DEFAULT 0,
                passage_hash TEXT NOT NULL,
                last_incorrect INTEGER NOT NULL DEFAULT 0,
                user_flags INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _passage_hash(passage: str) -> str:
    """SHA-256 hash of normalized passage text for deduplication."""
    normalized = passage.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def cache_contexts(exam_data: dict, status: str = "reviewed"):
    """
    Extract each context from an exam dict and insert into the bank.
    Extracts type from each context dict and collects grammar_topics from
    each question's grammar_topic field. Deduplicates by passage text hash —
    skips if a context with the same passage already exists.
    """
    conn = _get_conn()
    try:
        session_id = exam_data.get("session_id", "unknown")
        now = datetime.now().isoformat()

        for ctx in exam_data.get("contexts", []):
            p_hash = _passage_hash(ctx["passage"])

            # Check for duplicate
            existing = conn.execute(
                "SELECT 1 FROM contexts WHERE passage_hash = ?", (p_hash,)
            ).fetchone()
            if existing:
                continue

            questions = ctx.get("questions", [])
            # Strip question_id from stored questions (reassigned at assembly)
            stored_questions = []
            for q in questions:
                stored_questions.append({
                    "options": q["options"],
                    "correct_answer": q["correct_answer"],
                    "grammar_topic": q["grammar_topic"],
                    "explanation": q.get("explanation"),
                })

            topics = ",".join(q["grammar_topic"] for q in questions)

            conn.execute(
                """INSERT INTO contexts
                   (context_id, type, passage, questions_json, num_questions,
                    grammar_topics, status, source_session, created_at,
                    times_served, passage_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    str(uuid.uuid4()),
                    ctx["type"],
                    ctx["passage"],
                    json.dumps(stored_questions, ensure_ascii=False),
                    len(questions),
                    topics,
                    status,
                    session_id,
                    now,
                    p_hash,
                ),
            )

        conn.commit()
    finally:
        conn.close()


def get_bank_stats() -> dict:
    """Return question bank statistics."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*), COALESCE(SUM(num_questions), 0) FROM contexts GROUP BY status"
        ).fetchall()
    finally:
        conn.close()

    stats = {
        "total_contexts": 0, "total_questions": 0,
        "reviewed": 0, "battle_tested": 0, "warned": 0,
        "reviewed_questions": 0, "battle_tested_questions": 0, "warned_questions": 0,
    }
    for row in rows:
        status, count, q_sum = row[0], row[1], row[2]
        stats["total_contexts"] += count
        stats["total_questions"] += q_sum
        if status in ("reviewed", "battle_tested", "warned"):
            stats[status] = count
            stats[f"{status}_questions"] = q_sum

    return stats


def flag_context(bank_context_id: str = None, passage_hash: str = None, category: str = ""):
    """Increment user_flags for a context. Logs to system_error_tracking.md."""
    conn = _get_conn()
    try:
        if bank_context_id:
            conn.execute(
                "UPDATE contexts SET user_flags = user_flags + 1 WHERE context_id = ?",
                (bank_context_id,),
            )
        elif passage_hash:
            conn.execute(
                "UPDATE contexts SET user_flags = user_flags + 1 WHERE passage_hash = ?",
                (passage_hash,),
            )
        conn.commit()
    finally:
        conn.close()

    # Log to system error tracking
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ctx_ref = bank_context_id or passage_hash or "unknown"
    lines = [
        f"\n## User Flag — Context: {ctx_ref}",
        f"**Date:** {timestamp}",
        f"**Category:** {category}",
        "",
        "---",
        "",
    ]
    tracking_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "system_error_tracking.md")
    if not os.path.exists(tracking_file):
        header = "# System Error Tracking / Suivi des erreurs systeme\n\nThis file logs all issues flagged by the automated quality review agent across exam sessions.\n\n---\n"
        with open(tracking_file, "w", encoding="utf-8") as f:
            f.write(header)
    with open(tracking_file, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def upgrade_to_battle_tested(source_session: str, evaluation: dict):
    """Upgrade cached contexts from 'reviewed' to 'battle_tested'.
    Explanations are already stored in questions_json from generation.
    Only 'reviewed' contexts upgrade — 'warned' contexts stay permanently.
    Matches by bank_context_id or passage_hash (not source_session, which
    differs for cached exams that get a new session_id at assembly)."""
    # Build set of context identifiers from evaluation for matching
    bank_ids = set()
    hash_ids = set()
    for ctx_r in evaluation.get("context_results", []):
        bank_id = ctx_r.get("bank_context_id")
        if bank_id:
            bank_ids.add(bank_id)
        orig_hash = ctx_r.get("original_passage_hash")
        p_hash = orig_hash or _passage_hash(ctx_r["passage"])
        hash_ids.add(p_hash)

    if not bank_ids and not hash_ids:
        return

    conn = _get_conn()
    try:
        # Match by bank_context_id first, then fall back to passage_hash
        for bank_id in bank_ids:
            conn.execute(
                "UPDATE contexts SET status = 'battle_tested' WHERE context_id = ? AND status = 'reviewed'",
                (bank_id,),
            )
        # Also match by passage_hash for contexts without bank_context_id
        for p_hash in hash_ids:
            conn.execute(
                "UPDATE contexts SET status = 'battle_tested' WHERE passage_hash = ? AND status = 'reviewed'",
                (p_hash,),
            )
        conn.commit()
    finally:
        conn.close()


def assemble_exam_from_cache(num_questions: int) -> dict:
    """
    Assemble an exam from cached contexts with even grammar topic distribution
    and ~50/50 type mix.

    Args:
        num_questions: Target number of questions (best-fit: exact, then -1, then +1)

    Returns:
        dict with keys:
            available_questions: int — total questions in the bank
            exam: dict | None — full exam dict with "source": "cache", or None
    """
    conn = _get_conn()
    try:
        # Get total available
        total_row = conn.execute("SELECT COALESCE(SUM(num_questions), 0) FROM contexts").fetchone()
        available = total_row[0]

        # Calculate type mix targets
        num_fill = round(num_questions * 0.5)
        num_err = num_questions - num_fill

        # Check per-type availability
        fill_avail = conn.execute(
            "SELECT COALESCE(SUM(num_questions), 0) FROM contexts WHERE type = 'fill_in_blank'"
        ).fetchone()[0]
        err_avail = conn.execute(
            "SELECT COALESCE(SUM(num_questions), 0) FROM contexts WHERE type = 'error_identification'"
        ).fetchone()[0]

        # Adjust targets if one type is short — shift quota to the other type
        if fill_avail < num_fill:
            num_fill = fill_avail
            num_err = min(num_questions - num_fill, err_avail)
        elif err_avail < num_err:
            num_err = err_avail
            num_fill = min(num_questions - num_err, fill_avail)

        if num_fill + num_err == 0:
            return {"available_questions": available, "exam": None}

        # Fetch all contexts grouped by type, quality-preferred then least-served
        fill_rows = conn.execute(
            "SELECT context_id, type, passage, questions_json, num_questions, grammar_topics, status, user_flags "
            "FROM contexts WHERE type = 'fill_in_blank' "
            "ORDER BY "
            "  CASE WHEN user_flags >= 1 THEN 1 ELSE 0 END, "
            "  CASE status WHEN 'battle_tested' THEN 0 WHEN 'reviewed' THEN 1 WHEN 'warned' THEN 2 END, "
            "  times_served ASC, RANDOM()"
        ).fetchall()
        err_rows = conn.execute(
            "SELECT context_id, type, passage, questions_json, num_questions, grammar_topics, status, user_flags "
            "FROM contexts WHERE type = 'error_identification' "
            "ORDER BY "
            "  CASE WHEN user_flags >= 1 THEN 1 ELSE 0 END, "
            "  CASE status WHEN 'battle_tested' THEN 0 WHEN 'reviewed' THEN 1 WHEN 'warned' THEN 2 END, "
            "  times_served ASC, RANDOM()"
        ).fetchall()

        # Select contexts with even topic distribution
        selected = []
        selected += _select_contexts_evenly(fill_rows, num_fill)
        selected += _select_contexts_evenly(err_rows, num_err)

        if not selected:
            return {"available_questions": available, "exam": None}

        # Update times_served
        for row in selected:
            conn.execute(
                "UPDATE contexts SET times_served = times_served + 1 WHERE context_id = ?",
                (row[0],),
            )
        conn.commit()
    finally:
        conn.close()

    # Build exam dict
    exam = _build_exam_from_rows(selected)
    return {"available_questions": available, "exam": exam}


def _select_contexts_evenly(rows: list, target_questions: int) -> list:
    """
    Select contexts from rows aiming for even grammar topic distribution.
    Uses best-fit strategy: (1) try exact match, (2) try target-1, (3) allow target+1.
    Never exceeds target by more than 1.

    Each row is: (context_id, type, passage, questions_json, num_questions, grammar_topics, status, user_flags)
    """
    if not rows or target_questions <= 0:
        return []

    # Parse each row's topics for selection logic
    parsed = []
    for row in rows:
        topics = row[5].split(",")
        num_q = row[4]
        parsed.append((row, topics, num_q))

    def _greedy_select(parsed_rows, max_questions):
        """Greedy selection: pick contexts whose topics are least represented, up to max_questions."""
        topic_counts = {}
        selected = []
        total_q = 0
        remaining = list(parsed_rows)

        while remaining and total_q < max_questions:
            best = None
            best_score = float("inf")

            for item in remaining:
                row, topics, num_q = item
                if total_q + num_q > max_questions:
                    continue
                score = sum(topic_counts.get(t, 0) for t in topics)
                if score < best_score:
                    best_score = score
                    best = item

            if best is None:
                break

            row, topics, num_q = best
            selected.append(row)
            total_q += num_q
            for t in topics:
                topic_counts[t] = topic_counts.get(t, 0) + 1
            remaining.remove(best)

        return selected, total_q

    # Best-fit strategy: try exact, then target-1, then target+1
    for limit in [target_questions, target_questions - 1, target_questions + 1]:
        if limit <= 0:
            continue
        selected, total_q = _greedy_select(parsed, limit)
        if total_q == limit:
            return selected

    # If none hit exactly, return the best attempt (exact target or under)
    selected, _ = _greedy_select(parsed, target_questions)
    return selected


def _build_exam_from_rows(rows: list) -> dict:
    """
    Build a valid exam dict from selected database rows.
    Renumbers context_ids, question_ids, and passage blank markers.
    Stores original_passage_hash as fallback for post-exam matching.

    Each row is: (context_id, type, passage, questions_json, num_questions, grammar_topics, status, user_flags)
    """
    contexts = []
    question_id = 1
    blank_pattern = re.compile(r"\((\d+)\)\s*_+")

    for ctx_idx, row in enumerate(rows, start=1):
        db_ctx_id, ctx_type, passage, questions_json_str, num_q, topics, status, user_flags = row
        questions = json.loads(questions_json_str)

        # Store original passage hash before any renumbering (fallback for post-exam matching)
        orig_p_hash = _passage_hash(passage)

        # Build question_id mapping for passage renumbering
        new_questions = []
        old_to_new = {}

        for i, q in enumerate(questions):
            new_qid = question_id + i
            old_to_new[i] = new_qid
            new_questions.append({
                "question_id": new_qid,
                "options": q["options"],
                "correct_answer": q["correct_answer"],
                "grammar_topic": q["grammar_topic"],
                "explanation": q.get("explanation"),
            })

        # Renumber passage blank markers for fill_in_blank only
        if ctx_type == "fill_in_blank":
            blank_idx = [0]  # mutable counter for closure

            def replace_blank(match, _new_questions=new_questions, _counter=blank_idx):
                idx = _counter[0]
                if idx < len(_new_questions):
                    new_id = _new_questions[idx]["question_id"]
                    _counter[0] += 1
                    return f"({new_id}) _______________"
                return match.group(0)

            passage = blank_pattern.sub(replace_blank, passage)

        contexts.append({
            "context_id": ctx_idx,
            "type": ctx_type,
            "passage": passage,
            "questions": new_questions,
            "bank_context_id": db_ctx_id,
            "original_passage_hash": orig_p_hash,
            "bank_status": status,
        })

        question_id += len(questions)

    timestamp = datetime.now()
    session_id = f"exam_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    total_q = sum(len(ctx["questions"]) for ctx in contexts)

    return {
        "session_id": session_id,
        "timestamp": timestamp.isoformat(),
        "num_questions": total_q,
        "contexts": contexts,
        "source": "cache",
    }


def prefill_bank(num_questions: int, model_configs: dict) -> dict:
    """Generate, review, and cache contexts. Warned contexts get 'warned' status."""
    from tools.generate_exam import generate_exam
    from tools.review_exam import review_exam_quality

    exam = generate_exam(num_questions, model_config=model_configs["generate"])
    review = review_exam_quality(exam, model_config=model_configs["review"])

    # Collect context IDs with critical/warning issues
    critical_ctx_ids = set()
    warned_ctx_ids = set()
    for f in review.get("flagged_questions", []):
        ctx_id = f.get("context_id")
        if not ctx_id:
            continue
        if f.get("severity") == "critical":
            critical_ctx_ids.add(ctx_id)
        elif f.get("severity") == "warning":
            warned_ctx_ids.add(ctx_id)

    # Remove critical contexts
    clean_contexts = [
        ctx for ctx in exam.get("contexts", [])
        if ctx["context_id"] not in critical_ctx_ids
    ]

    if not clean_contexts:
        return {"success": False, "message": "All generated contexts had critical quality issues. Try again."}

    # Split into warned and reviewed
    warned_contexts = [ctx for ctx in clean_contexts if ctx["context_id"] in warned_ctx_ids]
    reviewed_contexts = [ctx for ctx in clean_contexts if ctx["context_id"] not in warned_ctx_ids]

    # Cache each group with appropriate status
    if reviewed_contexts:
        reviewed_exam = dict(exam)
        reviewed_exam["contexts"] = reviewed_contexts
        cache_contexts(reviewed_exam, status="reviewed")

    if warned_contexts:
        warned_exam = dict(exam)
        warned_exam["contexts"] = warned_contexts
        cache_contexts(warned_exam, status="warned")

    cached_q = sum(len(ctx.get("questions", [])) for ctx in clean_contexts)
    warned_count = len(warned_contexts)
    msg = f"Cached {cached_q} questions from {len(clean_contexts)} contexts"
    if warned_count:
        msg += f" ({warned_count} warned)"
    msg += "."
    if critical_ctx_ids:
        msg += f" ({len(critical_ctx_ids)} context(s) excluded due to quality issues.)"
    return {"success": True, "message": msg}


def update_last_incorrect(evaluation: dict):
    """
    For each context in the evaluation, sets last_incorrect to 0 if all questions
    were answered correctly, or 1 if any question was answered incorrectly.
    Matches by bank_context_id (UUID) first, then original_passage_hash, then
    passage_hash for fresh exams.

    Args:
        evaluation: The evaluation dict from evaluate_exam() or cached evaluation
    """
    conn = _get_conn()
    try:
        for ctx_r in evaluation.get("context_results", []):
            has_incorrect = any(
                not q_r.get("is_correct", True)
                for q_r in ctx_r["question_results"]
            )
            flag = 1 if has_incorrect else 0

            bank_id = ctx_r.get("bank_context_id")
            orig_hash = ctx_r.get("original_passage_hash")
            if bank_id:
                conn.execute(
                    "UPDATE contexts SET last_incorrect = ? WHERE context_id = ?",
                    (flag, bank_id),
                )
            elif orig_hash:
                # Cached exam with original_passage_hash fallback
                conn.execute(
                    "UPDATE contexts SET last_incorrect = ? WHERE passage_hash = ?",
                    (flag, orig_hash),
                )
            else:
                # Fresh exam — match by passage hash
                p_hash = _passage_hash(ctx_r["passage"])
                conn.execute(
                    "UPDATE contexts SET last_incorrect = ? WHERE passage_hash = ?",
                    (flag, p_hash),
                )
        conn.commit()
    finally:
        conn.close()
