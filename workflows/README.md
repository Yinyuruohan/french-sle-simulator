# Workflows Directory

This directory contains **Standard Operating Procedures (SOPs)** written in Markdown for the SLE exam simulator and LLM Grader.

## Available Workflows

| Workflow | Description |
|---|---|
| `sle_exam_simulator.md` | Full SOP for the exam pipeline: generation, quality review, exam administration, evaluation, and results display |
| `llm_grader.md` | SOP for the expert review interface: Flask startup, list/detail navigation, review submission, and snapshot staleness detection |

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
