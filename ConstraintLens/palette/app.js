// ConstraintLens palette UI — vanilla JS, no framework, no build step.
// Mirrors the message contract in SPEC.md section 7.

(function () {
    "use strict";

    // --- Action names — must match lib/messaging.py exactly. -------------

    const JS_TO_PY = {
        paletteReady: "paletteReady",
        requestRefresh: "requestRefresh",
        selectEntities: "selectEntities",
        selectConstraint: "selectConstraint",
        deleteConstraint: "deleteConstraint",
        showUnderconstrained: "showUnderconstrained",
    };

    const PY_TO_JS = {
        data: "data",
        noActiveSketch: "noActiveSketch",
        error: "error",
        actionResult: "actionResult",
    };

    // --- Glyphs (text fallback; SVG files can replace these later). ------

    const TYPE_GLYPHS = {
        HorizontalConstraint: "—",
        VerticalConstraint: "|",
        HorizontalPointsConstraint: "↔",
        VerticalPointsConstraint: "↕",
        ParallelConstraint: "∥",
        PerpendicularConstraint: "⊥",
        CollinearConstraint: "⋯",
        CoincidentConstraint: "●",
        CoincidentToSurfaceConstraint: "▣",
        TangentConstraint: "⌒",
        EqualConstraint: "=",
        ConcentricConstraint: "⊙",
        MidPointConstraint: "◐",
        SymmetryConstraint: "↔",
        OffsetConstraint: "⫽",
        PolygonConstraint: "⬡",
        CircularPatternConstraint: "○",
        RectangularPatternConstraint: "▦",
        LineOnPlanarSurfaceConstraint: "▤",
        LineParallelToPlanarSurfaceConstraint: "▥",
        PerpendicularToSurfaceConstraint: "▧",
        ImplicitCoincidentJoin: "●",
    };

    // --- State -----------------------------------------------------------

    const state = {
        snapshot: null,
        loaded: false,
        filter: "",
    };

    const els = {
        root: document.getElementById("root"),
        status: document.getElementById("status"),
        refresh: document.getElementById("refresh"),
        highlightUnder: document.getElementById("highlight-under"),
        filter: document.getElementById("filter"),
    };

    // --- Outgoing messages -----------------------------------------------

    function send(action, payload) {
        if (typeof adsk === "undefined" || !adsk.fusionSendData) {
            console.warn("adsk.fusionSendData not present yet:", action);
            return;
        }
        adsk.fusionSendData(action, JSON.stringify(payload || {}));
    }

    els.refresh.addEventListener("click", () => send(JS_TO_PY.requestRefresh, {}));
    els.highlightUnder.addEventListener("click", () => send(JS_TO_PY.showUnderconstrained, {}));
    els.filter.addEventListener("input", () => {
        state.filter = els.filter.value.trim().toLowerCase();
        renderSnapshot();
    });

    // --- Incoming messages ----------------------------------------------

    // Fusion calls window.fusionJavaScriptHandler.handle(action, data).
    window.fusionJavaScriptHandler = {
        handle(action, data) {
            let payload = {};
            try {
                payload = data ? JSON.parse(data) : {};
            } catch (e) {
                console.warn("malformed payload for", action, e);
            }
            switch (action) {
                case PY_TO_JS.data: onData(payload); break;
                case PY_TO_JS.noActiveSketch: onNoActiveSketch(payload); break;
                case PY_TO_JS.error: onError(payload); break;
                case PY_TO_JS.actionResult: onActionResult(payload); break;
                default: console.log("unknown action", action, payload);
            }
            return "OK";
        },
    };

    function onData(payload) {
        state.snapshot = payload;
        els.highlightUnder.disabled = false;
        renderSnapshot();
    }

    function onNoActiveSketch(payload) {
        state.snapshot = null;
        els.highlightUnder.disabled = true;
        setStatus(payload.reason || "No active sketch.", "warn");
        els.root.innerHTML = `<div class="empty">${escape(payload.reason || "Open a sketch for edit to see its constraints.")}</div>`;
    }

    function onError(payload) {
        setStatus(`Error: ${payload.message || "unknown"}`, "error");
    }

    function onActionResult(payload) {
        const cls = payload.ok ? "ok" : "error";
        showToast(payload.message || (payload.ok ? "OK" : "Failed"), cls);
    }

    // --- Filtering -------------------------------------------------------

    function matchesFilter(row, q) {
        if (!q) return true;
        return (row.label || "").toLowerCase().includes(q)
            || (row.kind || "").toLowerCase().includes(q);
    }

    // --- Rendering -------------------------------------------------------

    function renderSnapshot() {
        const snap = state.snapshot;
        if (!snap) {
            els.root.innerHTML = `<div class="empty">No data.</div>`;
            return;
        }

        const sk = snap.sketch || {};
        const fully = sk.isFullyConstrained;
        const statusText = sk.name
            ? `${escape(sk.name)}${sk.componentName ? " · " + escape(sk.componentName) : ""}`
            + ` — ${fully ? "fully constrained" : "under-constrained"}`
            : "No active sketch.";
        setStatus(statusText, fully ? "ok" : "warn");

        const q = state.filter;
        const allC = snap.constraints || [];
        const allD = snap.dimensions || [];
        const allJ = snap.implicitJoins || [];
        const c = allC.filter(r => matchesFilter(r, q));
        const d = allD.filter(r => matchesFilter(r, q));
        const j = allJ.filter(r => matchesFilter(r, q));

        const parts = [];

        if (c.length === 0 && d.length === 0 && j.length === 0) {
            const totalAll = allC.length + allD.length + allJ.length;
            if (q && totalAll > 0) {
                parts.push(`<div class="empty">No matches for &ldquo;${escape(q)}&rdquo;.</div>`);
            } else {
                parts.push(`<div class="empty">This sketch has no constraints or dimensions yet.</div>`);
            }
        }

        if (c.length) {
            const label = q
                ? `Geometric constraints (${c.length} of ${allC.length})`
                : `Geometric constraints (${allC.length})`;
            parts.push(`<div class="section-header">${label}</div>`);
            for (const row of c) parts.push(rowHTML(row));
        }
        if (d.length) {
            const label = q
                ? `Dimensions (${d.length} of ${allD.length})`
                : `Dimensions (${allD.length})`;
            parts.push(`<div class="section-header">${label}</div>`);
            for (const row of d) parts.push(rowHTML(row));
        }
        if (j.length) {
            const label = q
                ? `Endpoint joins (${j.length} of ${allJ.length})`
                : `Endpoint joins (${allJ.length})`;
            parts.push(`<div class="section-header">${label}</div>`);
            for (const row of j) parts.push(rowHTML(row));
        }

        els.root.innerHTML = parts.join("");
    }

    function rowHTML(row) {
        const glyph = TYPE_GLYPHS[row.kind] || "·";
        const hasErrors = row.errors && row.errors.length > 0;
        const chips = (row.entities || []).map(chipHTML).join("");
        const pseudoClass = row.isPseudo ? " pseudo" : "";
        const errorClass = hasErrors ? " has-errors" : "";
        const badges = [];
        if (row.isPseudo) badges.push(`<span class="badge implicit">implicit</span>`);
        if (hasErrors) badges.push(`<span class="badge error">accessor</span>`);
        const errorsHTML = hasErrors
            ? `<div class="errors">${row.errors.map(escape).join("; ")}</div>`
            : "";

        // Entity tokens for token-based selection (bypasses accessor re-scan).
        const entityTokensJson = JSON.stringify(
            (row.entities || []).map(e => e.token || "").filter(t => t)
        );

        const selectConstraintBtn = row.isPseudo
            ? ""
            : `<button class="btn" data-action="selectConstraint" data-token="${escape(row.token || "")}" title="Select the constraint object itself">⌖</button>`;

        // Pseudo rows (implicit joins) cannot be deleted — show a lock indicator
        // with an explanatory tooltip instead of a disabled × button.
        const deleteBtn = row.isPseudo
            ? `<span class="row-lock" title="Endpoint joins are shared sketch points and cannot be individually deleted">⊘</span>`
            : `<button class="btn danger" data-action="deleteConstraint"
                       data-token="${escape(row.token || "")}"${!row.isDeletable ? ' disabled title="This constraint cannot be deleted"' : ""}>×</button>`;

        return `
            <div class="row${pseudoClass}${errorClass}"
                 data-row-key="${escape(row.rowKey || "")}"
                 data-entity-tokens="${escape(entityTokensJson)}"
                 data-action="selectEntities"
                 role="button">
                <div class="row-glyph">${escape(glyph)}</div>
                <div class="row-body">
                    <div class="row-label">${escape(row.label || "")}</div>
                    <div class="row-meta">
                        <span class="kind">${escape(row.kind || "")}</span>
                        ${badges.join("")}
                    </div>
                    ${chips ? `<div class="chips">${chips}</div>` : ""}
                    ${errorsHTML}
                </div>
                <div class="row-actions">
                    ${selectConstraintBtn}
                    ${deleteBtn}
                </div>
            </div>
        `;
    }

    function chipHTML(chip) {
        return `<span class="chip">${escape(chip.label || chip.kind || "?")}</span>`;
    }

    // --- Delegated click handling ---------------------------------------

    els.root.addEventListener("click", (evt) => {
        const actionEl = evt.target.closest("[data-action]");
        if (!actionEl) return;
        const action = actionEl.getAttribute("data-action");

        if (action === "deleteConstraint") {
            evt.stopPropagation();
            const token = actionEl.getAttribute("data-token") || "";
            if (!token) return;
            send(JS_TO_PY.deleteConstraint, { token });
            return;
        }

        if (action === "selectConstraint") {
            evt.stopPropagation();
            const token = actionEl.getAttribute("data-token") || "";
            if (!token) return;
            send(JS_TO_PY.selectConstraint, { token });
            return;
        }

        if (action === "selectEntities") {
            const row = actionEl.closest(".row");
            const rowKey = row ? row.getAttribute("data-row-key") || "" : "";
            if (!rowKey) return;
            let entityTokens = [];
            try {
                const attr = row ? row.getAttribute("data-entity-tokens") : null;
                entityTokens = attr ? JSON.parse(attr) : [];
            } catch (e) { entityTokens = []; }
            send(JS_TO_PY.selectEntities, { rowKey, entityTokens });
            return;
        }
    });

    // --- Helpers ---------------------------------------------------------

    function setStatus(text, cls) {
        els.status.textContent = text;
        els.status.className = "status" + (cls ? " " + cls : "");
    }

    let toastTimer = null;
    function showToast(text, cls) {
        let toast = document.querySelector(".toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "toast";
            document.body.appendChild(toast);
        }
        toast.textContent = text;
        toast.className = "toast show " + (cls || "");
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toast.className = "toast " + (cls || "");
        }, 2400);
    }

    function escape(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    // --- Hello ----------------------------------------------------------
    // Fusion injects adsk.fusionSendData asynchronously after DOMContentLoaded.
    // Poll until the bridge is ready before firing paletteReady, so the initial
    // scan happens automatically without requiring a manual Refresh click.

    function _sendWhenReady(action, payload, maxMs) {
        const deadline = Date.now() + (maxMs || 5000);
        function attempt() {
            if (typeof adsk !== "undefined" && adsk.fusionSendData) {
                adsk.fusionSendData(action, JSON.stringify(payload || {}));
                return;
            }
            if (Date.now() < deadline) {
                setTimeout(attempt, 100);
            }
        }
        attempt();
    }

    document.addEventListener("DOMContentLoaded", () => {
        state.loaded = true;
        _sendWhenReady(JS_TO_PY.paletteReady, {});
    });
})();
