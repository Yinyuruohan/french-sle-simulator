# Product Requirement Document (PRD) — French SLE Written Expression Simulator

## 1. Product Overview

**Product Name:** French SLE Written Expression Simulator
**Version:** MVP v1.0
**Last Updated:** 2026-02-12

An AI-powered practice tool for the Canadian federal Public Service Commission's **Second Language Evaluation (SLE) — Test of Written Expression**. Generates realistic exam questions, grades answers, provides detailed French grammar feedback, and tracks errors for adaptive learning.

**Target Users:** Canadian federal public servants preparing for the SLE Written Expression exam (levels A, B, C).

**Problem Statement:** The official PSC SLE exam has limited publicly available practice material. Candidates need a way to practice with realistic, format-accurate questions and receive immediate, detailed grammar feedback — especially on their specific weak areas.

---

## 2. Goals and Success Metrics

### Goals

| # | Goal | Rationale |
|---|---|---|
| G1 | Provide unlimited, realistic practice exams in the official SLE format | Addresses the scarcity of public practice material |
| G2 | Deliver immediate, accurate grammar feedback on every wrong answer | Accelerates learning vs. taking a practice test with no feedback |
| G3 | Adapt to individual weaknesses over time | Personalized practice is more efficient than generic drills |
| G4 | Ensure quality through automated review before content reaches the user | AI-generated content can contain errors; a second-pass review catches them |

### Success Metrics

| Metric | Target | How Measured |
|---|---|---|
| Exam generation success rate | >= 95% of exams generate without fatal errors | App error logs |
| QA review pass rate | >= 70% of generated exams pass review with zero critical issues on first attempt | `system_error_tracking.md` |
| Regeneration fix rate | >= 80% of critical issues resolved after one regeneration | `system_error_tracking.md` (compare pre/post review) |
| Grammar feedback accuracy | >= 90% of explanations pass feedback review | `system_error_tracking.md` |
| User engagement | Users complete full exam cycle (generate → answer → review results) | Session state progression |

---

## 3. User Personas

### Primary: Federal Employee Preparing for SLE

- Works in a federal department, needs B or C level for bilingual positions
- Has intermediate French but struggles with specific grammar areas (prepositions, agreement, conjugation)
- Limited time — practices in 15-30 minute sessions
- Wants targeted practice, not generic French courses

### Secondary: Language Training Instructor

- Uses the tool to generate practice material for students
- Values the configurable question count and format accuracy
- Interested in the error tracking data to identify common weak areas

---

## 4. MVP v1.0 — Current State (Shipped)

### 4.1 Feature Summary

| Feature | Status | Description |
|---|---|---|
| Bilingual web UI | Done | Streamlit app with English/French interface, 4 stages: welcome, setup, exam, results |
| Two question types | Done | Fill-in-the-blank (~75%) and error identification (~25%), matching the official ratio |
| Configurable exam length | Done | 5 to 40 questions, user-selected |
| Canadian workplace contexts | Done | Passages use emails, memos, policies, meeting invitations, announcements |
| AI-powered question generation | Done | DeepSeek API with few-shot examples and JSON-structured output |
| Randomized answer positions | Done | Post-generation shuffling of A/B/C/D so correct answers aren't predictable |
| Automated exam quality review | Done | Adversarial AI reviewer (temp 0.1) + deterministic duplicate detection |
| Targeted context regeneration | Done | Critical issues trigger per-context regeneration with structured error feedback and structural validation |
| Deterministic grading | Done | Scores compared against answer key, no AI involved in scoring |
| Grammar feedback generation | Done | DeepSeek API generates why_incorrect, why_correct, grammar_rule for each wrong answer |
| Feedback quality review | Done | Adversarial reviewer validates grammar explanations; critical issues trigger regeneration |
| SLE level estimation | Done | Simplified proportional scoring: C >= 90%, B >= 70%, A >= 50% |
| User error tracking | Done | Persistent `user_error_tracking.md` logs every wrong answer across sessions |
| Adaptive question generation | Done | Reads error history to bias generation toward weak grammar areas |
| System QA tracking | Done | Persistent `system_error_tracking.md` logs all review-flagged issues |
| Exam + feedback markdown export | Done | Every session saves exam and feedback as readable `.md` files in `.tmp/` |

### 4.2 Architecture

**Framework:** WAT (Workflows, Agents, Tools)

```
Layer 1: Workflows    →  Markdown SOPs defining processes (workflows/)
Layer 2: Agents       →  Orchestration layer (Claude Code / app.py)
Layer 3: Tools        →  Python scripts making API calls (tools/)
```

**Tech Stack:**

| Component | Technology |
|---|---|
| AI Engine | DeepSeek (`deepseek-chat`) via OpenAI-compatible SDK |
| Web UI | Streamlit |
| Language | Python 3.10+ |
| Dependencies | `openai`, `streamlit`, `python-dotenv`, `requests` |

**Pipeline Flow:**

```
User selects question count
        │
        ▼
┌─────────────────┐
│  generate_exam() │  ← DeepSeek API (temp 0.7)
│  + shuffle opts  │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│ review_exam_quality()│  ← Deterministic checks + DeepSeek API (temp 0.1)
│  + duplicate detect  │
└────────┬────────────┘
         │ critical? → regenerate_context() + re-review
         ▼
┌─────────────────┐
│  User takes exam │  ← Streamlit form with radio buttons
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│  evaluate_exam()  │  ← Deterministic scoring + DeepSeek API (temp 0.3)
└────────┬─────────┘
         │
         ▼
┌───────────────────────┐
│review_feedback_quality()│  ← DeepSeek API (temp 0.1)
│  + regen if critical    │
└────────┬───────────────┘
         │
         ▼
┌────────────────┐
│  Show results   │  ← Score, level, per-question explanations
└────────────────┘
```

### 4.3 File Structure

```
french_sle_simulator/
├── app.py                           # Streamlit entry point (4 stages)
├── tools/
│   ├── generate_exam.py             # Generation + shuffling + regeneration + validation
│   ├── evaluate_exam.py             # Grading + explanations + error tracking
│   └── review_exam.py               # Adversarial QA review + system error logging
├── workflows/
│   └── sle_exam_simulator.md        # Full SOP for the exam workflow
├── contexts/
│   └── fr-written-test-booklet-100919.pdf  # Official PSC test reference
├── .tmp/                            # Generated exams + feedback (disposable)
├── user_error_tracking.md           # Persistent user error log
├── system_error_tracking.md         # Persistent system QA log
├── .env                             # API keys (gitignored)
├── .env.template                    # Environment variable template
├── requirements.txt                 # Python dependencies
├── CLAUDE.md                        # Agent operating instructions
├── MVP-roadmap.md                   # This file
└── README.md                        # Project documentation
```

### 4.4 API Cost Profile

| Scenario | DeepSeek API Calls |
|---|---|
| Best case (all pass, all correct) | 2 (generation + exam review) |
| Typical (some wrong, no critical) | 4 (+ evaluation explanations + feedback review) |
| Worst case (critical at both points) | ~8 (+ regeneration + re-reviews) |

Review calls use `max_tokens: 4000` (compact JSON) vs. 8000 for generation. All calls use `response_format: json_object`.

### 4.5 Quality Assurance Pipeline

```
1. Deterministic    →  Duplicate option detection (programmatic, zero cost)
2. AI exam review   →  Adversarial QA at temp 0.1
3. Regeneration     →  Structured error feedback + structural validation (max 1 retry)
4. Feedback review  →  Grammar explanation validation at temp 0.1
5. Error logging    →  All flagged issues tracked in system_error_tracking.md
```

**Severity model:**

| Level | Meaning | Action |
|---|---|---|
| Critical | Wrong answer key, multiple correct, no real error, duplicate options, misleading explanation | Automatic regeneration (1 attempt) |
| Warning | Weak distractor, imprecise topic label | Flag to user, proceed |

### 4.6 Known Limitations (v1.0)

| # | Limitation | Impact |
|---|---|---|
| L1 | Same AI model generates and reviews — may share blind spots | Some errors slip through both passes |
| L2 | Scoring is simplified proportional thresholds, not official PSC methodology | Results are estimates, not predictions of official scores |
| L3 | No exam timer | Doesn't simulate the 45-minute time pressure |
| L4 | Error identification questions depend on AI placing errors correctly | Occasionally the "error" segment has no real error |
| L5 | No question caching — every exam is generated fresh | Slower start, higher API costs, no reuse of validated questions |
| L6 | Flat tracking file — no analytics or visualization | Users can't see progress trends |
| L7 | Single AI provider (DeepSeek) — no fallback | Service outage = app unavailable |

---

## 5. Roadmap — Future Versions

### Phase 2: Timer and UX Polish

| Feature | Priority | Description | Effort |
|---|---|---|---|
| Countdown timer | High | 45-minute timer matching the official exam window, with configurable time-per-question | Small |
| Progress bar | Medium | Show question N of M during the exam | Small |
| Exam navigation | Medium | Allow jumping between questions (currently linear) | Medium |
| Flag for review | Low | Let users mark uncertain questions to revisit before submission | Medium |

### Phase 3: Question Bank and Caching

| Feature | Priority | Description | Effort |
|---|---|---|---|
| Question bank | High | Cache validated questions in a local database; serve from cache for instant exams | Large |
| Quality scoring | Medium | Track per-question pass/fail rate from reviews; auto-retire low-quality questions | Medium |
| Deduplication | Medium | Detect semantically similar questions across sessions to avoid repetition | Medium |

### Phase 4: Analytics Dashboard

| Feature | Priority | Description | Effort |
|---|---|---|---|
| Progress dashboard | High | Visualize score trends, grammar-area breakdown, session history | Medium |
| Weak area heatmap | Medium | Show which grammar categories have the most errors over time | Medium |
| Session comparison | Low | Side-by-side comparison of two exam sessions | Small |

### Phase 5: Difficulty Targeting

| Feature | Priority | Description | Effort |
|---|---|---|---|
| Difficulty levels | High | Generate exams targeting specific SLE levels (A, B, or C difficulty) | Medium |
| Adaptive difficulty | Medium | Auto-adjust difficulty based on recent performance | Medium |
| Mixed difficulty | Low | Create exams with a gradient from easy to hard questions | Small |

### Phase 6: Export and Sharing

| Feature | Priority | Description | Effort |
|---|---|---|---|
| PDF export | High | Export exam results as a formatted PDF report | Medium |
| Print-friendly exam | Medium | Generate a printable exam version (no interactive UI) | Small |
| Shareable results link | Low | Generate a unique URL for exam results | Large |

### Phase 7: Infrastructure

| Feature | Priority | Description | Effort |
|---|---|---|---|
| Multi-provider AI fallback | Medium | Add OpenAI / Anthropic as backup providers if DeepSeek is unavailable | Medium |
| User authentication | Low | Optional accounts to persist data across devices | Large |
| Cloud deployment | Low | Deploy to Streamlit Cloud or similar for public access | Medium |
| Database backend | Low | Replace markdown tracking files with SQLite or PostgreSQL | Medium |

---

## 6. Exam Format Specification

For reference, the current exam format matches the official PSC SLE Written Expression structure:

### Fill-in-the-Blank (75% of questions)

- Workplace passage with numbered blanks: `(1) _______________`
- Each blank is a separate question with 4 options (A/B/C/D)
- 1-2 blanks per passage
- Tests: prepositions, conjugation, agreement, pronouns, tense, vocabulary, syntax

### Error Identification (25% of questions)

- Workplace passage with 3 bolded segments
- One question per passage: "which segment contains an error?"
- Options A/B/C = the three segments, D = "Aucun des choix offerts." (none of the above)
- Tests: past participle agreement, gender/number agreement, spelling, syntax

### Scoring

| Level | Threshold | Meaning |
|---|---|---|
| C | >= 90% | Advanced — can work in French without limitation |
| B | >= 70% | Intermediate — can work in French with some limitations |
| A | >= 50% | Basic — limited ability to work in French |
| Below A | < 50% | Insufficient for bilingual positions |

*These are simplified proportional thresholds, not the official PSC scoring methodology.*

---

## 7. Technical Constraints

| Constraint | Details |
|---|---|
| AI model | DeepSeek `deepseek-chat` — affordable but less accurate than GPT-4 / Claude for French |
| Response format | JSON-only (`response_format: json_object`) — reliable parsing but limits creativity |
| Temperature tradeoffs | 0.7 generation (variety) vs. 0.1 review (consistency) — single model can't be both creative and strict |
| Regeneration cap | Max 1 retry per context/explanation — prevents cost explosion but may leave issues unfixed |
| Streamlit limitations | No persistent sessions, no real-time collaboration, limited custom components |
| Tracking files | Markdown-based, append-only — simple but not queryable, no rollback |

---

## 8. Glossary

| Term | Definition |
|---|---|
| **SLE** | Second Language Evaluation — the Canadian federal government's official language proficiency test |
| **PSC** | Public Service Commission of Canada — administers the SLE |
| **WAT** | Workflows, Agents, Tools — the architectural framework used in this project |
| **Context** | A numbered passage containing 1-2 questions (fill-in-blank) or 1 question (error identification) |
| **Distractor** | An incorrect option in a multiple-choice question, designed to be plausible but wrong |
| **Adversarial review** | A QA pattern where the reviewer is explicitly framed as an opponent to the generator |
| **Regeneration** | Replacing a flagged context/explanation with a new one generated from a prompt that includes the original errors |
