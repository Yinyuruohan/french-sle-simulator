# Workflows Directory

This directory contains **Standard Operating Procedures (SOPs)** written in Markdown for the SLE exam simulator and LLM Grader.

## Available Workflows

| Workflow | Description |
|---|---|
| `sle_exam_simulator.md` | Full SOP for the Written Expression pipeline: generation, quality review, exam administration, evaluation, and results display |
| `llm_grader.md` | SOP for the expert review interface: Flask startup, list/detail navigation, review submission, snapshot staleness detection, and batch Excel export/import |

> **Reading Comprehension** runs inside the same Streamlit app as Written Expression (reachable from the shared top nav) but has no separate SOP in this directory yet. It is implemented by `tools/generate_reading_exam.py`, `tools/grade_reading_exam.py`, `tools/reading_question_bank.py`, and `tools/review_reading_exam.py`.

## What is a Workflow?

A workflow is a documented process that defines:
1. **Objective:** What we're trying to accomplish
2. **Required Inputs:** What information or resources are needed
3. **Tool Sequence:** Which tools to run and in what order
4. **Expected Outputs:** What the deliverables look like
5. **Edge Cases:** Known failure modes and how to handle them
6. **Learnings:** Updated based on real-world execution

## Best Practices

- Keep workflows focused on a single objective
- Update workflows after each run with new learnings
- Document failures and their solutions
- Link to related workflows when applicable
- Use clear, imperative language
