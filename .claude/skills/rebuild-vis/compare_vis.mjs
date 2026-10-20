// Compare what the vis draws and does with two bundles, in headless Chrome.
//
// Part of the rebuild-vis skill. Serves one store of the test corpus with
// the working tree's `now vis`, in the e2e harness's synthetic environment,
// and drives the same scenario three times in a fresh Chrome: with the base
// bundle, with the base bundle again (the control) and with the new one.
// The bundle is swapped in the browser (DevTools Protocol, Fetch domain), so
// the tracked bundle.js is never touched and the two bundles can be any two
// files; everything else the page loads (the CSS, the hashed images the
// bundle names, the routes) comes from the working tree's server. Each step
// of the scenario opens a view or acts on one with real input events
// (wheel, drag, click, right click, Shift+click, typing), waits until the
// page is quiet, and keeps:
//
//   - the DOM, serialized one node per line (attributes sorted, the value of
//     inputs, a hash of each <style>), ids that change between runs and
//     the coordinates of the database graph (d3-force's clock) masked;
//   - the measures of the interaction (a transform before and after, how
//     many nodes, which tab is current), and whether the view came up at all;
//   - the events: console messages, uncaught exceptions, dialogs, and
//     responses with status >= 400.
//
// A change between base and new that the control does not show is a
// difference of the new bundle. The control is what makes the result
// readable: whatever differs between two runs of the same bundle is noise,
// and the comparison discounts it line by line.
//
// usage, from the repository root and outside the sandbox (the server binds
// a port, Chrome needs its own profile directory), with a Node that has a
// global WebSocket (22 or later; nothing to install):
//
//   node .claude/skills/rebuild-vis/compare_vis.mjs ROOT OUT
//        [--base FILE] [--new FILE] [--now PATH] [--port N] [--chrome PATH]
//        [--runs LIST]
//
// ROOT     a store root the way the e2e harness leaves it under --basetemp
//          (ROOT/project/.noworkflow, ROOT/home, ROOT/tmp); the scenario
//          needs two trials: <basetemp>/two_trials0 of test_list_shows
// OUT      a directory that does not exist yet
// --base   the bundle to compare against (default: bundle.js at HEAD)
// --new    the bundle under test (default: the working tree's bundle.js)
// --now    the `now` that serves (default: .venv/bin/now of the checkout)
// --chrome Chrome or Chromium (default: CHROME, then the usual locations)
// --runs   only these runs, no comparison (base, control, new): to adapt
//          the scenario after a change to the vis, with --runs base
//
// OUT/report.txt   one line per step: dom, measures, events (also printed)
// OUT/<run>/NN-step.dom.txt   the serialized DOM after each step, per run
//                  (base, control, new): it holds the store's synthetic
//                  environment and paths, so it is read here, never pasted
// OUT/<run>/steps.json        measures and events of every step
// OUT/diff/NN-step.diff       base against new, for every step that differs
// OUT/server.log   what `now vis` printed
//
// Exit status: 0 when new shows no difference the control does not; 1 when
// it does; 2 when the comparison itself failed (no server, no Chrome, a
// step the base bundle never reached: the scenario no longer matches the
// vis, and it is fixed here before anything is concluded).

import { spawn, spawnSync, execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const BUNDLE = "src/noworkflow/now/vis/static/dist/bundle.js";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function fail(message) {
  console.error(`compare_vis: ${message}`);
  process.exit(2);
}

function parseArgs(argv) {
  const usage = "usage: compare_vis.mjs ROOT OUT [--base FILE] [--new FILE] [--now PATH] [--port N] [--chrome PATH] [--runs LIST]";
  const args = { positional: [] };
  for (let i = 0; i < argv.length; i++) {
    if (!argv[i].startsWith("--")) args.positional.push(argv[i]);
    else if (["base", "new", "now", "port", "chrome", "runs"].includes(argv[i].slice(2)) && i + 1 < argv.length) args[argv[i].slice(2)] = argv[++i];
    else fail(`${argv[i]}?\n${usage}`);
  }
  if (args.positional.length !== 2) fail(usage);
  return args;
}

function findChrome(given) {
  const candidates = [
    given,
    process.env.CHROME,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  ];
  for (const c of candidates) if (c && fs.existsSync(c)) return c;
  for (const name of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]) {
    const found = spawnSync("which", [name], { encoding: "utf8" });
    if (found.status === 0) return found.stdout.trim();
  }
  return null;
}

// The environment of the e2e harness (clean_env in tests/e2e/harness.py):
// the store records it, and PYTHONHASHSEED fixes the order of the DOT that
// `now export dataflow` prints. The directory of `now` goes first on the
// PATH: the /commands/* routes start a bare `now`.
function harnessEnv(root, now) {
  const dirs = [path.dirname(now), "/usr/bin", "/bin", "/usr/local/bin"];
  const git = spawnSync("which", ["git"], { encoding: "utf8" });
  if (git.status === 0) dirs.push(path.dirname(git.stdout.trim()));
  const env = {
    PATH: [...new Set(dirs)].join(path.delimiter),
    HOME: path.join(root, "home"),
    USERPROFILE: path.join(root, "home"),
    USER: "nowtest",
    LOGNAME: "nowtest",
    USERNAME: "nowtest",
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
    PYTHONHASHSEED: "0",
    COLUMNS: "100",
    NO_COLOR: "1",
    PYTHON_COLORS: "0",
    TMPDIR: path.join(root, "tmp"),
    TEMP: path.join(root, "tmp"),
    TMP: path.join(root, "tmp"),
  };
  for (const key of ["SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "PATHEXT", "COMSPEC", "PROGRAMDATA"]) {
    if (process.env[key]) env[key] = process.env[key];
  }
  return env;
}

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

async function answers(url) {
  try {
    return (await fetch(url)).status;
  } catch {
    return 0;
  }
}

// --- the page side -------------------------------------------------------

// The page helpers of the tests of the vis in a browser (window.__vis: where
// input goes, when the page is quiet, the views), installed before any
// script of the page runs, so that this comparison and the tests drive the
// vis the same way.
const PAGE_HELPERS = path.join(REPO, "src/noworkflow/tests/browser/page_helpers.js");

// Also before any script of the page: fixes the two sources of randomness
// the vis draws ids from (makeid uses Math.random, lumino's UUID uses
// crypto), so that two runs of the same bundle draw the same ids.
const SEED = `(() => {
  let s = 0x9e3779b9;
  Math.random = () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return (s >>> 0) / 4294967296; };
  let c = 12345;
  crypto.getRandomValues = (array) => {
    const bytes = new Uint8Array(array.buffer, array.byteOffset, array.byteLength);
    for (let i = 0; i < bytes.length; i++) { c = (Math.imul(c, 1103515245) + 12345) & 0x7fffffff; bytes[i] = (c >> 16) & 0xff; }
    return array;
  };
})();`;

// The snapshot of the DOM this comparison diffs, added to window.__vis.
const SNAPSHOT = `(() => {
  const vis = window.__vis;
  const hash = (text) => { let h = 2166136261; for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(16); };
  // One node per line, attributes sorted; the value of form fields, which is
  // no attribute; a hash of each <style> (style-loader puts the CSS of the
  // packages there, so a CSS change shows as a changed hash). Inside the
  // database graph the coordinates are masked: a click or a drag on a table
  // reheats d3-force's simulation, whose ticks follow the clock.
  const POSITION = new Set(["x", "y", "x1", "x2", "y1", "y2", "cx", "cy", "transform"]);
  vis.snapshot = () => {
    const out = [];
    const walk = (n, depth, force = false) => {
      const pad = " ".repeat(depth);
      if (n.nodeType === 3) {
        const text = n.textContent.replace(/\\s+/g, " ").trim();
        if (text) out.push(pad + JSON.stringify(text));
        return;
      }
      if (n.nodeType !== 1) return;
      const tag = n.tagName.toLowerCase();
      if (tag === "style") { out.push(pad + "<style #" + hash(n.textContent) + " " + n.textContent.length + ">"); return; }
      if (tag === "script") { out.push(pad + "<script src=" + JSON.stringify(n.getAttribute("src") || "") + ">"); return; }
      if (n.classList.contains("ace_cursor-layer")) { out.push(pad + "<ace cursor layer>"); return; }
      force = force || (tag === "svg" && !!n.querySelector("g.node > circle"));
      const attrs = [...n.attributes].map((a) => a.name + "=" + (force && POSITION.has(a.name) ? "<force>" : JSON.stringify(a.value))).sort();
      if (tag === "input" || tag === "textarea" || tag === "select") attrs.push(".value=" + JSON.stringify(String(n.value)));
      if (tag === "input" && (n.type === "checkbox" || n.type === "radio")) attrs.push(".checked=" + n.checked);
      out.push(pad + "<" + tag + (attrs.length ? " " + attrs.join(" ") : "") + ">");
      for (const child of n.childNodes) walk(child, depth + 1, force);
    };
    walk(document.documentElement, 0);
    return out.join("\\n");
  };
})();`;

// --- the browser side ----------------------------------------------------

class Browser {
  constructor(chrome, profile) {
    this.chrome = chrome;
    this.profile = profile;
    this.id = 0;
    this.pending = new Map();
    this.events = [];
    this.loads = 0;
    this.bundleServed = 0;
  }

  async start(bundle) {
    fs.mkdirSync(this.profile, { recursive: true });
    this.proc = spawn(this.chrome, [
      "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
      "--disable-extensions", "--disable-background-networking", "--disable-component-update",
      "--force-device-scale-factor=1", "--hide-scrollbars", "--lang=en-US",
      "--remote-debugging-port=0", `--user-data-dir=${this.profile}`,
      "--window-size=1400,1000", "about:blank",
    ], { stdio: "ignore" });
    const portFile = path.join(this.profile, "DevToolsActivePort");
    let port;
    for (let i = 0; i < 100 && !port; i++) {
      if (fs.existsSync(portFile)) port = fs.readFileSync(portFile, "utf8").split("\n")[0].trim();
      if (!port) await sleep(100);
    }
    if (!port) throw new Error("Chrome did not open its DevTools port");
    let target;
    for (let i = 0; i < 50 && !target; i++) {
      try {
        const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
        target = list.find((t) => t.type === "page");
      } catch { /* not up yet */ }
      if (!target) await sleep(100);
    }
    if (!target) throw new Error("Chrome has no page target");
    this.ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((r, j) => { this.ws.addEventListener("open", r); this.ws.addEventListener("error", j); });
    const body = fs.readFileSync(bundle).toString("base64");
    this.ws.addEventListener("message", (m) => this.onMessage(JSON.parse(m.data), body));
    await this.send("Runtime.enable");
    await this.send("Page.enable");
    await this.send("Network.enable");
    // From the cache, the bundle would never reach the Fetch domain.
    await this.send("Network.setCacheDisabled", { cacheDisabled: true });
    await this.send("Fetch.enable", { patterns: [{ urlPattern: "*/dist/bundle.js*" }] });
    for (const source of [SEED, fs.readFileSync(PAGE_HELPERS, "utf8"), SNAPSHOT]) {
      await this.send("Page.addScriptToEvaluateOnNewDocument", { source });
    }
  }

  onMessage(msg, body) {
    if (msg.id && this.pending.has(msg.id)) {
      this.pending.get(msg.id)(msg);
      this.pending.delete(msg.id);
      return;
    }
    const p = msg.params;
    switch (msg.method) {
      case "Fetch.requestPaused":
        this.bundleServed++;
        this.send("Fetch.fulfillRequest", {
          requestId: p.requestId, responseCode: 200, body,
          responseHeaders: [{ name: "Content-Type", value: "application/javascript; charset=utf-8" }],
        });
        break;
      case "Runtime.consoleAPICalled":
        this.events.push(`console.${p.type}: ` + p.args.map((a) => a.value ?? a.description ?? a.type).join(" ").slice(0, 300));
        break;
      case "Runtime.exceptionThrown":
        this.events.push("exception: " + (p.exceptionDetails.exception?.description ?? p.exceptionDetails.text).split("\n")[0]);
        break;
      case "Page.javascriptDialogOpening":
        this.events.push(`dialog ${p.type}: ${p.message}`);
        this.send("Page.handleJavaScriptDialog", { accept: true });
        break;
      case "Network.responseReceived":
        if (p.response.status >= 400) this.events.push(`http ${p.response.status}: ${new URL(p.response.url).pathname}`);
        break;
      case "Network.loadingFailed":
        if (!p.canceled) this.events.push(`network failed: ${p.errorText}`);
        break;
    }
  }

  send(method, params = {}) {
    return new Promise((resolve) => {
      const n = ++this.id;
      this.pending.set(n, resolve);
      this.ws.send(JSON.stringify({ id: n, method, params }));
    });
  }

  async evaluate(expression) {
    const reply = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (reply.result?.exceptionDetails) {
      throw new Error("evaluate: " + (reply.result.exceptionDetails.exception?.description ?? reply.result.exceptionDetails.text));
    }
    return reply.result?.result?.value;
  }

  async waitFor(expression, ms = 30000) {
    for (let t = 0; t < ms; t += 200) {
      try { if (await this.evaluate(expression)) return true; } catch { /* page not ready */ }
      await sleep(200);
    }
    return false;
  }

  // Quiet: nothing in flight and no DOM change for 800 ms.
  async settle(ms = 60000) {
    return this.waitFor("window.__vis && __vis.quiet()", ms);
  }

  // A wait the step cannot go on without.
  async need(expression, what, ms = 30000) {
    if (!(await this.waitFor(expression, ms))) throw new Error(`never came: ${what}`);
  }

  // Where the input goes: a point the browser hits on the element that
  // `target` evaluates to (`empty`: on the background of that SVG). No such
  // point means the view is not there, or is hidden or clipped: the step
  // fails instead of sending the event nowhere.
  async at(target, empty = false) {
    const p = await this.evaluate(empty ? `__vis.emptyPoint(${target})` : `__vis.point(${target})`);
    if (!p) throw new Error(`nothing visible ${empty ? "behind" : "at"} ${target}`);
    return p;
  }

  async mouse(type, at, extra = {}) {
    await this.send("Input.dispatchMouseEvent", { type, x: at.x, y: at.y, ...extra });
  }

  async click(target, { button = "left", modifiers = 0 } = {}) {
    const at = await this.at(target);
    await this.mouse("mouseMoved", at, { modifiers });
    await this.mouse("mousePressed", at, { button, buttons: button === "left" ? 1 : 2, clickCount: 1, modifiers });
    await this.mouse("mouseReleased", at, { button, buttons: 0, clickCount: 1, modifiers });
    return at;
  }

  async drag(target, dx, dy, empty = false) {
    return this.dragAt(await this.at(target, empty), dx, dy);
  }

  async dragAt(from, dx, dy) {
    await this.mouse("mouseMoved", from);
    await this.mouse("mousePressed", from, { button: "left", buttons: 1, clickCount: 1 });
    for (let i = 1; i <= 6; i++) {
      await this.mouse("mouseMoved", { x: from.x + (dx * i) / 6, y: from.y + (dy * i) / 6 }, { button: "left", buttons: 1 });
      await sleep(30);
    }
    await this.mouse("mouseReleased", { x: from.x + dx, y: from.y + dy }, { button: "left", buttons: 0, clickCount: 1 });
    return from;
  }

  async wheel(target, deltaY, empty = false) {
    const at = await this.at(target, empty);
    await this.mouse("mouseMoved", at);
    await this.send("Input.dispatchMouseEvent", { type: "mouseWheel", x: at.x, y: at.y, deltaX: 0, deltaY });
    return at;
  }

  // A fresh page: every phase of the scenario starts from the layout the
  // vis opens with, where the history graph has the whole window.
  async load(base) {
    this.loads++;
    await this.send("Page.navigate", { url: base + "/" });
    await this.need("!!window.__vis && __vis.historyNodes().length >= 2", "the history graph");
    await this.settle();
  }

  async type(text) {
    await this.send("Input.insertText", { text });
  }

  async close() {
    try { this.ws.close(); } catch { /* already closed */ }
    if (this.proc && this.proc.exitCode === null) {
      this.proc.kill();
      await new Promise((r) => { this.proc.once("exit", r); setTimeout(r, 5000); });
    }
  }
}

// --- the scenario --------------------------------------------------------

// Each step acts, then the runner waits for `ready` and for the page to be
// quiet, and takes `measure`; `act` returns where its input went and what
// it saw before. The steps run in order on one page, in phases: a phase
// starts with `b.load`, because once a trial or a dataflow opens, the
// history pane keeps a fifth of the window and its context menu, or the
// database graph, no longer fits.
const BUTTON = (label) => `[...document.querySelectorAll('button')].find((x) => x.textContent.trim() === ${JSON.stringify(label)} && __vis.visible(x))`;
const HISTORY_G = "document.querySelector('g[id^=history-graph]')";
const TRIAL_G = "__vis.trialGraph()?.querySelector('g[id^=trial-graph]')";
const DATAFLOW_G = "document.querySelector('g.svg-pan-zoom_viewport')";
const PROSPECTIVE_SVG = "document.querySelector('.prospective-content svg')";
const TABLE = (name) => `[...document.querySelectorAll('svg g.node')].find((g) => g.querySelector('text')?.textContent === ${JSON.stringify(name)} && __vis.visible(g))`;
const SHIFT = 8; // the vis takes Ctrl, Shift or Alt; Ctrl+click is a right click on macOS

// A context-menu command on the first trial of the history graph.
async function menu(b, option) {
  const at = await b.click("__vis.historyNodes()[0]", { button: "right" });
  await b.need("document.getElementById('context-menu').classList.contains('show')", "the context menu", 5000);
  return { at, option: await b.click(`document.getElementById(${JSON.stringify(option)})`) };
}

const STEPS = [
  // The history graph.
  {
    name: "history",
    act: async (b, base) => { await b.load(base); return {}; },
    measure: "({ nodes: __vis.historyNodes().length, tabs: __vis.tabs(), rects: __vis.rects() })",
  },
  {
    name: "history-wheel-zoom",
    act: async (b) => ({ before: await b.evaluate(`__vis.transform(${HISTORY_G})`), at: await b.wheel(`${HISTORY_G}.ownerSVGElement`, -240, true) }),
    measure: `({ after: __vis.transform(${HISTORY_G}) })`,
  },
  {
    name: "history-drag",
    act: async (b) => ({ at: await b.drag(`${HISTORY_G}.ownerSVGElement`, 60, 40, true) }),
    measure: `({ after: __vis.transform(${HISTORY_G}) })`,
  },
  // A trial, its tabs, and the diff of the two trials.
  {
    name: "trial",
    act: async (b, base) => { await b.load(base); return { at: await b.click("__vis.historyNodes()[0]") }; },
    ready: "!!__vis.trialGraph() && __vis.tabs().some((t) => t.endsWith('- Information'))",
    measure: "({ tabs: __vis.tabs(), nodes: __vis.trialGraph().querySelectorAll('g.node').length, rects: __vis.rects() })",
  },
  {
    name: "trial-wheel-zoom",
    act: async (b) => ({ before: await b.evaluate(`__vis.transform(${TRIAL_G})`), at: await b.wheel("__vis.trialGraph()", -240, true) }),
    measure: `({ after: __vis.transform(${TRIAL_G}) })`,
  },
  {
    name: "trial-drag",
    act: async (b) => ({ at: await b.drag("__vis.trialGraph()", 60, 40, true) }),
    measure: `({ after: __vis.transform(${TRIAL_G}) })`,
  },
  {
    name: "trial-node-click",
    act: async (b) => ({
      before: await b.evaluate("__vis.trialGraph().querySelectorAll('g.node').length"),
      at: await b.click("__vis.trialGraph().querySelector('g.node rect')"),
    }),
    measure: "({ after: __vis.trialGraph().querySelectorAll('g.node').length })",
  },
  {
    name: "trial-info-fold",
    act: async (b) => ({ at: await b.click("[...document.querySelectorAll('.fold span')].find(__vis.visible)") }),
    measure: "({ folds: [...document.querySelectorAll('.fold i')].map((i) => i.className) })",
  },
  {
    name: "diff",
    act: async (b) => ({ at: await b.click("__vis.historyNodes()[1]", { modifiers: SHIFT }) }),
    ready: "__vis.tabs().some((t) => t.includes('Diff Info')) && __vis.tabs().some((t) => t.startsWith('*Diff '))",
    measure: "({ tabs: __vis.tabs(), rects: __vis.rects() })",
  },
  {
    name: "split-drag",
    act: async (b) => ({
      before: await b.evaluate("__vis.rects()"),
      at: await b.drag("[...document.querySelectorAll('.lm-DockPanel-handle')].find((h) => __vis.point(h))", 0, 60),
    }),
    measure: "({ after: __vis.rects() })",
  },
  {
    name: "close-tab",
    act: async (b) => ({ at: await b.click("[...document.querySelectorAll('.lm-TabBar-tab.lm-mod-current.lm-mod-closable .lm-TabBar-tabCloseIcon')].find((i) => __vis.point(i))") }),
    measure: "({ tabs: __vis.tabs(), rects: __vis.rects() })",
  },
  // The dataflow: svg-pan-zoom over the graph @viz-js draws.
  {
    name: "dataflow",
    act: async (b, base) => {
      await b.load(base);
      const opened = await menu(b, "dataflow-option");
      await b.need(`!!${BUTTON("Generate dataflow")}`, "the dataflow form");
      return { ...opened, generate: await b.click(BUTTON("Generate dataflow")) };
    },
    ready: `!!${DATAFLOW_G}`,
    timeout: 90000,
    measure: `({ tabs: __vis.tabs(), transform: __vis.transform(${DATAFLOW_G}), nodes: ${DATAFLOW_G}.querySelectorAll('g.node').length })`,
  },
  {
    name: "dataflow-wheel-zoom",
    act: async (b) => ({ at: await b.wheel(`${DATAFLOW_G}.ownerSVGElement`, -240) }),
    measure: `({ after: __vis.transform(${DATAFLOW_G}) })`,
  },
  {
    // The SVG is drawn at its natural size, several times the window, and
    // the box nodes (a polygon: the only selectable ones) may all be out of
    // view. Drag the background, as a user would, until the box nearest to
    // the visible part is in it.
    name: "dataflow-drag",
    act: async (b) => {
      const box = await b.evaluate(`__vis.nearest(__vis.dataflowBoxes(), ${DATAFLOW_G}.ownerSVGElement).id`);
      const target = `document.getElementById(${JSON.stringify(box)})`;
      const drags = [];
      for (let i = 0; i < 8 && !(await b.evaluate(`__vis.point(${target})`)); i++) {
        drags.push(await b.evaluate(`__vis.towards(${target}, ${DATAFLOW_G}.ownerSVGElement)`));
        const d = drags[drags.length - 1];
        await b.dragAt(d, d.dx, d.dy);
        await b.settle();
      }
      return { box, drags };
    },
    measure: `({ after: __vis.transform(${DATAFLOW_G}) })`,
  },
  {
    name: "dataflow-node-click",
    act: async (b) => ({ at: await b.click(`[...${DATAFLOW_G}.querySelectorAll('g.node')].find((g) => g.children[1]?.tagName === 'polygon' && __vis.point(g))`) }),
    measure: `({ red: ${DATAFLOW_G}.querySelectorAll('g.node > polygon[stroke=red]').length })`,
  },
  // The prospective graph: its own zoom buttons and pan.
  {
    name: "prospective",
    act: async (b, base) => { await b.load(base); return menu(b, "prospective-option"); },
    ready: `!!${PROSPECTIVE_SVG}`,
    timeout: 60000,
    measure: `({ tabs: __vis.tabs(), viewBox: ${PROSPECTIVE_SVG}.getAttribute('viewBox') })`,
  },
  {
    name: "prospective-zoom-in",
    act: async (b) => ({ at: await b.click("[...document.querySelectorAll('.prospective-toolbar a[title=\"Zoom In\"]')].find(__vis.visible)") }),
    measure: `({ viewBox: ${PROSPECTIVE_SVG}.getAttribute('viewBox') })`,
  },
  {
    name: "prospective-drag",
    act: async (b) => ({ at: await b.drag(PROSPECTIVE_SVG, 50, 30) }),
    measure: `({ viewBox: ${PROSPECTIVE_SVG}.getAttribute('viewBox') })`,
  },
  // The Prolog export and a query run by tau-prolog in the page.
  {
    name: "prolog",
    act: async (b, base) => {
      await b.load(base);
      const opened = await menu(b, "export-option");
      await b.need(`!!${BUTTON("Generate prolog")}`, "the prolog form");
      return { ...opened, generate: await b.click(BUTTON("Generate prolog")) };
    },
    ready: "!!document.querySelector('textarea[id^=exportPrologProgram]')?.value",
    timeout: 60000,
    measure: "({ tabs: __vis.tabs(), program: document.querySelector('textarea[id^=exportPrologProgram]').value.length })",
  },
  {
    name: "prolog-query",
    act: async (b) => {
      const at = await b.click("document.querySelector('textarea[id^=exportPrologQuery]')");
      await b.type("current_predicate(N/A).");
      return { at, execute: await b.click(BUTTON("Execute Query")) };
    },
    ready: "!!document.querySelector('[id^=\"Answers prolog card text\"]')",
    measure: "({ answers: document.querySelector('[id^=\"Answers prolog card text\"]').innerHTML.split('<br>').length - 1 })",
  },
  // The main tabs, the database graph and the SQL editor (ace).
  {
    name: "tabs",
    act: async (b, base) => {
      await b.load(base);
      const seen = [];
      for (const label of ["Config", "Annotation", "History"]) {
        await b.click(`__vis.tab(${JSON.stringify(label)})`);
        await b.settle();
        seen.push(await b.evaluate("__vis.tabs().filter((t) => t.startsWith('*'))"));
      }
      return { seen };
    },
  },
  {
    name: "database",
    act: async (b) => ({ at: await b.click("__vis.tab('Database')") }),
    ready: "[...document.querySelectorAll('svg g.node circle')].some(__vis.visible)",
    measure: "({ tables: [...document.querySelectorAll('svg g.node circle')].filter(__vis.visible).length })",
  },
  {
    name: "database-table",
    act: async (b) => ({ at: await b.click(`${TABLE("trial")}.querySelector('circle')`) }),
    ready: "__vis.tabs().some((t) => t.replace('*', '') === 'trial')",
    measure: "({ tabs: __vis.tabs() })",
  },
  {
    name: "query-editor",
    act: async (b) => {
      await b.click("__vis.tab('Database')");
      await b.settle();
      return { at: await b.click("document.getElementById('new-query-btn')") };
    },
    ready: "[...document.querySelectorAll('.ace_editor')].some(__vis.visible)",
    measure: "({ tabs: __vis.tabs() })",
  },
  {
    name: "query-run",
    act: async (b) => {
      // Typed into ace's own input: ace handles the keystrokes.
      await b.evaluate("(() => { const ed = window.ace.edit([...document.querySelectorAll('.ace_editor')].find(__vis.visible)); ed.selectAll(); ed.focus(); return true; })()");
      await b.type("SELECT COUNT(*) AS trials FROM trial;");
      const text = await b.evaluate("window.ace.edit([...document.querySelectorAll('.ace_editor')].find(__vis.visible)).getValue()");
      return { text, execute: await b.click("[...document.querySelectorAll('button')].find((x) => x.textContent.includes('Execute Query') && __vis.visible(x))") };
    },
    ready: "__vis.tabs().some((t) => t.includes('Query Result ('))",
    measure: "({ tabs: __vis.tabs() })",
  },
  // Dragging a table restarts d3-force's simulation, whose ticks follow the
  // clock: where the node stops changes from run to run (the snapshot masks
  // the graph's coordinates), so the measure is only whether it moved.
  {
    name: "database-drag",
    timed: true,
    act: async (b, base) => {
      await b.load(base);
      await b.click("__vis.tab('Database')");
      await b.need(`!!${TABLE("trial")}`, "the database graph");
      await b.settle();
      const before = await b.evaluate(`${TABLE("trial")}.getAttribute('transform')`);
      return { before, at: await b.drag(`${TABLE("trial")}.querySelector('circle')`, 40, 25) };
    },
    measure: `({ after: ${TABLE("trial")}.getAttribute('transform') })`,
  },
];

// --- masking and comparing -----------------------------------------------

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;

// Trial ids are the store's and stay. Any other UUID (lumino's widget ids)
// is numbered by first appearance; the five characters makeid() appends to
// a widget id are masked, and so is the clock in svg-pan-zoom's viewport
// id; long decimals are cut to three places.
function mask(text, trials) {
  const seen = new Map();
  return text
    .replace(/viewport-\d+/g, "viewport-<time>")
    .replace(UUID, (u) => {
      if (trials.has(u)) return u;
      if (!seen.has(u)) seen.set(u, `<uuid-${seen.size + 1}>`);
      return seen.get(u);
    })
    .replace(/([0-9a-f]{12}|<uuid-\d+>)([A-Za-z0-9]{5})(?![A-Za-z0-9])/g, "$1<id>")
    .replace(/(-?\d+\.\d{3})\d+/g, "$1");
}

function changedLines(a, b) {
  const result = spawnSync("diff", ["-U0", a, b], { encoding: "utf8", maxBuffer: 1 << 30 });
  if (result.status === 0) return { lines: [], text: "" };
  return {
    text: result.stdout,
    lines: result.stdout.split("\n").filter((l) => /^[-+]/.test(l) && !/^(---|\+\+\+) /.test(l)),
  };
}

function minus(changes, noise) {
  const counts = new Map();
  for (const l of noise) counts.set(l, (counts.get(l) || 0) + 1);
  return changes.filter((l) => {
    const n = counts.get(l) || 0;
    if (n === 0) return true;
    counts.set(l, n - 1);
    return false;
  });
}

// --- main ----------------------------------------------------------------

async function runScenario(label, bundle, chrome, base, out, trials) {
  const dir = path.join(out, label);
  fs.mkdirSync(dir);
  const browser = new Browser(chrome, path.join(out, "profiles", label));
  const steps = [];
  try {
    await browser.start(bundle);
    for (const [index, step] of STEPS.entries()) {
      const stem = `${String(index + 1).padStart(2, "0")}-${step.name}`;
      browser.events = [];
      const record = { step: stem };
      try {
        record.act = await step.act(browser, base);
        // Quiet counts from the end of the input: a wheel event can still be
        // on its way when the page has not changed for a while.
        await browser.evaluate("(__vis.touch(), true)");
        record.ready = step.ready ? await browser.waitFor(step.ready, step.timeout ?? 30000) : true;
        record.quiet = await browser.settle();
        if (step.measure) record.measure = await browser.evaluate(step.measure).catch((e) => `error: ${e.message}`);
        for (const id of await browser.evaluate("__vis.historyNodes().map((r) => r.parentNode.getAttribute('attr-trialid'))")) trials.add(id);
        fs.writeFileSync(path.join(dir, `${stem}.dom.txt`), mask(await browser.evaluate("__vis.snapshot()"), trials) + "\n");
      } catch (e) {
        record.error = e.message;
      }
      record.events = browser.events.map((e) => mask(e, trials));
      steps.push(record);
      console.log(`${label} ${stem}: ready=${record.ready} quiet=${record.quiet}${record.error ? " error=" + record.error : ""}`);
    }
  } finally {
    await browser.close();
  }
  const swaps = { loads: browser.loads, bundleServed: browser.bundleServed };
  fs.writeFileSync(path.join(dir, "steps.json"), JSON.stringify({ ...swaps, steps }, null, 1) + "\n");
  return { steps, ...swaps };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const root = path.resolve(args.positional[0]);
  const out = path.resolve(args.positional[1]);
  const project = path.join(root, "project");
  if (!fs.existsSync(path.join(project, ".noworkflow"))) fail(`${project} holds no .noworkflow`);
  if (fs.existsSync(out)) fail(`${out} already exists`);
  const now = path.resolve(args.now ?? path.join(REPO, ".venv", "bin", "now"));
  if (!fs.existsSync(now)) fail(`no now at ${now}`);
  const chrome = findChrome(args.chrome);
  if (!chrome) fail("no Chrome or Chromium found: pass --chrome or set CHROME");
  fs.mkdirSync(out, { recursive: true });

  const bundles = {};
  if (args.base) bundles.base = path.resolve(args.base);
  else {
    bundles.base = path.join(out, "bundle.base.js");
    fs.writeFileSync(bundles.base, execFileSync("git", ["-C", REPO, "show", `HEAD:${BUNDLE}`], { maxBuffer: 1 << 30 }));
  }
  bundles.new = path.resolve(args.new ?? path.join(REPO, BUNDLE));
  const sha1 = (f) => createHash("sha1").update(fs.readFileSync(f)).digest("hex");
  const header = [
    `base    ${sha1(bundles.base)}  ${args.base ? bundles.base : "HEAD:" + BUNDLE}`,
    `new     ${sha1(bundles.new)}  ${bundles.new}`,
    `now     ${now}`,
    `chrome  ${execFileSync(chrome, ["--version"], { encoding: "utf8" }).trim()}`,
  ];
  console.log(header.join("\n"));
  if (sha1(bundles.base) === sha1(bundles.new)) console.log("note: base and new are the same file; the run is a control of the scenario");

  const port = args.port ? Number(args.port) : await freePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  if (await answers(baseUrl + "/")) fail(`port ${port} already answers; pick another`);
  const log = fs.openSync(path.join(out, "server.log"), "w");
  // From inside the project: the /commands/* routes run `now` without --dir.
  const server = spawn(now, ["vis", "-p", String(port), "--dir", project], {
    cwd: project, env: harnessEnv(root, now), stdio: ["ignore", log, log], detached: process.platform !== "win32",
  });
  const stop = () => {
    if (server.exitCode !== null) return;
    try { process.platform === "win32" ? server.kill() : process.kill(-server.pid); } catch { /* gone */ }
  };
  process.on("exit", stop);
  let up = false;
  for (let i = 0; i < 300 && !up && server.exitCode === null; i++) {
    up = (await answers(baseUrl + "/")) === 200;
    if (!up) await sleep(200);
  }
  if (!up) fail(`the vis server did not answer on ${baseUrl}; see ${path.join(out, "server.log")}`);

  const trials = new Set();
  const runs = {};
  const only = args.runs ? args.runs.split(",") : null;
  try {
    for (const [label, bundle] of [["base", bundles.base], ["control", bundles.base], ["new", bundles.new]]) {
      if (!only || only.includes(label)) runs[label] = await runScenario(label, bundle, chrome, baseUrl, out, trials);
    }
  } finally {
    stop();
  }
  if (only) {
    console.log(`\n--runs ${args.runs}: no comparison; read ${out}/<run>/steps.json`);
    process.exit(Object.values(runs).some((r) => r.steps.some((s) => s.error || s.ready === false)) ? 2 : 0);
  }

  // The report.
  fs.mkdirSync(path.join(out, "diff"));
  const lines = [...header, ""];
  let differs = false;
  let broken = false;
  for (const label of Object.keys(runs)) {
    if (runs[label].bundleServed !== runs[label].loads) {
      lines.push(`${label}: the bundle was swapped ${runs[label].bundleServed} times in ${runs[label].loads} page loads`);
      broken = true;
    }
  }
  lines.push(["step".padEnd(24), "dom".padEnd(18), "measures".padEnd(10), "events"].join(" "));
  for (const [index, step] of STEPS.entries()) {
    const stem = `${String(index + 1).padStart(2, "0")}-${step.name}`;
    const [b, c, n] = ["base", "control", "new"].map((l) => runs[l].steps[index]);
    const file = (l) => path.join(out, l, `${stem}.dom.txt`);
    let dom;
    if (!fs.existsSync(file("base"))) dom = "no base snapshot";
    else if (!fs.existsSync(file("new"))) dom = "NO NEW SNAPSHOT";
    else {
      const noise = fs.existsSync(file("control")) ? changedLines(file("base"), file("control")).lines : [];
      const change = changedLines(file("base"), file("new"));
      const left = minus(change.lines, noise);
      if (change.lines.length) fs.writeFileSync(path.join(out, "diff", `${stem}.diff`), change.text);
      if (left.length) dom = `DIFF ${left.length} lines`;
      else dom = noise.length ? `same (noise ${noise.length})` : "same";
    }
    const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);
    const facts = (r) => {
      const f = { ready: r.ready, act: r.act, measure: r.measure, error: r.error };
      // Where a timed simulation stops is not compared, only whether it moved.
      if (step.timed) return { ready: r.ready, error: r.error, at: r.act?.at, moved: !!r.measure && r.measure.after !== r.act?.before };
      return f;
    };
    let measures = same(facts(b), facts(n)) ? "same" : same(facts(b), facts(c)) ? "DIFF" : "noise";
    const events = same(b.events, n.events) ? "same" : same(b.events, c.events) ? "DIFF" : "noise";
    if (b.ready === false || b.error) {
      measures = "BASE FAILED";
      broken = true;
    }
    if (dom.startsWith("DIFF") || dom.startsWith("NO") || measures === "DIFF" || events === "DIFF") differs = true;
    lines.push([stem.padEnd(24), dom.padEnd(18), measures.padEnd(10), events].join(" "));
    if (measures !== "same") lines.push(`    base: ${JSON.stringify(facts(b))}`, `    new:  ${JSON.stringify(facts(n))}`);
    if (events !== "same") lines.push(`    base: ${JSON.stringify(b.events)}`, `    new:  ${JSON.stringify(n.events)}`);
  }
  lines.push("", broken ? "the comparison failed: see BASE FAILED above" : differs ? "new differs from base" : "no difference beyond the control");
  fs.writeFileSync(path.join(out, "report.txt"), lines.join("\n") + "\n");
  console.log("\n" + lines.join("\n"));
  process.exit(broken ? 2 : differs ? 1 : 0);
}

main().catch((e) => fail(e.stack || e.message));
