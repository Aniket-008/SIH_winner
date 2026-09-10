/**
 * Browser-less UI smoke test for the JAN-DRISHTI AI website.
 *
 * Loads the real website/index.html + website/app.js into jsdom, talks to a
 * REAL running server (default http://127.0.0.1:8000) and walks the officer
 * journey that matters for the scalability work:
 *
 *   login -> live fleet dashboard -> traffic-policy change -> preset profile
 *         -> in-app load test -> read-only role checks (viewer)
 *
 * Usage:
 *   python scripts/start_cluster.py --nodes 3 --base-port 8000 &
 *   npm install jsdom --no-save          # once, in this directory
 *   node tests/ui_smoke.mjs              # or BASE_URL=http://host:port node tests/ui_smoke.mjs
 *
 * Exits non-zero if any assertion fails or the page logs a runtime error.
 * jsdom does not implement scrollIntoView/canvas, which this harness stubs out;
 * use a real browser for anything visual.
 */
// Headless UI test: load the real page against the live server, log in,
// exercise the scalability dashboard and report any runtime errors.
import { JSDOM } from "jsdom";
import fs from "node:fs";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const html = fs.readFileSync(new URL("../website/index.html", import.meta.url), "utf8");
const appjs = fs.readFileSync(new URL("../website/app.js", import.meta.url), "utf8");

const errors = [];
const dom = new JSDOM(html, {
  url: BASE + "/",
  runScripts: "outside-only",
  pretendToBeVisual: true,
});
const { window } = dom;
window.addEventListener("error", (e) => errors.push("window error: " + e.message));
const origError = console.error;
console.error = (...args) => { errors.push("console.error: " + args.join(" ")); };

// Real network fetch (Node 22 has global fetch); make it same-origin aware.
window.fetch = (url, opts) => fetch(new URL(url, BASE).toString(), opts);
window.FormData = FormData;
// jsdom provides its own localStorage; nothing to stub.

// jsdom lacks canvas 2D; give the chart a recording stub so we can assert it drew.
const drawCalls = [];
const ctxStub = new Proxy({}, {
  get(_t, prop) {
    if (prop === "setTransform" || prop === "measureText") return () => ({ width: 10 });
    if (prop === "canvas") return null;
    return (...args) => { drawCalls.push(String(prop)); };
  },
  set() { return true; },
});
window.HTMLCanvasElement.prototype.getContext = () => ctxStub;
// jsdom has no layout engine; scrollIntoView is a no-op in tests.
window.Element.prototype.scrollIntoView = () => {};

try {
  window.eval(appjs);
} catch (e) {
  errors.push("app.js threw: " + e.stack);
}

const $ = (id) => window.document.getElementById(id);
function assert(cond, msg) { console.log((cond ? "PASS " : "FAIL ") + msg); if (!cond) errors.push(msg); }

// ---- login flow -------------------------------------------------------------
$("username").value = "admin";
$("password").value = "admin123";
$("loginForm").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
await new Promise((r) => setTimeout(r, 1500));

assert(!$("mainApp").hidden, "login reveals the main app");
assert($("userInfo").textContent.includes("admin"), "user badge shows the admin account");

// ---- scalability dashboard --------------------------------------------------
await window.loadScalability(true);
await new Promise((r) => setTimeout(r, 500));

const summaryHtml = $("scalSummary").innerHTML;
assert(summaryHtml.includes("Replicas healthy"), "summary cards rendered");
assert(summaryHtml.includes("Fleet throughput"), "throughput card rendered");
assert(summaryHtml.includes("Cache hit ratio"), "cache card rendered");
assert(/2 \/ 2|3 \/ 3|1 \/ 1/.test(summaryHtml), "replica health card shows a healthy count");

const nodesHtml = $("scalNodes").innerHTML;
assert(nodesHtml.includes("node-1") || nodesHtml.includes("node-"), "replica table lists nodes");
assert(nodesHtml.includes("share-fill"), "traffic-share bars rendered");
assert(nodesHtml.includes("this node"), "own replica is marked");

assert(drawCalls.length > 20, `fleet chart drew (${drawCalls.length} canvas ops)`);
assert($("scalChartLegend").innerHTML.includes("requests/s"), "chart legend rendered");
assert($("scalRecommendation").innerHTML.length > 40, "autoscaler recommendation rendered");
assert($("scalEnforcement").innerHTML.includes("Load balancer"), "enforcement chain rendered");
assert($("scalRequests").innerHTML.includes("status-chip"), "live request feed rendered");
assert($("scalEvents").innerHTML.length > 10, "ops event log rendered");
assert($("policyRps").value !== "", "traffic policy form populated");
assert($("policyRoleBadge").textContent.includes("admin"), "admin sees editable policy badge");
assert($("scalLbBadge").textContent.length > 2, "balancer badge populated");

// ---- traffic policy change --------------------------------------------------
$("policyRps").value = "42";
$("applyPolicyBtn").dispatchEvent(new window.Event("click", { bubbles: true }));
await new Promise((r) => setTimeout(r, 900));
assert($("policyFeedback").innerHTML.includes("rate_limit_rps=42"), "policy change reported back to the officer");

// ---- preset profile ---------------------------------------------------------
window.document.querySelector('.chip-button[data-preset="state"]').dispatchEvent(new window.Event("click", { bubbles: true }));
await new Promise((r) => setTimeout(r, 900));
assert($("policyFeedback").innerHTML.includes("State scale"), "preset profile applied and confirmed");

// ---- load test --------------------------------------------------------------
$("ltDuration").value = "2";
$("ltConcurrency").value = "4";
$("ltPath").value = "/health";
$("runLoadTestBtn").dispatchEvent(new window.Event("click", { bubbles: true }));
await new Promise((r) => setTimeout(r, 9000));
const ltHtml = $("ltResult").innerHTML;
assert(ltHtml.includes("Throughput"), "load test result rendered");
assert(/req\/s/.test(ltHtml), "load test reports throughput");
assert(ltHtml.includes("Traffic distribution across replicas"), "load test reports replica distribution");

// ---- restore demo policy ---------------------------------------------------
window.document.querySelector('.chip-button[data-preset="demo"]').dispatchEvent(new window.Event("click", { bubbles: true }));
await new Promise((r) => setTimeout(r, 800));

// ---- read-only role (viewer) -----------------------------------------------
const dom2 = new JSDOM(html, { url: BASE + "/", runScripts: "outside-only", pretendToBeVisual: true });
const w2 = dom2.window;
w2.fetch = (url, opts) => fetch(new URL(url, BASE).toString(), opts);
w2.HTMLCanvasElement.prototype.getContext = () => ctxStub;
w2.Element.prototype.scrollIntoView = () => {};
try { w2.eval(appjs); } catch (e) { errors.push("viewer app.js threw: " + e.stack); }
const $2 = (id) => w2.document.getElementById(id);
$2("username").value = "viewer";
$2("password").value = "viewer123";
$2("loginForm").dispatchEvent(new w2.Event("submit", { bubbles: true, cancelable: true }));
await new Promise((r) => setTimeout(r, 1500));
await w2.loadScalability(true);
await new Promise((r) => setTimeout(r, 400));
assert($2("mainApp").hidden === false, "viewer can log in");
assert($2("policyRoleBadge").textContent.includes("read-only"), "viewer sees the read-only badge");
assert($2("applyPolicyBtn").disabled === true, "viewer cannot apply traffic policy");
assert($2("runLoadTestBtn").disabled === true, "viewer cannot run load tests");
assert($2("scalSummary").innerHTML.includes("Fleet throughput"), "viewer still sees live telemetry");
$2("runLoadTestBtn").dispatchEvent(new w2.Event("click", { bubbles: true }));
await new Promise((r) => setTimeout(r, 300));
assert($2("ltResult").innerHTML.includes("administrators"), "viewer attempting a load test is told why it is blocked");

console.log("\n--- runtime errors ---");
console.log(errors.length ? errors.join("\n") : "NONE");
process.exit(errors.length ? 1 : 0);
