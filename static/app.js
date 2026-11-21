/* Mushroom Livability front end.
 * Plain JavaScript, no dependencies. Reads api/results (relative, so the page
 * also works from a static copy such as GitHub Pages) once and renders
 * everything from that document. State = { group, query, selectedId, compareA, compareB }.
 * No location is singled out: the comparison starts with ranks 1 and 2 and the
 * reader can pick any two.
 */
(function () {
  "use strict";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var state = { data: null, group: "All", query: "", selectedId: null, compareA: null, compareB: null };
  var $ = function (id) { return document.getElementById(id); };

  // ---- tiny helpers ----------------------------------------------------
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === "text") node.textContent = attrs[key];
      else if (key === "style") node.setAttribute("style", attrs[key]);
      else if (key.indexOf("on") === 0) node.addEventListener(key.slice(2), attrs[key]);
      else node.setAttribute(key, attrs[key]);
    });
    (children || []).forEach(function (child) { if (child) node.appendChild(child); });
    return node;
  }
  function svg(tag, attrs) {
    var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    return node;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function num(value, digits) {
    if (value === null || value === undefined) return "–";
    return Number(value).toLocaleString("en-US", { minimumFractionDigits: digits || 0, maximumFractionDigits: digits || 0 });
  }
  function smart(value) {
    if (value === null || value === undefined) return "–";
    var a = Math.abs(value);
    return num(value, a >= 100 || Number.isInteger(value) ? 0 : a >= 1 ? 2 : 3);
  }
  function hexToRgb(hex) {
    hex = hex.replace("#", "");
    return [0, 2, 4].map(function (i) { return parseInt(hex.substr(i, 2), 16); });
  }
  function ramp(t) {
    var p = state.data.palette, lo = hexToRgb(p.sequential_low), hi = hexToRgb(p.sequential_high);
    t = Math.max(0, Math.min(1, t));
    return "rgb(" + lo.map(function (c, i) { return Math.round(c + (hi[i] - c) * t); }).join(",") + ")";
  }
  function color(key) { return state.data.palette.components[key] || "#999999"; }
  function byId(id) {
    return state.data.locations.filter(function (l) { return l.id === id; })[0] || null;
  }

  // ---- tooltip ---------------------------------------------------------
  var tip = $("tooltip");
  function attachTip(node, html) {
    node.addEventListener("mouseenter", function () { tip.innerHTML = ""; tip.appendChild(html()); tip.hidden = false; });
    node.addEventListener("mousemove", function (e) {
      var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
      var y = e.clientY + 16;
      if (y + tip.offsetHeight > window.innerHeight - 8) y = e.clientY - tip.offsetHeight - 10;
      tip.style.left = x + "px"; tip.style.top = y + "px";
    });
    node.addEventListener("mouseleave", function () { tip.hidden = true; });
  }
  function tipLines(title, lines) {
    var box = el("div", {}, [el("b", { text: title })]);
    lines.forEach(function (line) { box.appendChild(el("div", { text: line })); });
    return box;
  }

  // ---- header ----------------------------------------------------------
  // When the provider data was fetched (from the cache records), not when the file was built.
  function retrievalText(d) {
    var w = d.data_retrieved;
    if (!w) return (d.synthetic ? "demo data generated " : "results built ") + d.generated_at.slice(0, 10);
    var first = w.first.slice(0, 10), last = w.last.slice(0, 10);
    return "data retrieved " + (first === last ? first : first + " – " + last);
  }
  function renderHeader() {
    var d = state.data, v = d.verdict, banner = $("banner"), notes = [];
    if (d.synthetic) notes.push("DEMO MODE — synthetic placeholder numbers, not real data. Run the real pipeline for actual results.");
    if (d.partial) notes.push("Partial run — only some locations were processed, so scores are not comparable with a full run.");
    if (notes.length) { banner.textContent = notes.join("  ·  "); banner.hidden = false; }

    $("verdict").textContent = v.sentence || "No location could be scored yet.";

    var scored = d.locations.filter(function (l) { return l.scored; }).length, groups = d.groups || [];
    $("meta").textContent = scored + " locations scored in " + groups.length + " regions, all with the same method · everything within " +
      num(d.settings.radius_km) + " km of each city centre · " + retrievalText(d);

    var regions = $("regions"), best = v.best_by_group || {};
    clear(regions);
    groups.forEach(function (group) {
      var loc = byId(best[group]);
      if (!loc) return;
      regions.appendChild(el("span", { title: "Highest score in " + group }, [
        document.createTextNode("Best in " + group + ": "), el("b", { text: loc.name }),
        document.createTextNode(" " + num(loc.score, 1) + " (#" + loc.rank + ")")
      ]));
    });

    var download = $("download"), url = d.settings.download_url;
    if (url && /^https:\/\//.test(url)) {
      download.setAttribute("href", url);
      download.setAttribute("rel", "noopener");
      download.hidden = false;
    }
  }

  // ---- heatmap ---------------------------------------------------------
  function heatmap(loc) {
    var h = loc.heatmap;
    if (!h) return el("p", { class: "muted", text: "No observation coordinates available for a density map." });
    var size = 480, cell = size / h.cells, root = svg("svg", { viewBox: "0 0 " + size + " " + size, class: "heatmap", role: "img" });
    root.setAttribute("aria-label", "Density map of recent fungal observations around " + loc.name);
    root.appendChild(svg("rect", { x: 0, y: 0, width: size, height: size, fill: state.data.palette.sequential_low }));
    var kmPerCell = h.span_km / h.cells;
    h.counts.forEach(function (row, r) {
      row.forEach(function (count, c) {
        if (!count) return;
        var rect = svg("rect", {
          x: c * cell + 0.5, y: r * cell + 0.5, width: cell - 1, height: cell - 1, rx: 2,
          fill: ramp(0.12 + 0.88 * Math.sqrt(count / h.max))
        });
        attachTip(rect, function () {
          return tipLines(loc.name, [num(count) + " of the " + num(h.points) + " most recent records", "in this " + num(kmPerCell, 1) + " × " + num(kmPerCell, 1) + " km cell"]);
        });
        root.appendChild(rect);
      });
    });
    root.appendChild(svg("circle", { cx: size / 2, cy: size / 2, r: size / 2 - 1, fill: "none", stroke: "#22302a", "stroke-opacity": 0.28, "stroke-dasharray": "3 5" }));
    root.appendChild(svg("circle", { cx: size / 2, cy: size / 2, r: 4, fill: "#ffffff", stroke: "#22302a", "stroke-width": 1.5 }));
    return root;
  }
  function mapBlock(loc) {
    var wrap = el("div", {}, [el("p", { class: "map-title", text: "Where recent finds cluster" }), heatmap(loc)]);
    if (loc.heatmap) {
      wrap.appendChild(el("p", { class: "map-note", text: "North is up · " + num(loc.heatmap.span_km) + " km across · dashed circle = search radius · white dot = city centre · latest " + num(loc.heatmap.points) + " research-grade records, darker = more" }));
    }
    return wrap;
  }

  // ---- compare two locations --------------------------------------------
  function fact(value, label) { return el("div", { class: "fact" }, [el("b", { text: value }), el("span", { text: label })]); }
  function duelCard(loc, isWinner, isTie) {
    var m = loc.metrics;
    return el("div", { class: "card duel-card" + (isWinner && !isTie ? " winner" : "") }, [
      el("div", { class: "duel-top" }, [
        el("div", {}, [
          el("h3", { class: "duel-name", text: loc.name }),
          el("p", { class: "duel-sub", text: loc.country + " · rank " + loc.rank + " overall" }),
          isWinner && !isTie ? el("span", { class: "pill", text: "Higher score" }) : null
        ]),
        el("div", { class: "big-score" }, [document.createTextNode(num(loc.score, 1)), el("small", { text: "/ 100" })])
      ]),
      el("div", { class: "facts" }, [
        fact(num(loc.raw.fungi_observations), "research-grade observations"),
        fact(num(loc.raw.species_count), "species recorded"),
        fact(num(m.reliable_months) + " / 12", "reliable months")
      ]),
      mapBlock(loc)
    ]);
  }
  function butterfly(a, b) {
    var rows = [el("div", { class: "bf-head" }, [el("span", { text: a.name }), el("span", {}), el("span", { text: b.name })])];
    var other = {};
    b.components.forEach(function (c) { other[c.key] = c; });
    a.components.forEach(function (ca) {
      var cb = other[ca.key], max = ca.weight * 100;
      function side(c, cls, name) {
        var fill = el("div", { class: "bf-fill", style: "width:" + (c.contribution / max * 100).toFixed(1) + "%;background:" + color(c.key) });
        var node = el("div", { class: "bf-side " + cls }, [el("div", { class: "bf-track" }, [fill]), el("span", { text: num(c.contribution, 1) })]);
        attachTip(node, function () {
          return tipLines(name + " · " + c.label, [num(c.contribution, 1) + " of " + num(max, 1) + " possible points"].concat(
            c.submetrics.map(function (s) { return s.label + ": " + smart(s.raw); })));
        });
        return node;
      }
      rows.push(el("div", { class: "bf-row" }, [
        side(ca, "left", a.name),
        el("div", { class: "bf-label" }, [document.createTextNode(ca.label), el("small", { text: "max " + num(max, 1) + " pts" })]),
        side(cb, "right", b.name)
      ]));
    });
    return el("div", { class: "card butterfly" }, rows);
  }
  function renderPickers() {
    var scored = state.data.locations.filter(function (l) { return l.scored; });
    [["compare-a", "compareA"], ["compare-b", "compareB"]].forEach(function (pair) {
      var node = $(pair[0]);
      clear(node);
      scored.forEach(function (l) { node.appendChild(el("option", { value: l.id, text: l.rank + ". " + l.name + ", " + l.country })); });
      node.value = state[pair[1]];
      node.onchange = function () { state[pair[1]] = node.value; renderDuel(); };
    });
  }
  function renderDuel() {
    var body = $("duel-body"), a = byId(state.compareA), b = byId(state.compareB);
    clear(body);
    if (!a || !b) {
      $("duel-lede").textContent = "At least two locations must be scored for a comparison. See the coverage notes under “How the score works”.";
      return;
    }
    $("duel-lede").textContent = "Pick any two locations; the page opens on the two highest-ranked. Same radius, same sources, same formula. The bars show how many points each ingredient adds to the total.";
    if (a.id === b.id) {
      body.appendChild(el("p", { class: "muted", text: "Choose two different locations to compare." }));
      return;
    }
    var pair = a.score >= b.score ? [a, b] : [b, a], isTie = pair[0].score - pair[1].score < state.data.verdict.tie_margin;
    var cards = el("div", { class: "duel" }, [a, b].map(function (loc) { return duelCard(loc, loc.id === pair[0].id, isTie); }));
    body.appendChild(cards);
    body.appendChild(butterfly(a, b));
  }

  // ---- ranking ---------------------------------------------------------
  function visibleLocations() {
    var q = state.query.trim().toLowerCase();
    return state.data.locations.filter(function (l) {
      if (!l.scored) return false;
      if (state.group !== "All" && l.group !== state.group) return false;
      return !q || (l.name + " " + l.country).toLowerCase().indexOf(q) !== -1;
    });
  }
  function renderChips() {
    var groups = ["All"].concat(state.data.groups || []), chips = $("chips");
    state.data.locations.forEach(function (l) { if (groups.indexOf(l.group) === -1) groups.push(l.group); });
    clear(chips);
    groups.forEach(function (group) {
      chips.appendChild(el("button", {
        class: "chip", type: "button", text: group, "aria-pressed": String(group === state.group),
        onclick: function () { state.group = group; renderChips(); renderRanking(); renderCalendar(); }
      }));
    });
  }
  function renderLegend() {
    var legend = $("legend");
    clear(legend);
    state.data.model.forEach(function (c) {
      legend.appendChild(el("span", {}, [el("i", { style: "background:" + color(c.key) }), document.createTextNode(c.label + " (" + num(c.weight * 100) + "%)")]));
    });
  }
  function stack(loc) {
    var bar = el("div", { class: "stack" });
    loc.components.forEach(function (c) {
      if (c.contribution <= 0.05) return;
      var seg = el("div", { class: "seg", style: "width:" + c.contribution.toFixed(2) + "%;background:" + color(c.key) });
      attachTip(seg, function () { return tipLines(loc.name + " · " + c.label, [num(c.contribution, 1) + " of " + num(c.weight * 100, 1) + " possible points"]); });
      bar.appendChild(seg);
    });
    return el("div", { class: "stack-track" }, [bar]);
  }
  function select(id, scroll) {
    state.selectedId = id;
    $("detail-select").value = id;
    renderRanking();
    renderDetail();
    if (scroll) $("detail").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function renderRanking() {
    var body = $("rank-table").querySelector("tbody"), rows = visibleLocations();
    clear(body);
    $("rank-empty").hidden = rows.length > 0;
    rows.forEach(function (loc) {
      var name = el("td", {}, [el("span", { class: "loc-name", text: loc.name })]);
      var row = el("tr", { tabindex: "0", class: loc.id === state.selectedId ? "selected" : "", "aria-label": loc.name + ", score " + num(loc.score, 1) }, [
        el("td", { class: "num", text: String(loc.rank) }), name, el("td", { text: loc.country }),
        el("td", { class: "num score-cell", text: num(loc.score, 1) }), el("td", {}, [stack(loc)])
      ]);
      row.addEventListener("click", function () { select(loc.id, true); });
      row.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(loc.id, true); } });
      body.appendChild(row);
    });
  }

  // ---- detail ----------------------------------------------------------
  function miniBars(values, cls, label, format) {
    var max = Math.max.apply(null, values.concat([1e-9]));
    var bars = el("div", { class: "mini " + cls, role: "img", "aria-label": label });
    values.forEach(function (v, i) {
      var bar = el("div", { class: "bar", style: "height:" + Math.max(1, v / max * 100).toFixed(1) + "%" });
      attachTip(bar, function () { return tipLines(MONTHS[i], [format(v, i)]); });
      bars.appendChild(bar);
    });
    return el("div", {}, [bars, el("div", { class: "months" }, MONTHS.map(function (m) { return el("span", { text: m[0] }); }))]);
  }
  function renderDetail() {
    var loc = byId(state.selectedId), body = $("detail-body"), questions = {};
    clear(body);
    if (!loc) return;
    state.data.model.forEach(function (c) { questions[c.key] = c.question; });
    $("detail-title").textContent = "Score breakdown — " + loc.name + " (" + num(loc.score, 1) + ")";

    var left = el("div", { class: "card" });
    loc.components.forEach(function (c) {
      var max = c.weight * 100, table = el("table", { class: "subs" });
      c.submetrics.forEach(function (s) {
        table.appendChild(el("tr", {}, [
          el("td", { text: s.label }), el("td", { class: "num", text: smart(s.raw) + " " + s.unit }),
          el("td", { class: "num", text: num(s.normalized * 100) + " / 100" })
        ]));
      });
      left.appendChild(el("div", { class: "comp" }, [
        el("div", { class: "comp-head" }, [
          el("span", { class: "comp-name" }, [el("i", { class: "swatch", style: "background:" + color(c.key) }), document.createTextNode(c.label)]),
          el("span", { class: "comp-pts" }, [document.createTextNode(num(c.contribution, 1) + " "), el("small", { text: "of " + num(max, 1) + " pts" })])
        ]),
        el("p", { class: "comp-q", text: questions[c.key] || "" }),
        el("div", { class: "meter" }, [el("div", { style: "width:" + (c.value * 100).toFixed(1) + "%;background:" + color(c.key) })]),
        table
      ]));
    });

    var right = el("div", { class: "card" }, [mapBlock(loc)]);
    if (loc.monthly_share) {
      right.appendChild(el("p", { class: "mini-title", text: "Observations by month" }));
      right.appendChild(miniBars(loc.monthly_share, "", "Share of yearly observations per month", function (v, i) {
        return num(v * 100, 1) + "% of the year · " + num(loc.raw.monthly_observations[i]) + " records";
      }));
    }
    if (loc.climate_month_suitability) {
      right.appendChild(el("p", { class: "mini-title", text: "Climate suitability by month" }));
      right.appendChild(miniBars(loc.climate_month_suitability, "climate", "Climate suitability per month", function (v, i) {
        var c = loc.raw.climate_monthly[i];
        return "Suitability " + num(v, 2) + " · " + num(c.temp_c, 1) + " °C · " + num(c.precip_mm) + " mm";
      }));
    }
    body.appendChild(el("div", { class: "detail-grid" }, [left, right]));
  }
  function renderSelect() {
    var select_ = $("detail-select");
    clear(select_);
    state.data.locations.filter(function (l) { return l.scored; }).forEach(function (l) {
      select_.appendChild(el("option", { value: l.id, text: l.rank + ". " + l.name + ", " + l.country }));
    });
    select_.value = state.selectedId;
    select_.onchange = function () { select(select_.value, false); };
  }

  // ---- seasonal calendar -----------------------------------------------
  function renderCalendar() {
    var box = $("calendar"), rows = visibleLocations().filter(function (l) { return l.monthly_share; });
    clear(box);
    if (!rows.length) { box.appendChild(el("p", { class: "muted", text: "No location matches this filter." })); return; }
    var top = 0;
    rows.forEach(function (l) { top = Math.max(top, Math.max.apply(null, l.monthly_share)); });
    top = Math.max(top, 0.01);
    var grid = el("div", { class: "cal-grid" }, [el("span", {})].concat(MONTHS.map(function (m) { return el("span", { class: "cal-month", text: m }); })));
    rows.forEach(function (loc) {
      grid.appendChild(el("span", { class: "cal-name", text: loc.name }));
      loc.monthly_share.forEach(function (share, i) {
        var cell = el("span", { class: "cal-cell", style: "background:" + ramp(share / top) });
        attachTip(cell, function () {
          return tipLines(loc.name + " · " + MONTHS[i], [num(share * 100, 1) + "% of yearly observations", num(loc.raw.monthly_observations[i]) + " records"]);
        });
        grid.appendChild(cell);
      });
    });
    var scale = el("div", { class: "cal-scale" }, [
      el("span", { text: "0%" }),
      el("span", { class: "ramp", style: "background:linear-gradient(90deg," + ramp(0) + "," + ramp(1) + ")" }),
      el("span", { text: num(top * 100) + "% of the year in one month" })
    ]);
    box.appendChild(el("div", { class: "cal" }, [grid, scale]));
  }

  // ---- method & sources --------------------------------------------------
  function renderMethod() {
    var d = state.data, model = $("model"), coverage = $("coverage"), sources = $("sources");
    clear(model); clear(coverage); clear(sources);
    model.appendChild(el("p", { class: "lede", text: "Each ingredient is scaled to 0–1, multiplied by its weight and summed to a score out of 100. Counts use a logarithm and are scaled between the weakest and strongest location in this comparison; months and shares are scaled against a fixed ceiling." }));
    var grid = el("div", { class: "card model-rows" });
    d.model.forEach(function (c) {
      var list = el("ul", {}, c.submetrics.map(function (s) {
        return el("li", { text: s.label + (c.submetrics.length > 1 ? " (" + num(s.weight * 100) + "% of this ingredient)" : "") + " — " + s.why });
      }));
      grid.appendChild(el("div", { class: "model-row" }, [
        el("div", { class: "w", text: num(c.weight * 100) + "%" }),
        el("div", {}, [
          el("h4", {}, [el("i", { class: "swatch", style: "background:" + color(c.key) }), document.createTextNode(c.label)]),
          el("p", { text: c.question })
        ]),
        list
      ]));
    });
    model.appendChild(grid);

    var notes = [];
    d.exclusions.forEach(function (x) { notes.push("Left out — " + x.label + ": " + x.reason + "."); });
    d.unscored.forEach(function (u) { notes.push(u.name + " could not be scored (missing: " + u.missing.join(", ") + ")."); });
    if (notes.length) {
      coverage.appendChild(el("div", { class: "notice" }, [
        el("b", { text: "Coverage notes" }), el("ul", {}, notes.map(function (n) { return el("li", { text: n }); }))
      ]));
    }
    d.sources.forEach(function (s) {
      var title = s.url ? el("a", { href: s.url, target: "_blank", rel: "noopener", text: s.title }) : el("span", { text: s.title });
      sources.appendChild(el("li", {}, [
        el("b", {}, [title]),
        el("div", { text: s.provider + " · Licence: " + s.license }),
        el("div", { text: "Used for: " + s.used_for }),
        el("div", { class: "how", text: "How it is retrieved: " + s.retrieval })
      ]));
    });
  }

  // ---- boot ------------------------------------------------------------
  function render() {
    var v = state.data.verdict;
    state.selectedId = v.leader_id;
    state.compareA = v.leader_id;
    state.compareB = v.runner_up_id;
    renderHeader(); renderPickers(); renderDuel(); renderChips(); renderLegend(); renderSelect();
    renderRanking(); renderDetail(); renderCalendar(); renderMethod();
    $("search").addEventListener("input", function (e) { state.query = e.target.value; renderRanking(); renderCalendar(); });
    $("content").hidden = false;
    document.body.setAttribute("data-ready", "true");
  }
  function fail(message) {
    $("verdict").textContent = message;
    document.body.setAttribute("data-ready", "error");
  }
  fetch("api/results")
    .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
    .then(function (res) {
      if (!res.ok) return fail(res.body.message || "Results are not available.");
      state.data = res.body;
      render();
    })
    .catch(function (err) { fail("Could not load results: " + err.message); });
})();
