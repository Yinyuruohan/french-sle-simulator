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

  // ── Toast ──────────────────────────────────────────────────────────────
  function showToast(msg, type = "success") {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = `toast ${type}`;
    setTimeout(() => el.classList.add("hidden"), 2500);
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

      // Render rows
      const tbody = document.getElementById("ctx-tbody");
      for (const item of data.items) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><span class="ctx-id">${item.context_id.slice(0, 8)}</span></td>
          <td><span class="badge badge-${item.status}">${item.status.replace("_", " ")}</span></td>
          <td>${item.user_flags > 0 ? `<span class="flags-red">${item.user_flags}</span>` : "0"}</td>
          <td>${item.expert_rating
            ? `<span class="badge badge-${item.expert_rating.toLowerCase()}">${item.expert_rating}</span>`
            : `<span class="badge-none">not reviewed</span>`}</td>
        `;
        tr.addEventListener("click", () => {
          location.hash = `#/review/${item.context_id}`;
        });
        tbody.appendChild(tr);
      }
    } catch (err) {
      main.innerHTML = `<p style="color:#dc2626">Error loading contexts: ${err.message}</p>`;
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
        main.innerHTML = `<p style="color:#dc2626">Error: ${err.message}</p>`;
        return;
      }
    }

    try {
      const detail = await api(`/contexts/${contextId}`);
      const idx = state.contextList.findIndex((c) => c.context_id === contextId);
      const total = state.contextList.length;
      const prevId = idx > 0 ? state.contextList[idx - 1].context_id : null;
      const nextId = idx < total - 1 ? state.contextList[idx + 1].context_id : null;

      main.innerHTML = buildDetailHTML(detail, idx, total, prevId, nextId);
      bindDetailEvents(detail, prevId, nextId);
      renderSidebar(contextId);
    } catch (err) {
      main.innerHTML = `<p style="color:#dc2626">Error: ${err.message}</p>`;
    }
  }

  function buildDetailHTML(detail, idx, total, prevId, nextId) {
    const ctx = detail.context_data;
    const review = detail.review;
    const rating = review ? review.expert_rating : null;
    const critique = review ? review.expert_critique || "" : "";
    const outdated = review && review.snapshot_outdated;

    let questionsHTML = "";
    for (let i = 0; i < ctx.questions.length; i++) {
      const q = ctx.questions[i];
      let optionsHTML = "";
      for (const [letter, text] of Object.entries(q.options)) {
        const isCorrect = letter === q.correct_answer;
        optionsHTML += `
          <div class="${isCorrect ? "option-correct" : ""}">
            <span class="option-label">${letter}.</span>
            <span class="option-text">${text}${isCorrect ? " \u2713" : ""}</span>
          </div>`;
      }

      questionsHTML += `
        <div class="card">
          <div class="card-header">Question (${i + 1})</div>
          <div class="card-body">
            <div class="options-grid">${optionsHTML}</div>
            <div style="border-top:1px solid #e2e8f0;padding-top:12px;">
              <div class="meta-label">Grammar Topic</div>
              <div class="meta-value">${q.grammar_topic}</div>
            </div>
          </div>
        </div>`;

      if (q.explanation) {
        questionsHTML += `
          <div class="card">
            <div class="card-header">Explanation</div>
            <div class="card-body">
              <div style="margin-bottom:10px;">
                <div class="meta-label">Why Correct</div>
                <div class="meta-value">${q.explanation.why_correct || ""}</div>
              </div>
              <div>
                <div class="meta-label">Grammar Rule</div>
                <div class="meta-value">${q.explanation.grammar_rule || ""}</div>
              </div>
            </div>
          </div>`;
      }
    }

    const llmSection = review && review.llm_evaluator_rating
      ? `<div><div class="meta-label">Rating</div><div class="meta-value">${review.llm_evaluator_rating}</div></div>
         <div><div class="meta-label">Critique</div><div class="meta-value">${review.llm_evaluator_critique}</div></div>`
      : `<div class="placeholder-text">Not yet evaluated</div>`;

    return `
      ${outdated ? '<div class="banner-outdated">Snapshot outdated — the context has been regenerated since this review was created.</div>' : ""}

      <div class="nav-bar">
        <button class="btn-nav" id="btn-prev" ${!prevId ? "disabled" : ""}>&#8592; Previous</button>
        <span class="nav-counter">${idx + 1} of ${total}</span>
        <button class="btn-nav" id="btn-next" ${!nextId ? "disabled" : ""}>Next &#8594;</button>
      </div>

      <div class="detail-layout">
        <div class="sidebar" id="sidebar">
          <div class="sidebar-header">Contexts</div>
          <div class="sidebar-list" id="sidebar-list"></div>
        </div>

        <div class="detail-content">
          <div class="card">
            <div class="card-header">Context Passage &mdash; ${ctx.type.replace("_", " ")} &middot; ${ctx.grammar_topics}</div>
            <div class="card-body">
              <div class="passage">${ctx.passage}</div>
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
              <textarea class="critique-textarea" id="critique" placeholder="Optional — add notes about this context...">${critique}</textarea>
              <div style="text-align:right;">
                <button class="btn-primary" id="btn-submit">${review ? "Update Review" : "Submit Review"}</button>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-header">LLM Evaluator (automated)</div>
            <div class="card-body">${llmSection}</div>
          </div>

          <a class="back-link" id="btn-back">&#8592; Back to list</a>
        </div>
      </div>
    `;
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