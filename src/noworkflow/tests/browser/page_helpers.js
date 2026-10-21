// Helpers the tests of the vis in a browser install in the page, before any
// script of the page runs (Playwright's add_init_script). The comparison of
// the rebuild-vis skill (.claude/skills/rebuild-vis/compare_vis.mjs) loads
// this same file, so both drive the vis the same way.
//
// window.__vis counts the requests in flight and the time of the last DOM
// change, so that a test can wait until the page is quiet, and finds where
// an input event has to go: a point the browser hits on an element, which a
// large SVG, a clipped pane or a hidden tab make anything but its centre.
(() => {
  const vis = (window.__vis = { inflight: 0, last: performance.now() });
  const touch = () => {
    vis.last = performance.now();
  };
  const realFetch = window.fetch;
  window.fetch = function (...args) {
    vis.inflight++;
    touch();
    return realFetch.apply(this, args).finally(() => {
      vis.inflight--;
      touch();
    });
  };
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (...args) {
    vis.inflight++;
    touch();
    this.addEventListener("loadend", () => {
      vis.inflight--;
      touch();
    });
    return send.apply(this, args);
  };
  // The ace cursor blinks forever: its layer never counts as a change.
  new MutationObserver((records) => {
    if (records.some((r) => !(r.target.closest && r.target.closest(".ace_cursor-layer, .ace_text-input")))) touch();
  }).observe(document, { subtree: true, childList: true, attributes: true, characterData: true });

  // Quiet: nothing in flight and no DOM change for `ms`. A step marks the
  // end of its input with `vis.touch()` first: a wheel event can still be on
  // its way when the page has not changed for a while.
  vis.touch = touch;
  vis.quiet = (ms = 800) => vis.inflight === 0 && performance.now() - vis.last > ms;

  // The part of el inside the window and inside every ancestor that clips.
  vis.visibleRect = (el) => {
    const r = el.getBoundingClientRect();
    let v = { left: Math.max(r.left, 0), top: Math.max(r.top, 0), right: Math.min(r.right, innerWidth), bottom: Math.min(r.bottom, innerHeight) };
    for (let a = el.parentElement; a; a = a.parentElement) {
      if (getComputedStyle(a).overflow === "visible") continue;
      const c = a.getBoundingClientRect();
      v = { left: Math.max(v.left, c.left), top: Math.max(v.top, c.top), right: Math.min(v.right, c.right), bottom: Math.min(v.bottom, c.bottom) };
    }
    return v;
  };
  // A point inside el that the browser hits on el (or a descendant): a grid
  // over its visible part. A form control below the fold of a scrolling
  // modal is scrolled to first, as a user would; graphs never are, their
  // panes clip.
  vis.point = (el) => {
    if (!el) return null;
    if (/^(BUTTON|TEXTAREA|INPUT|SELECT)$/.test(el.tagName)) el.scrollIntoView({ block: "center" });
    const v = vis.visibleRect(el);
    if (v.right <= v.left || v.bottom <= v.top) return null;
    for (const fy of [0.5, 0.3, 0.7, 0.15, 0.85]) {
      for (const fx of [0.5, 0.3, 0.7, 0.15, 0.85]) {
        const x = v.left + (v.right - v.left) * fx, y = v.top + (v.bottom - v.top) * fy;
        const hit = document.elementFromPoint(x, y);
        if (hit && (hit === el || el.contains(hit))) return { x: Math.round(x), y: Math.round(y) };
      }
    }
    return null;
  };
  // A point over svg that hits its background, not a node: where a drag
  // pans instead of moving or selecting something.
  vis.emptyPoint = (svg) => {
    if (!svg) return null;
    const v = vis.visibleRect(svg);
    for (let fy = 0.1; fy < 0.95; fy += 0.1) {
      for (let fx = 0.1; fx < 0.95; fx += 0.1) {
        const x = v.left + (v.right - v.left) * fx, y = v.top + (v.bottom - v.top) * fy;
        const hit = document.elementFromPoint(x, y);
        const background = hit === svg || hit?.tagName === "g" || (hit?.tagName === "polygon" && hit.parentNode.getAttribute("class") === "graph");
        if (hit && svg.contains(hit) && background) return { x: Math.round(x), y: Math.round(y) };
      }
    }
    return null;
  };
  // Of `elements`, the one whose centre is nearest to the centre of the
  // visible part of `within`.
  vis.nearest = (elements, within) => {
    const v = vis.visibleRect(within);
    const distance = (el) => {
      const r = el.getBoundingClientRect();
      return Math.hypot((r.left + r.right - v.left - v.right) / 2, (r.top + r.bottom - v.top - v.bottom) / 2);
    };
    return elements.reduce((best, el) => (distance(el) < distance(best) ? el : best));
  };
  // Where the centre of the visible part of `within` must move for el's
  // centre to reach it, each axis bounded by half the visible part: a drag
  // that a window of that size can hold.
  vis.towards = (el, within) => {
    const v = vis.visibleRect(within), r = el.getBoundingClientRect();
    const cx = (v.left + v.right) / 2, cy = (v.top + v.bottom) / 2;
    const clamp = (d, room) => Math.max(-room, Math.min(room, d));
    const dx = Math.round(clamp(cx - (r.left + r.right) / 2, (v.right - v.left) / 2 - 10));
    const dy = Math.round(clamp(cy - (r.top + r.bottom) / 2, (v.bottom - v.top) / 2 - 10));
    return { x: Math.round(cx - dx / 2), y: Math.round(cy - dy / 2), dx, dy };
  };

  // The lumino dock: tabs by label (current ones marked with "*"), and the
  // rectangles of the widgets on screen.
  vis.tab = (label) => [...document.querySelectorAll(".lm-TabBar-tab")].find((t) => t.querySelector(".lm-TabBar-tabLabel")?.textContent === label);
  vis.tabs = () => [...document.querySelectorAll(".lm-TabBar-tab")].map((t) => (t.classList.contains("lm-mod-current") ? "*" : "") + t.querySelector(".lm-TabBar-tabLabel")?.textContent);
  vis.rects = () =>
    [...document.querySelectorAll(".lm-DockPanel-widget")]
      .filter((w) => !w.classList.contains("lm-mod-hidden"))
      .map((w) => {
        const r = w.getBoundingClientRect();
        return [r.left, r.top, r.width, r.height].map(Math.round).join(",");
      });
  vis.visible = (el) => !!el && el.getClientRects().length > 0 && !el.closest(".lm-mod-hidden");
  vis.button = (label) => [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === label && vis.visible(b));
  vis.transform = (el) => (el ? el.getAttribute("transform") || el.style.transform || "" : null);

  // The views. The history graph's trials; the graph of a trial (an SVG in
  // a trial widget whose nodes are not trials); the dataflow's svg-pan-zoom
  // viewport; a table of the database graph by name.
  vis.historyNodes = () => [...document.querySelectorAll("g.node[attr-trialid] > rect")];
  vis.historyNode = (tag) => vis.historyNodes().find((r) => r.getAttribute("title") === tag);
  vis.historyGroup = () => document.querySelector("g[id^=history-graph]");
  vis.trialGraph = () => [...document.querySelectorAll("svg")].find((s) => vis.visible(s) && s.closest(".trial-widget") && s.querySelector("g.node") && !s.querySelector("g.node[attr-trialid]"));
  vis.trialGroup = () => vis.trialGraph()?.querySelector("g[id^=trial-graph]");
  vis.diffGraph = () => [...document.querySelectorAll(".diff-widget svg")].find((s) => vis.visible(s) && s.querySelector("g.node"));
  vis.dataflow = () => document.querySelector("g.svg-pan-zoom_viewport");
  vis.dataflowBoxes = () => [...(vis.dataflow()?.querySelectorAll("g.node") ?? [])].filter((g) => g.children[1]?.tagName === "polygon");
  vis.prospective = () => document.querySelector(".prospective-content svg");
  vis.table = (name) => [...document.querySelectorAll("svg g.node")].find((g) => g.querySelector("text")?.textContent === name && vis.visible(g));
})();
