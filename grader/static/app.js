/* LLM Grader — SPA */
(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────────
  const state = {
    filters: JSON.parse(sessionStorage.getItem("grader_filters") || "{}"),
    contextList: [], // {context_id, type, status, user_flags, expert_rating}[]
    currentContextId: null,
  };

  function persistFilters() {
    sessionStorage.setItem("grader_filters", JSON.stringify(state.filters));
  }

  // ── API helpers ────────────────────────────────────────────────────────
  async function api(path, opts = {}) {
    const resp = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
    return data;
  }

  function queryString(filters) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v) params.set(k, v);
    }
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }

  // ── HTML escaping ──────────────────────────────────────────────────────
  function esc(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ── Toast ──────────────────────────────────────────────────────────────
  let _toastTimer = null;
  function showToast(msg, type = "success") {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = `toast ${type}`;
    if (_toastTimer) clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => el.classList.add("hidden"), 2500);
  }

  // ── Router ─────────────────────────────────────────────────────────────
  function route() {
    const hash = location.hash || "#/";
    const match = hash.match(/^#\/review\/(.+)$/);
    if (match) {
      renderDetailView(match[1]);
    } else {
      renderListView();
    }
  }

  // ── List View ──────────────────────────────────────────────────────────
  async function renderListView() {
    state.currentContextId = null;
    const main = document.getElementById("main");

    try {
      const data = await api(`/contexts${queryString(state.filters)}`);
      state.contextList = data.items;

      main.innerHTML = `
        <div class="filters">
          <div>
            <label>Status</label>
            <select id="f-status">
              <option value="">All</option>
              <option value="battle_tested">Battle Tested</option>
              <option value="reviewed">Reviewed</option>
              <option value="warned">Warned</option>
            </select>
          </div>
          <div>
            <label>Flags</label>
            <select id="f-flagged">
              <option value="">All</option>
              <option value="true">Flagged</option>
              <option value="false">Unflagged</option>
            </select>
          </div>
          <div>
            <label>Reviewed</label>
            <select id="f-reviewed">
              <option value="">All</option>
              <option value="true">Reviewed</option>
              <option value="false">Not Reviewed</option>
            </select>
          </div>
        </div>

        <div class="results-count" id="results-count"></div>

        <table class="ctx-table">
          <thead>
            <tr>
              <th>Context ID</th>
              <th>Status</th>
              <th>Flags</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody id="ctx-tbody"></tbody>
        </table>

        <div class="batch-actions">
          <a id="btn-download" class="btn-download" href="#">&#8595; Download Excel</a>
          <label class="btn-upload" for="upload-input">&#8593; Upload Excel</label>
          <input type="file" id="upload-input" accept=".xlsx" style="display:none">
          <span class="upload-status" id="upload-status"></span>
        </div>
      `;

      // Set filter values
      const setVal = (id, key) => {
        const el = document.getElementById(id);
        el.value = state.filters[key] || "";
        el.addEventListener("change", () => {
          state.filters[key] = el.value || undefined;
          if (!el.value) delete state.filters[key];
          persistFilters();
          renderListView();
        });
      };
      setVal("f-status", "status");
      setVal("f-flagged", "flagged");
      setVal("f-reviewed", "reviewed");

      // ── Download Excel ────────────────────────────────────────────────────
      document.getElementById("btn-download").addEventListener("click", function () {
        // Set href at click time so filters are always current
        this.href = `/api/export${queryString(state.filters)}`;
        // Allow browser default (follow link) to trigger the download
      });

      // ── Upload Excel ──────────────────────────────────────────────────────
      document.getElementById("upload-input").addEventListener("change", async function () {
        const file = this.files[0];
        if (!file) return;

        const statusEl = document.getElementById("upload-status");
        statusEl.textContent = "Uploading\u2026";
        statusEl.className = "upload-status";

        const formData = new FormData();
        formData.append("file", file);

        try {
          const resp = await fetch("/api/import", { method: "POST", body: formData });
          const data = await resp.json();

          if (!resp.ok) {
            statusEl.innerHTML = `<span style="color:#dc2626">Error: ${esc(data.error)}</span>`;
          } else {
            const msg = `Imported ${data.imported}, skipped ${data.skipped}`;
            showToast(msg, data.errors.length > 0 ? "error" : "success");

            if (data.errors.length > 0) {
              const items = data.errors
                .map((e) => `<li>${esc(e.context_id)}: ${esc(e.reason)}</li>`)
                .join("");
              statusEl.innerHTML = `<div class="import-errors"><strong>Errors (${data.errors.length}):</strong><ul>${items}</ul></div>`;
            } else {
              statusEl.textContent = "";
            }

            // Reload list to reflect updated review statuses
            renderListView();
          }
        } catch (err) {
          statusEl.innerHTML = `<span style="color:#dc2626">Error: ${esc(err.message)}</span>`;
        }

        // Reset so the same file can be re-uploaded if needed
        this.value = "";
      });

      // Render context count
      const hasFilters = Object.keys(state.filters).some((k) => state.filters[k]);
      const countEl = document.getElementById("results-count");
      const total = data.total;
      countEl.textContent = hasFilters
        ? `${total} context${total !== 1 ? "s" : ""} match the active filters`
        : `${total} context${total !== 1 ? "s" : ""} total`;

      // Render rows
      const tbody = document.getElementById("ctx-tbody");
      for (const item of data.items) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><span class="ctx-id">${item.context_id.slice(0, 8)}</span></td>
          <td><span class="badge badge-${item.status}">${item.status.replace("_", " ")}</span></td>
          <td>${item.user_flags > 0 ? `<span class="flags-red">${item.user_flags}</span>` : "0"}</td>
          <td>${item.expert_rating
            ? `<span class="badge badge-${esc(item.expert_rating.toLowerCase())}">${esc(item.expert_rating)}</span>`
            : `<span class="badge-none">not reviewed</span>`}</td>
        `;
        tr.addEventListener("click", () => {
          location.hash = `#/review/${item.context_id}`;
        });
        tbody.appendChild(tr);
      }
    } catch (err) {
      main.innerHTML = `<p style="color:#dc2626">Error loading contexts: ${esc(err.message)}</p>`;
    }
  }

  // ── Detail View ────────────────────────────────────────────────────────
  async function renderDetailView(contextId) {
    state.currentContextId = contextId;
    const main = document.getElementById("main");
    main.innerHTML = `<p>Loading...</p>`;

    // If contextList is empty (direct URL access), fetch unfiltered list
    if (state.contextList.length === 0) {
      try {
        const data = await api("/contexts");
        state.contextList = data.items;
      } catch (err) {
        main.innerHTML = `<p style="color:#dc2626">Error: ${esc(err.message)}</p>`;
        return;
      }
    }

    try {
      const detail = await api(`/contexts/${contextId}`);
      const idx = state.contextList.findIndex((c) => c.context_id === contextId);
      const total = state.contextList.length;

      // Guard: context not in the current filtered list (e.g. bookmarked URL with active filters)
      if (idx === -1) {
        const prevId = total > 0 ? state.contextList[total - 1].context_id : null;
        const nextId = total > 0 ? state.contextList[0].context_id : null;
        main.innerHTML = buildDetailHTML(detail, -1, total, prevId, nextId);
        bindDetailEvents(detail, prevId, nextId);
        renderSidebar(contextId);
        return;
      }

      const prevId = idx > 0 ? state.contextList[idx - 1].context_id : null;
      const nextId = idx < total - 1 ? state.contextList[idx + 1].context_id : null;

      main.innerHTML = buildDetailHTML(detail, idx, total, prevId, nextId);
      bindDetailEvents(detail, prevId, nextId);
      renderSidebar(contextId);
    } catch (err) {
      main.innerHTML = `<p style="color:#dc2626">Error: ${esc(err.message)}</p>`;
    }
  }

  function buildLlmEvaluatorHTML(review) {
    if (review && review.llm_evaluator_rating) {
      const badgeClass =
        review.llm_evaluator_rating === "Good" ? "badge-good" : "badge-bad";
      return `
        <div>
          <div class="meta-label">Rating</div>
          <div class="meta-value">
            <span class="badge ${badgeClass}">${esc(review.llm_evaluator_rating)}</span>
          </div>
        </div>
        <div style="margin-top:10px;">
          <div class="meta-label">Critique</div>
          <div class="meta-value">${esc(review.llm_evaluator_critique || "")}</div>
        </div>
        <div style="margin-top:12px;text-align:right;">
          <button class="btn-primary" id="btn-llm-review">Re-run</button>
        </div>`;
    }
    return `
      <div class="placeholder-text">Not yet evaluated</div>
      <div style="margin-top:12px;text-align:right;">
        <button class="btn-primary" id="btn-llm-review">Request LLM Review</button>
      </div>`;
  }

  function buildDetailHTML(detail, idx, total, prevId, nextId) {
    const ctx = detail.context_data;
    const review = detail.review;
    const rating = review ? review.expert_rating : null;
    const critique = review ? review.expert_critique || "" : "";
    const outdated = review && review.snapshot_outdated;
    const counterText = idx === -1 ? `(not in filtered list)` : `${idx + 1} of ${total}`;

    let questionsHTML = "";
    for (let i = 0; i < ctx.questions.length; i++) {
      const q = ctx.questions[i];
      let optionsHTML = "";
      for (const [letter, text] of Object.entries(q.options)) {
        const isCorrect = letter === q.correct_answer;
        optionsHTML += `
          <div class="${isCorrect ? "option-correct" : ""}">
            <span class="option-label">${esc(letter)}.</span>
            <span class="option-text">${esc(text)}${isCorrect ? " \u2713" : ""}</span>
          </div>`;
      }

      questionsHTML += `
        <div class="card">
          <div class="card-header">Question (${i + 1})</div>
          <div class="card-body">
            <div class="options-grid">${optionsHTML}</div>
            <div class="question-grammar-section">
              <div class="meta-label">Grammar Topic</div>
              <div class="meta-value">${esc(q.grammar_topic)}</div>
            </div>
          </div>
        </div>`;

      if (q.explanation) {
        questionsHTML += `
          <div class="card">
            <div class="card-header">Explanation</div>
            <div class="card-body">
              <div class="explanation-why">
                <div class="meta-label">Why Correct</div>
                <div class="meta-value">${esc(q.explanation.why_correct || "")}</div>
              </div>
              <div>
                <div class="meta-label">Grammar Rule</div>
                <div class="meta-value">${esc(q.explanation.grammar_rule || "")}</div>
              </div>
            </div>
          </div>`;
      }
    }

    return `
      ${outdated ? '<div class="banner-outdated">Snapshot outdated — the context has been regenerated since this review was created.</div>' : ""}

      <div class="nav-bar">
        <button class="btn-nav" id="btn-prev" ${!prevId ? "disabled" : ""}>&#8592; Previous</button>
        <span class="nav-counter">${counterText}</span>
        <button class="btn-nav" id="btn-next" ${!nextId ? "disabled" : ""}>Next &#8594;</button>
      </div>

      <div class="detail-layout">
        <div class="sidebar" id="sidebar">
          <div class="sidebar-header">Contexts</div>
          <div class="sidebar-list" id="sidebar-list"></div>
        </div>

        <div class="detail-content">
          <div class="card">
            <div class="card-header">Context Passage &mdash; ${esc(ctx.type.replace("_", " "))} &middot; ${esc(ctx.grammar_topics)}</div>
            <div class="card-body">
              <div class="passage">${esc(ctx.passage)}</div>
            </div>
          </div>
          ${questionsHTML}
        </div>

        <div class="review-panel">
          <div class="card">
            <div class="card-header">Expert Review</div>
            <div class="card-body">
              <div class="meta-label">Rating</div>
              <div class="rating-buttons">
                <button class="rating-btn ${rating === "Good" ? "selected-good" : ""}" data-rating="Good">Good</button>
                <button class="rating-btn ${rating === "Bad" ? "selected-bad" : ""}" data-rating="Bad">Bad</button>
              </div>
              <div class="meta-label">Critique</div>
              <textarea class="critique-textarea" id="critique" placeholder="Optional — add notes about this context...">${esc(critique)}</textarea>
              <div style="text-align:right;">
                <button class="btn-primary" id="btn-submit">${review ? "Update Review" : "Submit Review"}</button>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-header">LLM Evaluator (automated)</div>
            <div class="card-body" id="llm-evaluator-body">${buildLlmEvaluatorHTML(review)}</div>
          </div>

          <a class="back-link" id="btn-back">&#8592; Back to list</a>
        </div>
      </div>
    `;
  }

  function bindLlmReviewBtn(contextId) {
    const btn = document.getElementById("btn-llm-review");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Évaluation en cours…";
      try {
        const result = await api(`/contexts/${contextId}/llm-review`, {
          method: "POST",
        });
        const body = document.getElementById("llm-evaluator-body");
        if (!body) return; // user navigated away while request was in flight
        body.innerHTML = buildLlmEvaluatorHTML({
          llm_evaluator_rating: result.rating,
          llm_evaluator_critique: result.critique,
        });
        // A new #btn-llm-review was created by innerHTML — re-bind its handler.
        bindLlmReviewBtn(contextId);
        showToast("LLM review complete");
      } catch (err) {
        showToast(`Error: ${err.message}`, "error");
        btn.disabled = false;
        btn.textContent = originalText;
      }
    });
  }

  function bindDetailEvents(detail, prevId, nextId) {
    const contextId = detail.context_id;
    let selectedRating = detail.review ? detail.review.expert_rating : null;

    // Rating buttons
    document.querySelectorAll(".rating-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedRating = btn.dataset.rating;
        document.querySelectorAll(".rating-btn").forEach((b) => {
          b.className = "rating-btn";
        });
        btn.classList.add(selectedRating === "Good" ? "selected-good" : "selected-bad");
      });
    });

    // Submit
    document.getElementById("btn-submit").addEventListener("click", async () => {
      if (!selectedRating) {
        showToast("Please select Good or Bad", "error");
        return;
      }
      const critique = document.getElementById("critique").value;
      const submitBtn = document.getElementById("btn-submit");
      submitBtn.disabled = true;

      // Optimistic sidebar update
      const sidebarItem = document.querySelector(`.sidebar-item[data-id="${contextId}"] .dot`);
      const wasDotClass = sidebarItem ? sidebarItem.className : null;
      if (sidebarItem) {
        sidebarItem.className = "dot dot-reviewed";
      }

      try {
        await api(`/contexts/${contextId}/review`, {
          method: "PUT",
          body: JSON.stringify({
            expert_rating: selectedRating,
            expert_critique: critique,
          }),
        });
        // Update cached list
        const cached = state.contextList.find((c) => c.context_id === contextId);
        if (cached) cached.expert_rating = selectedRating;

        showToast("Review saved");
        submitBtn.textContent = "Update Review";
      } catch (err) {
        // Revert sidebar dot on failure
        if (sidebarItem && wasDotClass) sidebarItem.className = wasDotClass;
        showToast(`Error: ${err.message}`, "error");
      } finally {
        submitBtn.disabled = false;
      }
    });

    // Navigation
    if (prevId) {
      document.getElementById("btn-prev").addEventListener("click", () => {
        location.hash = `#/review/${prevId}`;
      });
    }
    if (nextId) {
      document.getElementById("btn-next").addEventListener("click", () => {
        location.hash = `#/review/${nextId}`;
      });
    }
    document.getElementById("btn-back").addEventListener("click", (e) => {
      e.preventDefault();
      location.hash = "#/";
    });
    bindLlmReviewBtn(contextId);
  }

  function renderSidebar(activeId) {
    const list = document.getElementById("sidebar-list");
    if (!list) return;
    list.innerHTML = "";

    const counters = { fill_in_blank: 0, error_identification: 0 };

    for (const item of state.contextList) {
      const type = item.type || "fill_in_blank";
      counters[type] = (counters[type] || 0) + 1;
      const label = type === "error_identification"
        ? `Error-ID #${counters[type]}`
        : `Fill-in #${counters[type]}`;

      const isActive = item.context_id === activeId;
      const hasReview = !!item.expert_rating;
      const div = document.createElement("div");
      div.className = `sidebar-item${isActive ? " active" : ""}`;
      div.dataset.id = item.context_id;
      div.innerHTML = `
        <span class="dot ${hasReview ? "dot-reviewed" : "dot-empty"}"></span>
        <span>${label}</span>
      `;
      div.addEventListener("click", () => {
        location.hash = `#/review/${item.context_id}`;
      });
      list.appendChild(div);
    }
  }

  // ── Init ───────────────────────────────────────────────────────────────
  window.addEventListener("hashchange", route);
  route();
})();