# Tools Directory

Python scripts that make API calls, process data, and execute specific tasks for the SLE exam simulator.

## Tools

| Tool | Purpose | API Calls |
|---|---|---|
| `generate_exam.py` | Generate SLE exam questions via DeepSeek API. Randomizes option positions post-generation. Supports single-context regeneration for quality fixes. | 1 (generation) + 0-N (regeneration) |
| `evaluate_exam.py` | Grade answers deterministically, generate grammar explanations for wrong answers via DeepSeek API, save feedback markdown, log errors to tracking file. | 1 (explanations) |
| `review_exam.py` | Adversarial QA review of exam questions and feedback explanations at temperature 0.1. Includes deterministic duplicate-option detection and system error logging. | 1-2 (exam review + optional feedback review) |

## Key Functions

### generate_exam.py
- `generate_exam(num_questions)` — generate a full exam (5-40 questions)
- `regenerate_context(context, contexts, start_qid, flagged_issues)` — replace a single flagged context with structured error details and structural validation
- `resave_exam_markdown(exam_data)` — re-save exam file after regeneration

### evaluate_exam.py
- `evaluate_exam(exam, user_answers)` — grade answers and generate explanations
- `regenerate_explanations(incorrect_items)` — re-generate flagged explanations with previous explanation + reviewer feedback for targeted correction
- `resave_feedback_markdown(evaluation)` — re-save feedback file after corrections

### review_exam.py
- `review_exam_quality(exam_data)` — validate exam questions (post-generation)
- `review_feedback_quality(evaluation_data)` — validate grammar explanations (post-evaluation)
- `log_system_errors(session_id, review_type, review_result)` — log flagged issues to `system_error_tracking.md`

## Conventions

- All tools load credentials from `.env` via `python-dotenv`
- DeepSeek API accessed via `openai` SDK with `base_url="https://api.deepseek.com"`
- JSON response format enforced on all API calls
- Temperature varies by purpose: 0.7 (generation), 0.3 (evaluation/regeneration), 0.1 (review)
