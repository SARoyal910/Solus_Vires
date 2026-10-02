// Notes export and the safety-plan layout (P2-E3, P2-E8).
//
// Everything here works on notes that are already decrypted in memory. It
// makes no network requests of any kind: it only builds text and DOM. The
// export is therefore readable plaintext, and the page says so before anyone
// prints or downloads it. tests/web/export.test.mjs holds it to that.
(function () {
  "use strict";

  // The fillable version of the Safety Planning page (safety.html), section
  // by section. Keys are stored inside the encrypted plan; labels can change.
  const PLAN = [
    {
      title: "Staying safer right now",
      fields: [
        { key: "safer_spots", label: "Safer places at home (a way out, no weapons)" },
        { key: "code_word", label: "My code word, and who knows what it means", short: true },
        { key: "people", label: "People I can call or go to (names and numbers)" },
        { key: "way_out", label: "How I'd leave in a hurry (door, keys, where to go)" },
      ],
    },
    {
      title: "Getting ready",
      fields: [
        { key: "where_to_go", label: "Where I could go (a friend, family, a shelter)" },
        { key: "money", label: "Money I can set aside, and where" },
        { key: "go_bag", label: "Where my go-bag is kept", short: true },
      ],
    },
    {
      title: "Documents and essentials",
      checklist: [
        { key: "id", label: "ID or driver's license, passports, birth certificates" },
        { key: "ssn", label: "Social Security cards" },
        { key: "immigration", label: "Green cards, visas, and other immigration papers" },
        { key: "health", label: "Health insurance cards and medical records" },
        { key: "housing", label: "Marriage license, lease or deed" },
        { key: "court", label: "Court orders (protective orders, custody orders)" },
        { key: "children_records", label: "Children's school and medical records" },
        { key: "meds", label: "Medications and prescriptions" },
        { key: "money_cards", label: "Cash, bank cards, checkbook" },
        { key: "keys", label: "Keys: house, car, work" },
        { key: "phone", label: "Phone and charger" },
        { key: "clothes", label: "A change of clothes" },
        { key: "numbers", label: "A list of important numbers" },
      ],
      fields: [{ key: "documents_notes", label: "Notes on documents (copies, where they are)" }],
    },
    {
      title: "Phones and accounts",
      fields: [{ key: "phone_accounts", label: "Shared plans, accounts, and location settings to deal with, and when" }],
    },
    {
      title: "Children",
      fields: [{ key: "children", label: "Their safe place, their code word, who may pick them up" }],
    },
    {
      title: "Pets",
      fields: [{ key: "pets", label: "Who could care for them; records and supplies to take" }],
    },
    {
      title: "After leaving",
      fields: [{ key: "after", label: "Locks, routines, and who to tell" }],
    },
    {
      title: "Anything else",
      fields: [{ key: "other", label: "Other notes" }],
    },
  ];

  const pad = (n) => String(n).padStart(2, "0");

  // "September 1, 2026" from "2026-09-01" (the date the writer chose).
  function longDate(isoDay) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDay || "");
    if (!m) return "Undated";
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
  }

  // "2026-09-02 14:05" in this device's local time, from a timestamp.
  function localStamp(value) {
    if (!value) return "";
    const s = String(value);
    const d = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(s) || !/T/.test(s) ? s : s + "Z");
    if (Number.isNaN(d.getTime())) return s;
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function formatSize(bytes) {
    if (!bytes && bytes !== 0) return "";
    return bytes >= 1024 * 1024 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  function planHasContent(plan) {
    if (!plan) return false;
    const fields = plan.fields || {};
    const checks = plan.checklist || {};
    return Object.values(fields).some((v) => String(v || "").trim()) || Object.values(checks).some(Boolean);
  }

  // Input: decrypted data. entries: [{ entry_date, text, created_at, photos }],
  // photos: [{ name, type, width, height, taken, size, created_at, url }].
  // Output: a plain description of the document, oldest entry first.
  function buildModel({ profile, plan, entries, exportedAt }) {
    const sorted = [...(entries || [])]
      .filter((e) => e && !e.unreadable)
      .sort((a, b) => (a.entry_date || "").localeCompare(b.entry_date || "") || String(a.created_at || "").localeCompare(String(b.created_at || "")));
    const unreadable = (entries || []).filter((e) => e && e.unreadable).length;
    return {
      exportedAt: exportedAt || new Date(),
      profile: profile && (profile.name || profile.relationship || profile.notes) ? profile : null,
      plan: planHasContent(plan) ? plan : null,
      entries: sorted.map((e, i) => ({
        number: i + 1,
        date: longDate(e.entry_date),
        isoDate: e.entry_date || "",
        saved: localStamp(e.created_at),
        text: e.text || "",
        photos: (e.photos || []).map((p) => ({
          name: p.name || "photo",
          taken: p.taken ? p.taken.replace("T", " ").slice(0, 16) : "",
          added: localStamp(p.created_at),
          details: [p.width && p.height ? `${p.width}×${p.height}` : "", formatSize(p.size)].filter(Boolean).join(", "),
          url: p.url || "",
        })),
      })),
      unreadable,
    };
  }

  const HEADER_NOTE =
    "Exported from private notes kept on Solus Vires. The notes were decrypted on this device to make this copy. " +
    "Each entry shows the date its writer gave it and when it was first saved. Photos were stripped of hidden data " +
    "(such as location) before they were stored; a photo's \"taken\" time comes from the camera, if it recorded one.";

  function planLines(plan) {
    const lines = [];
    for (const section of PLAN) {
      const body = [];
      for (const item of section.checklist || []) {
        if (plan.checklist && plan.checklist[item.key]) body.push(`  [x] ${item.label}`);
      }
      for (const field of section.fields || []) {
        const value = String((plan.fields || {})[field.key] || "").trim();
        if (value) body.push(`  ${field.label}:`, ...value.split("\n").map((l) => `    ${l}`));
      }
      if (body.length) lines.push(section.title, ...body, "");
    }
    return lines;
  }

  function toText(model) {
    const out = [
      "NOTES EXPORT",
      `Exported: ${localStamp(model.exportedAt.toISOString())} (this device's time)`,
      `Entries: ${model.entries.length}`,
      "",
      HEADER_NOTE,
      "",
    ];
    if (model.unreadable) out.push(`${model.unreadable} entr${model.unreadable === 1 ? "y" : "ies"} could not be read with this PIN and are not included.`, "");
    if (model.profile) {
      out.push("PRIVATE PROFILE", "---------------");
      if (model.profile.name) out.push(`Name or names used: ${model.profile.name}`);
      if (model.profile.relationship) out.push(`Relationship: ${model.profile.relationship}`);
      if (model.profile.notes) out.push("Notes:", ...model.profile.notes.split("\n").map((l) => `  ${l}`));
      out.push("");
    }
    if (model.plan) out.push("SAFETY PLAN", "-----------", ...planLines(model.plan));
    out.push("ENTRIES (oldest first)", "----------------------");
    if (!model.entries.length) out.push("No entries.");
    for (const e of model.entries) {
      out.push("", `${e.number}. ${e.date}${e.isoDate ? ` (${e.isoDate})` : ""}`, `   Saved: ${e.saved}`, "");
      out.push(...e.text.split("\n").map((l) => `   ${l}`));
      if (e.photos.length) {
        out.push("", `   Photos (${e.photos.length}, not included in this text file; use Print / Save as PDF):`);
        for (const p of e.photos) out.push(`   - ${p.name}${p.taken ? `, taken ${p.taken}` : ""}${p.added ? `, added ${p.added}` : ""}${p.details ? ` (${p.details})` : ""}`);
      }
    }
    out.push("", "End of export.");
    return out.join("\n") + "\n";
  }

  // Fills `container` with a printable version of the model. textContent
  // only, never innerHTML, so nothing in a note can become markup.
  function renderInto(container, model, doc) {
    const d = doc || document;
    const el = (tag, cls, text) => {
      const node = d.createElement(tag);
      if (cls) node.className = cls;
      if (text !== undefined) node.textContent = text;
      return node;
    };
    container.textContent = "";
    const head = el("div", "export-head"); // not <header>: that gets the site header styles
    head.append(el("h1", null, "Notes export"));
    head.append(el("p", "export-meta", `Exported ${localStamp(model.exportedAt.toISOString())} (this device's time) · ${model.entries.length} entr${model.entries.length === 1 ? "y" : "ies"}`));
    head.append(el("p", "export-note", HEADER_NOTE));
    if (model.unreadable) head.append(el("p", "export-note", `${model.unreadable} entr${model.unreadable === 1 ? "y" : "ies"} could not be read with this PIN and are not included.`));
    container.append(head);

    if (model.profile) {
      const s = el("section", "export-section");
      s.append(el("h2", null, "Private profile"));
      const dl = el("dl");
      for (const [label, value] of [["Name or names used", model.profile.name], ["Relationship", model.profile.relationship], ["Notes", model.profile.notes]]) {
        if (!value) continue;
        dl.append(el("dt", null, label), el("dd", null, value));
      }
      s.append(dl);
      container.append(s);
    }

    if (model.plan) {
      const s = el("section", "export-section");
      s.append(el("h2", null, "Safety plan"));
      for (const section of PLAN) {
        const checked = (section.checklist || []).filter((i) => model.plan.checklist && model.plan.checklist[i.key]);
        const filled = (section.fields || []).filter((f) => String((model.plan.fields || {})[f.key] || "").trim());
        if (!checked.length && !filled.length) continue;
        s.append(el("h3", null, section.title));
        if (checked.length) {
          const ul = el("ul", "export-checks");
          checked.forEach((i) => ul.append(el("li", null, i.label)));
          s.append(ul);
        }
        if (filled.length) {
          const dl = el("dl");
          filled.forEach((f) => dl.append(el("dt", null, f.label), el("dd", null, model.plan.fields[f.key])));
          s.append(dl);
        }
      }
      container.append(s);
    }

    const s = el("section", "export-section");
    s.append(el("h2", null, "Entries, oldest first"));
    if (!model.entries.length) s.append(el("p", null, "No entries."));
    for (const e of model.entries) {
      const art = el("article", "export-entry");
      art.append(el("h3", null, `${e.number}. ${e.date}`));
      art.append(el("p", "export-meta", `Date given: ${e.isoDate || "none"} · Saved: ${e.saved}`));
      art.append(el("p", "export-text", e.text));
      for (const p of e.photos) {
        const fig = el("figure", "export-photo");
        if (p.url) {
          const img = el("img");
          img.src = p.url;
          img.alt = p.name;
          fig.append(img);
        }
        fig.append(el("figcaption", null, [p.name, p.taken ? `taken ${p.taken}` : "", p.added ? `added ${p.added}` : "", p.details].filter(Boolean).join(" · ")));
        art.append(fig);
      }
      s.append(art);
    }
    container.append(s);
    container.append(el("p", "export-meta", "End of export."));
  }

  window.NotesExport = { PLAN, buildModel, toText, renderInto, longDate, localStamp, formatSize, planHasContent };
})();
