// Notes export (P2-E3): built only from notes already decrypted in memory,
// with zero network calls. tests/browser/notes_vault.mjs repeats the
// zero-request check in a real browser, through the page's own buttons.
//   node --test tests/web/
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

globalThis.window = globalThis;
vm.runInThisContext(readFileSync(new URL("../../html/notes-export.js", import.meta.url), "utf8"));
const X = globalThis.NotesExport;

// Every way a page can talk to a server, replaced by a recorder.
const calls = [];
const record = (name) => function () { calls.push(name); throw new Error(`network call: ${name}`); };
globalThis.fetch = record("fetch");
globalThis.XMLHttpRequest = record("XMLHttpRequest");
globalThis.WebSocket = record("WebSocket");
globalThis.EventSource = record("EventSource");
globalThis.Image = record("Image");
Object.defineProperty(globalThis, "navigator", { value: { sendBeacon: record("sendBeacon") }, configurable: true });

// Just enough DOM for renderInto, which only uses createElement/textContent/append.
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ""; this.attrs = {}; }
  set textContent(v) { this.text = String(v); if (v === "") this.children = []; }
  get textContent() { return this.text + this.children.map((c) => (typeof c === "string" ? c : c.textContent)).join(" "); }
  append(...nodes) { this.children.push(...nodes); }
  set src(v) { if (/^https?:/.test(v)) calls.push("img-src " + v); this.attrs.src = v; }
  get src() { return this.attrs.src; }
}
const fakeDoc = { createElement: (tag) => new Node(tag) };

const data = {
  exportedAt: new Date("2026-10-02T14:05:00Z"),
  profile: { name: "J.", relationship: "ex-partner", notes: "" },
  plan: { fields: { code_word: "blue kettle", people: "Sam 555-0100" }, checklist: { id: true, meds: true, keys: false } },
  entries: [
    { entry_date: "2026-09-20", text: "Second thing.\nOn two lines.", created_at: "2026-09-21T09:00:00+00:00", photos: [{ name: "screenshot.png", taken: "2026-09-20T22:01:00", created_at: "2026-09-21T09:01:00+00:00", width: 1170, height: 2532, size: 812345, url: "blob:http://x/1" }] },
    { entry_date: "2026-09-01", text: "First thing.", created_at: "2026-09-02T08:00:00+00:00", photos: [] },
    { unreadable: true },
  ],
};

test("export is built with zero network calls", () => {
  calls.length = 0;
  const model = X.buildModel(data);
  X.toText(model);
  X.renderInto(new Node("div"), model, fakeDoc);
  assert.deepEqual(calls, []);
});

test("entries come out oldest first, dated in words and ISO, with saved times", () => {
  const text = X.toText(X.buildModel(data));
  assert.ok(text.indexOf("First thing.") < text.indexOf("Second thing."));
  assert.match(text, /1\. September 1, 2026 \(2026-09-01\)/);
  assert.match(text, /2\. September 20, 2026 \(2026-09-20\)/);
  assert.match(text, /Saved: 2026-09-0\d \d\d:\d\d/);
  assert.match(text, /Entries: 2/);
  assert.match(text, /1 entry could not be read with this PIN/);
});

test("export includes the profile, the filled-in safety plan, and photo details", () => {
  const text = X.toText(X.buildModel(data));
  assert.match(text, /Name or names used: J\./);
  assert.match(text, /SAFETY PLAN/);
  assert.match(text, /blue kettle/);
  assert.match(text, /\[x\] ID or driver's license/);
  assert.doesNotMatch(text, /\[x\] Keys/);
  assert.match(text, /screenshot\.png, taken 2026-09-20 22:01/);
  const box = new Node("div");
  X.renderInto(box, X.buildModel(data), fakeDoc);
  assert.match(box.textContent, /Safety plan/);
  assert.match(box.textContent, /screenshot\.png/);
});

test("an empty plan or profile is left out rather than printed blank", () => {
  const text = X.toText(X.buildModel({ ...data, profile: { name: "", relationship: "", notes: "" }, plan: { fields: { other: "  " }, checklist: {} } }));
  assert.doesNotMatch(text, /PRIVATE PROFILE/);
  assert.doesNotMatch(text, /SAFETY PLAN/);
});

test("note text is never turned into markup", () => {
  const box = new Node("div");
  X.renderInto(box, X.buildModel({ entries: [{ entry_date: "2026-09-01", text: "<img src=https://evil.example/x>", created_at: "2026-09-01T00:00:00Z" }] }), fakeDoc);
  assert.match(box.textContent, /<img src=https:\/\/evil\.example\/x>/);
  assert.deepEqual(calls.filter((c) => c.startsWith("img-src")), []);
});
