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
        bulkDelete: "bulkDelete",
        editDimension: "editDimension",
        openEditDialog: "openEditDialog",
        editParameter: "editParameter",
        setAutoZoom: "setAutoZoom",
        setAutoHide: "setAutoHide",
        setPaletteHeight: "setPaletteHeight",
    };

    const PY_TO_JS = {
        data: "data",
        noActiveSketch: "noActiveSketch",
        error: "error",
        actionResult: "actionResult",
        selectionResult: "selectionResult",
        selectionInfo: "selectionInfo",
        dockInfo: "dockInfo",
    };

    // --- SVG icons, one per constraint type. --------------------------------
    // Inserted as raw HTML (not escaped); safe because these are hardcoded constants.

    const _S = `<svg width="24" height="24" viewBox="0 0 16 16" fill="none">`;
    const _E = `</svg>`;
    const _L = (x1,y1,x2,y2,w,extra="") =>
        `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="currentColor" stroke-width="${w}" stroke-linecap="round"${extra}/>`;
    const _C = (cx,cy,r,fill) => fill
        ? `<circle cx="${cx}" cy="${cy}" r="${r}" fill="currentColor"/>`
        : `<circle cx="${cx}" cy="${cy}" r="${r}" stroke="currentColor" stroke-width="1.5"/>`;

    const TYPE_ICONS = {
        HorizontalConstraint:
            _S + _L(2,8,14,8,1.5) + _L(2,5,2,11,1.5) + _L(14,5,14,11,1.5) + _E,

        VerticalConstraint:
            _S + _L(8,2,8,14,1.5) + _L(5,2,11,2,1.5) + _L(5,14,11,14,1.5) + _E,

        HorizontalPointsConstraint:
            _S + _C(3,8,1.5,true) + _C(13,8,1.5,true)
            + _L(5,8,11,8,1,` stroke-dasharray="2 1.5"`) + _E,

        VerticalPointsConstraint:
            _S + _C(8,3,1.5,true) + _C(8,13,1.5,true)
            + _L(8,5,8,11,1,` stroke-dasharray="2 1.5"`) + _E,

        ParallelConstraint:
            _S + _L(2,13,8,3,1.5) + _L(8,13,14,3,1.5) + _E,

        PerpendicularConstraint:
            _S + _L(4,2,4,13,1.5) + _L(4,13,14,13,1.5)
            + `<path d="M4 9 L8 9 L8 13" stroke="currentColor" stroke-width="1" fill="none"/>` + _E,

        CollinearConstraint:
            _S + _L(2,13,14,3,1.5) + _C(5,11,1.5,true) + _C(8,8,1.5,true) + _C(11,5,1.5,true) + _E,

        CoincidentConstraint:
            _S + _L(2,13,8,8,1.5) + _L(14,3,8,8,1.5) + _C(8,8,2.5,true) + _E,

        CoincidentToSurfaceConstraint:
            _S + _L(2,13,14,13,1.5) + _C(8,8,2.5,true) + _L(8,10.5,8,13,1.5) + _E,

        TangentConstraint:
            _S + _L(1,5,15,5,1.5)
            + `<circle cx="8" cy="10" r="4.5" stroke="currentColor" stroke-width="1.5"/>` + _E,

        EqualConstraint:
            _S + _L(3,6,13,6,1.5) + _L(3,10,13,10,1.5) + _E,

        ConcentricConstraint:
            _S + _C(8,8,6.5,false) + _C(8,8,2.5,false) + _E,

        MidPointConstraint:
            _S + _L(2,12,14,12,1.5) + _L(8,4,8,12,1.5)
            + _C(8,12,1.5,true)
            + `<circle cx="8" cy="4" r="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/>` + _E,

        SymmetryConstraint:
            _S + _L(8,2,8,14,1,` stroke-dasharray="2 2"`)
            + `<polyline points="4,6 2,8 4,10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`
            + `<polyline points="12,6 14,8 12,10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>` + _E,

        OffsetConstraint:
            _S + `<path d="M2 5 Q8 3 14 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>`
            + `<path d="M2 11 Q8 9 14 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>`
            + _L(8,5,8,9,1,` stroke-dasharray="1.5 1.5"`) + _E,

        PolygonConstraint:
            _S + `<polygon points="8,2 13.2,5 13.2,11 8,14 2.8,11 2.8,5" stroke="currentColor" stroke-width="1.5"/>` + _E,

        CircularPatternConstraint:
            _S + `<circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1" stroke-dasharray="2 2"/>`
            + _C(8,2.5,1.5,true) + _C(12.3,10.5,1.5,true) + _C(3.7,10.5,1.5,true) + _E,

        RectangularPatternConstraint:
            _S + `<rect x="2" y="2" width="5" height="5" stroke="currentColor" stroke-width="1.5"/>`
            + `<rect x="9" y="2" width="5" height="5" stroke="currentColor" stroke-width="1.5"/>`
            + `<rect x="2" y="9" width="5" height="5" stroke="currentColor" stroke-width="1.5"/>`
            + `<rect x="9" y="9" width="5" height="5" stroke="currentColor" stroke-width="1.5"/>` + _E,

        LineOnPlanarSurfaceConstraint:
            _S + _L(2,12,14,12,1.5)
            + _L(2,14,5,12,1,"") + _L(6,14,9,12,1,"") + _L(10,14,13,12,1,"")
            + _L(8,3,8,12,1.5) + _E,

        LineParallelToPlanarSurfaceConstraint:
            _S + _L(2,13,14,13,1.5) + _L(2,6,14,6,1.5)
            + _L(8,6,8,13,1,` stroke-dasharray="2 2"`) + _E,

        PerpendicularToSurfaceConstraint:
            _S + _L(2,13,14,13,1.5) + _L(8,3,8,13,1.5)
            + `<path d="M8 9 L11 9 L11 13" stroke="currentColor" stroke-width="1" fill="none"/>` + _E,

        ImplicitCoincidentJoin:
            _S + _L(2,13,8,8,1.5) + _L(14,3,8,8,1.5) + _C(8,8,2.5,true) + _E,

        // Generic fallback for all dimension rows (glyph stem "dimension").
        dimension:
            _S + _L(3,6,3,14,1.5) + _L(13,6,13,14,1.5) + _L(3,10,13,10,1.5)
            + `<path d="M6 8 L3 10 L6 12" stroke="currentColor" stroke-width="1" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`
            + `<path d="M10 8 L13 10 L10 12" stroke="currentColor" stroke-width="1" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`
            + _E,
    };

    // --- State -----------------------------------------------------------

    const state = {
        snapshot: null,
        loaded: false,
        filter: "",
        selected: new Set(),
        highlights: new Set(),   // rowKeys highlighted by Find (#7)
        collapsed: new Set(),    // section ids collapsed by user (#14)
    };

    const els = {
        root: document.getElementById("root"),
        status: document.getElementById("status"),
        refresh: document.getElementById("refresh"),
        highlightUnder: document.getElementById("highlight-under"),
        bulkDelete: document.getElementById("bulk-delete"),
        clearSelection: document.getElementById("clear-selection"),
        filter: document.getElementById("filter"),
        entityReadout: document.getElementById("entity-readout"),
        selectedSection: document.getElementById("selected-section"),
        selectedLabel: document.getElementById("selected-label"),
        selectedLabelText: document.getElementById("selected-label-text"),
        autozoomToggle: document.getElementById("autozoom-toggle"),
        autohideToggle: document.getElementById("autohide-toggle"),
        filterClear: document.getElementById("filter-clear"),
        themeToggle: document.getElementById("theme-toggle"),
        selectionFooter: document.getElementById("selection-footer"),
        footerSection: document.getElementById("footer-section"),
        heightCycle: document.getElementById("height-cycle"),
        resizeGrip: document.getElementById("resize-grip"),
        resizeGripReadout: document.getElementById("resize-grip-readout"),
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
    els.filterClear.addEventListener("click", () => {
        state.filter = "";
        els.filter.value = "";
        renderSnapshot();
    });
    els.bulkDelete.addEventListener("click", () => {
        const tokens = [...state.selected];
        if (tokens.length === 0) return;
        const n = tokens.length;
        if (!confirm(`Delete ${n} constraint${n !== 1 ? "s" : ""}?\n(Ctrl+Z in Fusion can undo sketch operations.)`)) return;
        send(JS_TO_PY.bulkDelete, { tokens });
        state.selected.clear();
        updateBulkDeleteButton();
    });
    els.clearSelection.addEventListener("click", () => {
        state.selected.clear();
        updateBulkDeleteButton();
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
                case PY_TO_JS.selectionResult: onSelectionResult(payload); break;
                case PY_TO_JS.selectionInfo: onSelectionInfo(payload); break;
                case PY_TO_JS.dockInfo: onDockInfo(payload); break;
                default: console.log("unknown action", action, payload);
            }
            return "OK";
        },
    };

    function updateBulkDeleteButton() {
        const n = state.selected.size;
        const show = n > 0;
        els.bulkDelete.style.display = show ? "" : "none";
        els.clearSelection.style.display = show ? "" : "none";
        if (show) els.bulkDelete.textContent = `Delete ${n}`;
    }

    function onData(payload) {
        state.snapshot = payload;
        state.selected.clear();
        updateBulkDeleteButton();
        els.highlightUnder.disabled = false;
        renderSnapshot();
    }

    function onNoActiveSketch(payload) {
        state.snapshot = null;
        state.selected.clear();
        state.highlights.clear();
        updateBulkDeleteButton();
        els.highlightUnder.disabled = true;
        showEntityReadout("");
        setStatus(payload.reason || "No active sketch.", "warn");
        els.root.innerHTML = `<div class="empty">${escape(payload.reason || "Open a sketch for edit to see its constraints.")}</div>`;
    }

    function onError(payload) {
        setStatus(`Error: ${payload.message || "unknown"}`, "error");
    }

    function onSelectionInfo(payload) {
        const items = (payload && payload.items) || [];
        if (items.length === 0) {
            els.footerSection.className = "hidden";
            els.selectionFooter.innerHTML = "";
            return;
        }
        const html = items.map((item) => {
            const props = (item.props || []).map((p) =>
                `<span class="sel-prop"><span class="sel-key">${escape(p.key)}</span>` +
                `<span class="sel-val">${escape(p.value)}</span></span>`
            ).join("");
            const labelHTML = `<span class="sel-label">${escape(item.label || "")}</span>`;
            const sep = props ? `<span class="sel-sep">·</span>` : "";
            return `<div class="sel-item">${labelHTML}${sep}${props}</div>`;
        }).join("");
        els.footerSection.className = "";
        els.selectionFooter.innerHTML = html;
    }

    function onActionResult(payload) {
        const cls = payload.ok ? "ok" : "error";
        showToast(payload.message || (payload.ok ? "OK" : "Failed"), cls);
        if (payload.readout) showEntityReadout(payload.readout);
    }

    function onSelectionResult(payload) {
        const tokens = payload.tokens || [];
        const prefix = payload.prefix || "Selected:";
        els.selectedLabelText.textContent = prefix;
        state.highlights.clear();

        if (!state.snapshot || tokens.length === 0) {
            showEntityReadout("");
            renderSnapshot();
            return;
        }

        // Build entity token → label and token → [rowKey] indices from snapshot.
        const tokenToLabel = new Map();
        const tokenToRows = new Map();
        const _addToken = (tok, label, rowKey) => {
            if (!tok) return;
            if (!tokenToLabel.has(tok)) tokenToLabel.set(tok, label);
            if (!tokenToRows.has(tok)) tokenToRows.set(tok, []);
            tokenToRows.get(tok).push(rowKey);
        };
        for (const section of [
            state.snapshot.constraints,
            state.snapshot.dimensions,
            state.snapshot.patterns,
            state.snapshot.implicitJoins,
        ]) {
            for (const row of (section || [])) {
                // Index the row's own token (dimension/constraint entity itself).
                _addToken(row.token, row.label || row.kind || "?", row.rowKey);
                // Index each entity chip token (referenced geometry).
                for (const chip of (row.entities || [])) {
                    _addToken(chip.token, chip.label || chip.kind || "?", row.rowKey);
                }
            }
        }

        // #12 — entity name readout as clickable chips.
        const matched = tokens.filter(t => tokenToLabel.has(t)).map(t => ({ label: tokenToLabel.get(t), token: t }));
        if (matched.length) {
            showReadoutChips(matched);
        } else {
            showEntityReadout("Selected entity not in any row.");
        }

        // #22 — auto-filter to the selected entity when exactly one is matched.
        if (matched.length === 1) {
            state.filter = matched[0].label.toLowerCase();
            els.filter.value = matched[0].label;
        }

        // #7 — collect matching row keys.
        for (const tok of tokens) {
            for (const rk of (tokenToRows.get(tok) || [])) {
                state.highlights.add(rk);
            }
        }

        renderSnapshot();

        // Scroll to first highlighted row.
        const first = els.root.querySelector(".row.highlighted");
        if (first) first.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function showEntityReadout(text) {
        if (!text) {
            els.selectedSection.className = "hidden";
            els.entityReadout.innerHTML = "";
            return;
        }
        els.entityReadout.textContent = text;
        els.selectedSection.className = "";
    }

    function showReadoutChips(items) {
        if (!items || items.length === 0) {
            els.selectedSection.className = "hidden";
            els.entityReadout.innerHTML = "";
            return;
        }
        const chipsHTML = items.map(({label, token}) =>
            `<span class="chip" data-label="${escape(label)}" data-token="${escape(token)}"
                   title="Click to filter and select">${escape(label)}</span>`
        ).join("");
        els.entityReadout.innerHTML = chipsHTML;
        els.selectedSection.className = "";
    }

    els.entityReadout.addEventListener("click", (evt) => {
        const chip = evt.target.closest(".chip");
        if (!chip) return;
        const label = chip.getAttribute("data-label") || "";
        const token = chip.getAttribute("data-token") || "";
        if (label) {
            state.filter = label.toLowerCase();
            els.filter.value = label;
            renderSnapshot();
        }
        if (token) send(JS_TO_PY.selectEntities, { entityTokens: [token] });
    });

    // --- Filtering -------------------------------------------------------

    function matchesFilter(row, q) {
        if (!q) return true;
        return (row.label || "").toLowerCase().includes(q)
            || (row.kind || "").toLowerCase().includes(q)
            || (row.entities || []).some(e => (e.label || "").toLowerCase().includes(q));
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
        const allP = snap.patterns || [];
        const allJ = snap.implicitJoins || [];
        const c = allC.filter(r => matchesFilter(r, q));
        const d = allD.filter(r => matchesFilter(r, q));
        const p = allP.filter(r => matchesFilter(r, q));
        const j = allJ.filter(r => matchesFilter(r, q));

        const parts = [];

        if (c.length === 0 && d.length === 0 && p.length === 0 && j.length === 0) {
            const totalAll = allC.length + allD.length + allP.length + allJ.length;
            if (q && totalAll > 0) {
                parts.push(`<div class="empty">No matches for &ldquo;${escape(q)}&rdquo;.</div>`);
            } else {
                parts.push(`<div class="empty">This sketch has no constraints or dimensions yet.</div>`);
            }
        }

        _renderSection(parts, "constraints", "Geometric constraints", c, allC.length, q);
        _renderSection(parts, "dimensions",  "Dimensions",            d, allD.length, q);
        _renderSection(parts, "patterns",    "Patterns and figures",  p, allP.length, q);
        _renderSection(parts, "joins",       "Endpoint joins",        j, allJ.length, q);

        els.root.innerHTML = parts.join("");
        _updateSectionCheckboxes();
    }

    const _SECTIONS_WITH_SELECT_ALL = new Set(["constraints", "dimensions", "patterns"]);

    function _renderSection(parts, id, title, rows, totalCount, q) {
        if (rows.length === 0) return;
        const collapsed = state.collapsed.has(id);
        const chevron = collapsed ? "▸" : "▾";
        const countLabel = q
            ? `${rows.length} of ${totalCount}`
            : `${totalCount}`;

        let checkboxHTML = "";
        if (_SECTIONS_WITH_SELECT_ALL.has(id)) {
            const deletable = rows.filter(r => !r.isPseudo && r.isDeletable && r.token).map(r => r.token);
            const allChecked = deletable.length > 0 && deletable.every(t => state.selected.has(t));
            checkboxHTML =
                `<input type="checkbox" class="section-check" data-section="${id}" ` +
                `data-tokens="${escape(JSON.stringify(deletable))}" ` +
                `${allChecked ? "checked" : ""} title="Select all in this section">`;
        }

        parts.push(
            `<div class="section-header" data-section="${id}" role="button" title="Click to collapse/expand">` +
            checkboxHTML +
            `<span class="section-title">${title} (${countLabel})</span>` +
            `<span class="section-chevron">${chevron}</span>` +
            `</div>`
        );
        if (!collapsed) {
            parts.push(`<div class="section-rows">`);
            for (const row of rows) parts.push(rowHTML(row));
            parts.push(`</div>`);
        }
    }

    function _updateSectionCheckboxes() {
        els.root.querySelectorAll(".section-check").forEach(cb => {
            let tokens = [];
            try { tokens = JSON.parse(cb.getAttribute("data-tokens") || "[]"); } catch (e) {}
            const n = tokens.filter(t => state.selected.has(t)).length;
            cb.checked = n > 0 && n === tokens.length;
            cb.indeterminate = n > 0 && n < tokens.length;
        });
    }

    // Native PNG load failure → swap in the SVG from TYPE_ICONS.
    // Error events on <img> don't bubble, so we use capture phase.
    document.addEventListener("error", (e) => {
        const img = e.target;
        if (!img.classList || !img.classList.contains("ci")) return;
        const k = img.getAttribute("data-k") || "";
        const svg = TYPE_ICONS[k];
        const tmpl = document.createElement("template");
        tmpl.innerHTML = svg || `<span style="line-height:16px">·</span>`;
        img.replaceWith(tmpl.content.firstElementChild || tmpl.content.firstChild);
    }, true);

    function rowHTML(row) {
        // Prefer kind-specific icon; fall back to glyph stem (e.g. "dimension").
        const _glyphStem = (row.glyph || "").replace(/\.svg$/, "");
        const iconKey = TYPE_ICONS[row.kind] ? row.kind
                      : (TYPE_ICONS[_glyphStem] ? _glyphStem : null);
        const iconSuffix = document.documentElement.getAttribute("data-theme") === "light" ? "-light" : "";
        const iconImg = iconKey
            ? `<img class="ci" src="icons/${iconKey}${iconSuffix}.png" data-k="${escape(iconKey)}" width="24" height="24" alt="">`
            : `<span style="line-height:24px">·</span>`;
        const glyphAttrs = (!row.isPseudo && row.token)
            ? ` data-action="selectConstraint" data-token="${escape(row.token || "")}" title="Select the constraint object itself"`
            : "";
        const hasErrors = row.errors && row.errors.length > 0;
        const chips = (row.entities || []).map(chipHTML).join("");
        const pseudoClass = row.isPseudo ? " pseudo" : "";
        const errorClass = hasErrors ? " has-errors" : "";
        const highlightClass = state.highlights.has(row.rowKey) ? " highlighted" : "";
        const isDimension = !!row.isDimension;
        const dblclickTitle = (_DBLCLICK_KINDS.has(row.kind) || isDimension)
            ? ` title="Double-click to open edit dialog"` : ``;
        const badges = [];
        if (row.isPseudo) badges.push(`<span class="badge implicit">implicit</span>`);
        if (hasErrors) badges.push(`<span class="badge error" title="An entity property returned no data in this Fusion build. Some chips may be missing — row is still functional.">accessor</span>`);
        const errorsHTML = hasErrors
            ? `<div class="errors">${row.errors.map(escape).join("; ")}</div>`
            : "";

        // Inline dimension expression (#6) — shown only for rows with a parameter.
        const exprHTML = row.parameterExpression
            ? `<div class="dim-expr-wrap">
                <span class="dim-expr">${escape(row.parameterExpression)}</span>
                <button class="btn-edit" data-action="editExpr" data-token="${escape(row.token || "")}"
                        title="Edit expression (Enter to commit, Esc to cancel)">✎</button>
               </div>`
            : "";

        // Pattern / polygon editable parameters (#15).
        const paramsHTML = (row.parameters || []).map(p => {
            const hasToken = p.token && p.token.length > 0;
            const pencil = hasToken
                ? `<button class="btn-edit" data-action="editParam" data-token="${escape(p.token)}"
                           title="Edit ${escape(p.label)} (Enter to commit, Esc to cancel)">✎</button>`
                : "";
            return `<div class="dim-expr-wrap">
                <span class="dim-expr-lbl">${escape(p.label)}:</span>
                <span class="dim-expr">${escape(p.expression)}</span>
                ${pencil}
            </div>`;
        }).join("");

        // Entity tokens for token-based selection (bypasses accessor re-scan).
        const entityTokensJson = JSON.stringify(
            (row.entities || []).map(e => e.token || "").filter(t => t)
        );

        const canCheck = !row.isPseudo && row.isDeletable && row.token;
        const checked = canCheck && state.selected.has(row.token) ? " checked" : "";
        const checkboxHTML = canCheck
            ? `<input type="checkbox" class="row-check" data-token="${escape(row.token)}"${checked}>`
            : `<span class="row-check-pad"></span>`;

        const selectConstraintBtn = "";

        // Density: show only the head of the label. dispatch.py builds every
        // label as "{type} — {entity} {sym} {entity}", and those entities are
        // already listed below as clickable chips, so the tail is the same
        // information twice. The uppercased row.kind that used to sit on its own
        // line between them was a third copy of the type name.
        //
        // Nothing is lost: the full label and the API type go in the tooltip,
        // and matchesFilter() reads row.label / row.kind from the data rather
        // than the DOM, so filtering by either still works.
        const fullLabel = row.label || "";
        const labelHead = fullLabel.split(" — ")[0];
        const labelTitle = [fullLabel, row.kind || ""].filter(Boolean).join("\n");

        // Pseudo rows (implicit joins) can't be checked or deleted individually.
        const lockBtn = row.isPseudo
            ? `<span class="row-lock" title="Endpoint joins are shared sketch points and cannot be deleted">⊘</span>`
            : "";

        return `
            <div class="row${pseudoClass}${errorClass}${highlightClass}"
                 data-row-key="${escape(row.rowKey || "")}"
                 data-kind="${escape(row.kind || "")}"
                 data-entity-tokens="${escape(entityTokensJson)}"
                 data-action="selectEntities"
                 ${isDimension ? 'data-is-dimension="1"' : ""}
                 role="button"${dblclickTitle}>
                ${checkboxHTML}
                <div class="row-glyph"${glyphAttrs}>${iconImg}</div>
                <div class="row-body">
                    <div class="row-head">
                        <span class="row-label" title="${escape(labelTitle)}">${escape(labelHead)}</span>
                        ${badges.join("")}
                        ${chips ? `<div class="chips">${chips}</div>` : ""}
                    </div>
                    ${exprHTML}
                    ${paramsHTML}
                    ${errorsHTML}
                </div>
                <div class="row-actions">
                    ${selectConstraintBtn}
                    ${lockBtn}
                </div>
            </div>
        `;
    }

    function chipHTML(chip) {
        const lbl = chip.label || chip.kind || "?";
        const tokAttr = chip.token ? ` data-token="${escape(chip.token)}"` : "";
        if (chip.invisible) {
            return `<span class="chip invisible" data-label="${escape(lbl)}"${tokAttr} title="Not visible on canvas — click to filter and select">${escape(lbl)} <span class="chip-hidden">hidden</span></span>`;
        }
        return `<span class="chip" data-label="${escape(lbl)}"${tokAttr} title="Click to filter and select">${escape(lbl)}</span>`;
    }

    // --- Delegated event handling ---------------------------------------

    // Checkbox changes update selection state independently of row clicks.
    els.root.addEventListener("change", (evt) => {
        if (evt.target.matches(".section-check")) {
            let tokens = [];
            try { tokens = JSON.parse(evt.target.getAttribute("data-tokens") || "[]"); } catch (e) {}
            if (evt.target.checked) {
                tokens.forEach(t => state.selected.add(t));
            } else {
                tokens.forEach(t => state.selected.delete(t));
            }
            updateBulkDeleteButton();
            renderSnapshot();
            return;
        }
        if (!evt.target.matches(".row-check")) return;
        const token = evt.target.getAttribute("data-token") || "";
        if (!token) return;
        if (evt.target.checked) {
            state.selected.add(token);
        } else {
            state.selected.delete(token);
        }
        updateBulkDeleteButton();
        _updateSectionCheckboxes();
    });

    els.root.addEventListener("click", (evt) => {
        // Checkbox clicks are handled by the change listener above.
        if (evt.target.matches(".row-check, .section-check")) return;

        // Section header click (#14) — toggle collapse.
        const header = evt.target.closest(".section-header[data-section]");
        if (header) {
            const id = header.getAttribute("data-section");
            if (state.collapsed.has(id)) {
                state.collapsed.delete(id);
            } else {
                state.collapsed.add(id);
            }
            renderSnapshot();
            return;
        }

        // Chip click (#16) — filter by label and select entity on canvas.
        const chip = evt.target.closest(".chip");
        if (chip && els.root.contains(chip)) {
            evt.stopPropagation();
            const label = chip.getAttribute("data-label") || "";
            const token = chip.getAttribute("data-token") || "";
            if (label) {
                state.filter = label.toLowerCase();
                els.filter.value = label;
                renderSnapshot();
            }
            if (token) {
                send(JS_TO_PY.selectEntities, { entityTokens: [token] });
            }
            return;
        }

        const actionEl = evt.target.closest("[data-action]");
        if (!actionEl) return;
        const action = actionEl.getAttribute("data-action");

        if (action === "selectConstraint") {
            evt.stopPropagation();
            const token = actionEl.getAttribute("data-token") || "";
            if (!token) return;
            send(JS_TO_PY.selectConstraint, { token });
            return;
        }

        if (action === "editExpr" || action === "editParam") {
            evt.stopPropagation();
            startEditExpr(actionEl);
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

    function startEditExpr(editBtn) {
        const wrap = editBtn.closest(".dim-expr-wrap");
        if (!wrap) return;
        const span = wrap.querySelector(".dim-expr");
        if (!span) return;
        const token = editBtn.getAttribute("data-token") || "";
        const currentVal = span.textContent || "";
        // editParam buttons use editParameter action; editExpr use editDimension.
        const pyAction = editBtn.getAttribute("data-action") === "editParam"
            ? JS_TO_PY.editParameter : JS_TO_PY.editDimension;

        const input = document.createElement("input");
        input.type = "text";
        input.className = "expr-input";
        input.value = currentVal;

        wrap.replaceChild(input, span);
        editBtn.style.visibility = "hidden";
        input.focus();
        input.select();

        function commit() {
            if (input.disabled) return;
            const newExpr = input.value.trim();
            if (!newExpr) { cancelEdit(); return; }
            input.disabled = true;
            send(pyAction, { token, expression: newExpr });
            // Python always sends a data refresh after, which rebuilds the DOM.
        }

        function cancelEdit() {
            if (!wrap.contains(input)) return;
            wrap.replaceChild(span, input);
            editBtn.style.visibility = "";
        }

        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); commit(); }
            if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cancelEdit(); }
            e.stopPropagation();
        });
        input.addEventListener("blur", () => {
            // Delay to let keydown fire first; disabled flag prevents double-commit.
            setTimeout(() => {
                if (document.contains(input) && !input.disabled) commit();
            }, 150);
        });
        input.addEventListener("click", (e) => e.stopPropagation());
    }

    // Double-click on a row → open Fusion's native edit dialog (#13).
    // Single-click still selects entities; the two preceding clicks on a
    // dblclick are harmless (they just re-select the same entities).
    const _DBLCLICK_KINDS = new Set([
        "Offset curves",
        "CircularPatternConstraint",
        "RectangularPatternConstraint",
    ]);

    els.root.addEventListener("dblclick", (evt) => {
        // Ignore dblclick on interactive controls inside the row.
        if (evt.target.closest(".btn-edit, .expr-input, .row-check, .btn")) return;
        const row = evt.target.closest(".row[data-kind]");
        if (!row) return;
        const kind = row.getAttribute("data-kind") || "";
        const isDimension = row.hasAttribute("data-is-dimension");
        if (!_DBLCLICK_KINDS.has(kind) && !isDimension) return;
        const rowKey = row.getAttribute("data-row-key") || "";
        send(JS_TO_PY.openEditDialog, { kind, rowKey, isDimension });
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
        }, 5000);
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

    // --- Auto-zoom toggle (Pack 4) ---------------------------------------

    let autoZoomOn = localStorage.getItem("cl-autozoom") === "true";

    function updateAutoZoomButton() {
        els.autozoomToggle.classList.toggle("active", autoZoomOn);
        els.autozoomToggle.title = autoZoomOn
            ? "Auto-zoom to selection (on — click to disable)"
            : "Auto-zoom to selection (off — click to enable)";
    }

    els.autozoomToggle.addEventListener("click", () => {
        autoZoomOn = !autoZoomOn;
        localStorage.setItem("cl-autozoom", String(autoZoomOn));
        updateAutoZoomButton();
        send(JS_TO_PY.setAutoZoom, { enabled: autoZoomOn });
    });

    // --- Docked height: cycle button + drag grip (v1.6.0) ----------------
    //
    // Fusion gives a docked custom palette no bottom drag handle unless a
    // maximum size has been registered, and a docked palette refuses size
    // changes outright — Python has to round-trip it through the floating
    // state to apply one. So both controls send a target height and let
    // Python do the work; neither resizes anything client-side.

    const HEIGHT_PRESETS = [
        { label: "50%", fraction: 0.50 },
        { label: "75%", fraction: 0.75 },
        { label: "Full", fraction: 1 },
    ];

    const dock = { docked: false, heightPx: 0, columnPx: 0, minPx: 150, note: "" };

    let presetIndex = (function () {
        const saved = parseInt(localStorage.getItem("cl-height-preset"), 10);
        return Number.isInteger(saved) && saved >= 0 && saved < HEIGHT_PRESETS.length
            ? saved
            : HEIGHT_PRESETS.length - 1;   // default: full height
    })();
    let presetRestored = false;

    // Falls back to the screen height until Python has reported a real
    // measurement, which only happens once the palette is docked.
    function heightReference() {
        return dock.columnPx || window.screen.availHeight || 900;
    }

    // Guard against a partially-copied deploy: if index.html is still the old
    // one, these elements are absent and an unguarded addEventListener below
    // would throw at load time and take the whole palette script down with it.
    const heightControlsPresent = !!(els.heightCycle && els.resizeGrip);

    function updateHeightButton() {
        if (!heightControlsPresent) return;
        els.heightCycle.textContent = `⇕ ${HEIGHT_PRESETS[presetIndex].label}`;
        const where = dock.docked
            ? `docked, column ${dock.columnPx || "?"} px`
            : "floating";
        els.heightCycle.title =
            `Docked height — click to cycle 50% / 75% / full\n`
            + `now ${dock.heightPx || "?"} px (${where})`
            + (dock.note ? `\napplied via ${dock.note}` : "");
    }

    function applyPreset(index) {
        const preset = HEIGHT_PRESETS[index];
        if (preset.fraction >= 1) {
            // Python asks for its safe ceiling, which the dock layout clamps
            // to the column — that also re-measures the column after the
            // Fusion window has been resized.
            send(JS_TO_PY.setPaletteHeight, { full: true });
        } else {
            send(JS_TO_PY.setPaletteHeight, {
                heightPx: Math.round(heightReference() * preset.fraction),
            });
        }
    }

    if (heightControlsPresent) els.heightCycle.addEventListener("click", () => {
        presetIndex = (presetIndex + 1) % HEIGHT_PRESETS.length;
        localStorage.setItem("cl-height-preset", String(presetIndex));
        updateHeightButton();
        applyPreset(presetIndex);
    });

    function onDockInfo(payload) {
        dock.docked = !!payload.docked;
        dock.heightPx = payload.heightPx || 0;
        dock.columnPx = payload.columnPx || 0;
        dock.minPx = payload.minPx || 150;
        dock.note = payload.note || "";
        updateHeightButton();

        // Fusion recreates the palette each session, so a cap never survives a
        // restart. Re-apply the remembered preset once, the first time we hear
        // that the palette is docked and the column has been measured.
        if (!presetRestored && dock.docked && dock.columnPx) {
            presetRestored = true;
            if (HEIGHT_PRESETS[presetIndex].fraction < 1) applyPreset(presetIndex);
        }
    }

    // Drag grip. The height is applied on release rather than per frame,
    // because each apply may bounce the palette through the floating state.
    // During the drag the grip shows the pending value instead.
    (function () {
        if (!heightControlsPresent) return;
        let dragging = false;
        let startY = 0;
        let startHeight = 0;
        let pending = 0;

        function clamp(px) {
            const max = dock.columnPx || 4000;
            return Math.max(dock.minPx, Math.min(Math.round(px), max));
        }

        els.resizeGrip.addEventListener("pointerdown", (e) => {
            dragging = true;
            startY = e.clientY;
            startHeight = dock.heightPx || window.innerHeight;
            pending = startHeight;
            els.resizeGrip.classList.add("dragging");
            els.resizeGrip.setPointerCapture(e.pointerId);
            e.preventDefault();
        });

        els.resizeGrip.addEventListener("pointermove", (e) => {
            if (!dragging) return;
            pending = clamp(startHeight + (e.clientY - startY));
            els.resizeGripReadout.textContent = `${pending} px`;
        });

        function finish(e) {
            if (!dragging) return;
            dragging = false;
            els.resizeGrip.classList.remove("dragging");
            els.resizeGripReadout.textContent = "";
            try { els.resizeGrip.releasePointerCapture(e.pointerId); } catch (_) {}
            if (pending && Math.abs(pending - startHeight) > 2) {
                send(JS_TO_PY.setPaletteHeight, { heightPx: pending });
            }
        }

        els.resizeGrip.addEventListener("pointerup", finish);
        els.resizeGrip.addEventListener("pointercancel", finish);
    })();

    // Note: sketch-change polling deliberately does NOT live here. Fusion fires
    // no event while a resident tool edits the sketch, so a poll is required,
    // but it runs on a Python worker thread (_start_sketch_poll in
    // lifecycle.py) instead of a setInterval in this view. The worker does not
    // depend on the web view being loaded, visible, or focused, and it is
    // verified working. A setInterval here was never actually shown to fail —
    // that test ran against a file the sync client had rolled back, so the JS
    // was not present — but there is no reason to revisit it.

    // --- Auto-hide on sketch exit (issue #9) -----------------------------
    //
    // Pin metaphor, and note the sense is inverted relative to the flag:
    // pinned (default, .active) means "stay open", so autoHide is OFF. Default
    // is pinned so existing behaviour is unchanged unless the user opts in.
    //
    // Fusion has no minimize state for a palette, so this hides and shows
    // rather than collapsing, and it never touches dock position.

    const autohidePresent = !!els.autohideToggle;
    let autoHideOn = localStorage.getItem("cl-autohide") === "true";

    function updateAutoHideButton() {
        if (!autohidePresent) return;
        // .active marks the pinned (non-auto-hiding) state.
        els.autohideToggle.classList.toggle("active", !autoHideOn);
        els.autohideToggle.textContent = autoHideOn ? "📍" : "📌";
        els.autohideToggle.title = autoHideOn
            ? "Auto-hide on — palette hides when you leave a sketch, returns on the next one. Click to pin it open."
            : "Pinned — palette stays open when you leave a sketch. Click to auto-hide instead.";
    }

    if (autohidePresent) els.autohideToggle.addEventListener("click", () => {
        autoHideOn = !autoHideOn;
        localStorage.setItem("cl-autohide", String(autoHideOn));
        updateAutoHideButton();
        send(JS_TO_PY.setAutoHide, { enabled: autoHideOn });
    });

    // --- Theme toggle (#5) -----------------------------------------------

    function updateThemeButton(theme) {
        els.themeToggle.textContent = theme === "dark" ? "☀" : "🌙";
        els.themeToggle.title = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
    }

    els.themeToggle.addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("cl-theme", next);
        updateThemeButton(next);
        renderSnapshot();
    });

    document.addEventListener("DOMContentLoaded", () => {
        const savedTheme = localStorage.getItem("cl-theme") || "dark";
        document.documentElement.setAttribute("data-theme", savedTheme);
        updateThemeButton(savedTheme);
        updateAutoZoomButton();
        updateHeightButton();
        updateAutoHideButton();
        state.loaded = true;
        _sendWhenReady(JS_TO_PY.paletteReady, { autoZoom: autoZoomOn, autoHide: autoHideOn });
    });
})();
