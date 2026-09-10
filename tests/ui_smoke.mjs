/**
 * Browser-less UI smoke test for the login & access analytics dashboard.
 *
 * Loads the real website/index.html + website/app.js into jsdom and drives them
 * against a RUNNING server (default http://127.0.0.1:8000):
 *
 *   static checks (favicon, brand icon, nav link) -> admin login -> dashboard
 *   cards, per-day chart, recent feed, user table -> range switch -> refresh
 *   -> viewer login (aggregates visible, client IPs withheld)
 *
 * Usage:
 *   python -m jan_drishti.server --host 127.0.0.1 --port 8000 &
 *   npm install jsdom --no-save
 *   node tests/ui_smoke.mjs          # or BASE_URL=http://host:port node tests/ui_smoke.mjs
 *
 * Exits non-zero if any assertion fails or the page logs a runtime error.
 */
import { JSDOM } from "jsdom";
import fs from "node:fs";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const html = fs.readFileSync(new URL("../website/index.html", import.meta.url), "latin1");
const appjs = fs.readFileSync(new URL("../website/app.js", import.meta.url), "utf8");
const errors = [];
const results = [];
const assert = (cond, msg) => { results.push((cond ? "PASS " : "FAIL ") + msg); if (!cond) errors.push(msg); };

// --- static wiring checks ----------------------------------------------------
const dom0 = new JSDOM(html);
const d0 = dom0.window.document;
assert(!!d0.querySelector('link[rel="icon"][href="favicon.svg"]'), "favicon <link rel=icon> present in <head>");
assert(d0.querySelectorAll('img[src="favicon.svg"]').length >= 3, "brand marks use the app icon (login + header)");
assert(!!d0.getElementById("login-analytics"), "login analytics section exists");
assert(!!d0.getElementById("navAnalytics") && !!d0.getElementById("navAnalytics2"), "nav links to the analytics dashboard");

// --- live behaviour ---------------------------------------------------------
function boot() {
  const dom = new JSDOM(html, { url: BASE + "/", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window;
  w.addEventListener("error", (e) => errors.push("window error: " + e.message));
  w.fetch = (url, opts) => fetch(new URL(url, BASE).toString(), opts);
  w.Element.prototype.scrollIntoView = () => {};
  try { w.eval(appjs); } catch (e) { errors.push("app.js threw: " + e.stack); }
  return w;
}

const w = boot();
const $ = (id) => w.document.getElementById(id);
$("username").value = "admin";
$("password").value = "admin123";
$("loginForm").dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
await new Promise((r) => setTimeout(r, 2000));

assert(!$("mainApp").hidden, "admin login reveals the app");
const summary = $("analyticsSummary").innerHTML;
assert(summary.includes("Total sign-ins"), "card: total sign-ins");
assert(summary.includes("Unique users active"), "card: active users");
assert(summary.includes("Failed attempts"), "card: failed attempts");
assert(summary.includes("Sign-in success rate"), "card: success rate");
assert(summary.includes("Analysis activity"), "card: platform activity");
assert(/Total sign-ins<\/span>\s*<strong>\d+/.test(summary), "total sign-ins shows a number");

assert($("loginBars").innerHTML.includes("login-bar-col"), "per-day sign-in chart rendered");
assert(/login-bar-ok/.test($("loginBars").innerHTML), "successful sign-in bars rendered");
assert($("analyticsWindowBadge").textContent.length > 5, "window badge shows the date range");
assert($("recentLogins").innerHTML.includes("login-feed-item"), "recent sign-in feed rendered");
assert(/signed in|rejected/.test($("recentLogins").innerHTML), "feed marks outcome");
assert($("analyticsUsers").innerHTML.includes("role-admin") || $("analyticsUsers").innerHTML.includes("role-tag"), "user table rendered");
assert($("analyticsIpNote").textContent.includes("visible"), "admin sees the IP visibility note");
assert($("analyticsUpdated").textContent.includes("Updated"), "last-updated stamp shown");
assert($("analyticsNote").innerHTML.includes("How these numbers are counted"), "counting rules explained to the officer");

// range switch
$("analyticsRange").value = "7";
$("analyticsRange").dispatchEvent(new w.Event("change", { bubbles: true }));
await new Promise((r) => setTimeout(r, 1200));
assert($("loginBars").querySelectorAll(".login-bar-col").length === 7, "range selector re-renders the chart (7 days)");
$("analyticsRefreshBtn").dispatchEvent(new w.Event("click", { bubbles: true }));
await new Promise((r) => setTimeout(r, 1200));
assert($("analyticsSummary").innerHTML.includes("Total sign-ins"), "refresh button reloads the dashboard");

// viewer role: aggregates visible, IPs withheld
const w2 = boot();
const $2 = (id) => w2.document.getElementById(id);
$2("username").value = "viewer";
$2("password").value = "viewer123";
$2("loginForm").dispatchEvent(new w2.Event("submit", { bubbles: true, cancelable: true }));
await new Promise((r) => setTimeout(r, 2000));
assert(!$2("mainApp").hidden, "viewer login works");
assert($2("analyticsSummary").innerHTML.includes("Total sign-ins"), "viewer sees the analytics dashboard");
assert($2("analyticsIpNote").textContent.includes("hidden"), "viewer does not see client IPs");

const fails = results.filter((r) => r.startsWith("FAIL"));
console.log(results.join("\n"));
console.log("\nruntime errors: " + (errors.length ? "\n" + errors.join("\n") : "NONE"));
process.exit(fails.length || errors.length ? 1 : 0);
