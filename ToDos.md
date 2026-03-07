# ToDos — Areas for Improvement

Identified from end-to-end Playwright testing on 2026-03-07.

---

## 1. Quality Review Triggers Too Aggressively
The reviewer flagged questions on a 5-question exam and triggered full context regeneration, adding 2–3 minutes to setup time. For a practice tool, this is excessive.
- [ ] Raise the threshold for what counts as "critical" vs. surfacing minor issues as warnings only
- [ ] Review `review_exam.py` severity classification logic

## 2. No Progress Indication During Regeneration
When "Fixing flagged questions..." runs, there's no indication of how many contexts are being regenerated or which API call is in progress. Users may think the app is frozen.
- [ ] Add step counter to spinner text (e.g. "Fixing context 1 of 2...")

## 3. Quality Warning Shown After Regeneration Already Fixed the Issue
The yellow warning banner on the exam page ("Some questions were flagged...") appears even after regeneration completed successfully. It's misleading.
- [ ] Only show the warning if flagged issues remain after regeneration, not if they were resolved
- [ ] Soften the message when regeneration ran and passed re-review

## 4. All Answers Default to Option A
Radio buttons default to "A" on load. A user who accidentally submits without selecting every answer will silently submit "A" for skipped questions.
- [ ] Remove default selection so all questions start with no answer selected
- [ ] Add a validation check before submission that warns if any question is unanswered

## 5. No Wait Time Feedback for Users
Total wait from "Generate exam" to exam page was ~3–4 minutes with no sense of progress beyond sequential spinner text swaps.
- [ ] Add a multi-step progress indicator (e.g. "Step 2 of 3: Reviewing quality...")
- [ ] Consider showing estimated wait time on the setup page

## 6. Inconsistent MCP Browser Config (Dev Environment)
The user-level `mcpServers` in `~/.claude.json` has `--browser msedge` while the project-level config has `--browser chromium`. These are inconsistent.
- [ ] Align both to `--browser chromium` (already installed, no admin required)
