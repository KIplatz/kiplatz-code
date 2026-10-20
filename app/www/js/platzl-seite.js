// SPDX-License-Identifier: AGPL-3.0-or-later
import * as pl from "./platzl.js";
import * as verlauf from "./verlauf.js";

const $ = (s) => document.querySelector(s);
function el(tag, attrs = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "onclick") e.onclick = v; else if (k === "text") e.textContent = v; else if (k === "farbe") e.style.background = v;
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const k of kinder) if (k != null) e.append(k);
  return e;
}
const datum = (iso) => {
  const t = new Date(iso);
  if (isNaN(t)) return "";
  const tage = Math.floor((Date.now() - t) / 86400000);
  if (tage < 1) return t.toLocaleTimeString(kiplatzSprache.datumSprache(), { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Vienna" });
  if (tage < 7) return tage === 1 ? "gestern" : `vor ${tage} Tagen`;
  return t.toLocaleDateString(kiplatzSprache.datumSprache(), { day: "numeric", month: "numeric", year: "2-digit", timeZone: "Europe/Vienna" });
};

export function platzlSeite({ holen, geraet, status, skillVerwenden }) {
  const s = { kats: null, kat: null, stapel: [], warten: null, entwurf: null };
  const inhalt = () => $("#platzl-inhalt");
  const titel = (t) => { $("#platzl-titel").textContent = t; };
  const fehlerZeigen = (e) => inhalt().replaceChildren(el("p", { class: "fehler", role: "alert", text: e.message || String(e) }),
    el("button", { class: "knopf", type: "button", text: "Noch einmal", onclick: () => zeigen() }));

  async function nichtVerbunden(meldung = "") {
    titel("Platzl");
    const w = pl.wartet();
    inhalt().replaceChildren(el("div", { class: "karte" },
      el("h3", { text: "Die Community an einem Ort" }),
      el("p", { text: "Im Platzl reden die Mitglieder über Fragen, Ideen, Fehler und Skills. Verbinde die App einmal mit deinem Platzl, dann liest du hier mit." }),
      el("button", { class: "knopf haupt breit", type: "button", id: "pl-verbinden", text: w ? "Weiter warten auf „Erlauben“ …" : "Mit dem Platzl verbinden", onclick: verbinden }),
      el("p", { class: "leise klein", text: "Im Platzl tippst du einmal auf „Erlauben“. Die Verbindung gilt nur für dieses Gerät, und du kannst sie jederzeit trennen." }),
      meldung ? el("p", { class: "info", role: "status", text: meldung }) : null));
  }

  async function verbinden() {
    const g = geraet();
    if (!g) return;
    const knopf = $("#pl-verbinden");
    if (knopf) knopf.disabled = true;
    try {
      const adresse = await pl.verbindenStarten(holen, g);

      location.replace(adresse);
    } catch (e) {
      if (knopf) knopf.disabled = false;
      nichtVerbunden(e.message);
    }
  }


  async function abholen({ ruhig = false } = {}) {
    const g = geraet();
    if (!g || !pl.wartet()) return false;
    try {
      const r = await pl.abholen(holen, g);
      if (r === "fertig") { status?.("Mit dem Platzl verbunden."); einstellungenZeigen(); if (!$("#platzl").hidden) zeigen(); return true; }
      if (r === "wartet" && !$("#platzl").hidden) {
        clearTimeout(s.warten);
        s.warten = setTimeout(() => abholen({ ruhig: true }), 3000);
      }
    } catch (e) {
      if (!ruhig || !$("#platzl").hidden) nichtVerbunden(e.message);
    }
    return false;
  }

  async function uebersicht() {
    titel("Platzl");
    inhalt().replaceChildren(el("p", { class: "leise", text: "Lädt …" }));
    if (!s.kats) {
      const d = await pl.api("/categories.json");
      s.kats = (d?.category_list?.categories || []).filter((c) => c && Number.isInteger(c.id)).map((c) => ({
        id: c.id, name: String(c.name || "").slice(0, 60), slug: String(c.slug || "").toLowerCase(), farbe: pl.kategorieFarbe(c.color),
        darf: c.permission == null || c.permission === 1,
      })).filter((c) => /^[a-z0-9-]+$/.test(c.slug));
    }
    const weg = s.kat ? `/c/${s.kat.slug}/${s.kat.id}/l/latest.json` : "/latest.json";
    const d = await pl.api(weg);
    const themen = (d?.topic_list?.topics || []).filter((t) => Number.isInteger(t.id)).slice(0, 30);
    const katNach = new Map(s.kats.map((c) => [c.id, c]));
    const leiste = el("div", { class: "pl-kats", role: "group", "aria-label": "Kategorien" },
      el("button", { class: "pl-kat", type: "button", "aria-pressed": String(!s.kat), text: "Neueste", onclick: () => { s.kat = null; zeigen(); } }),
      ...s.kats.map((c) => el("button", { class: "pl-kat", type: "button", "aria-pressed": String(s.kat?.id === c.id), onclick: () => { s.kat = c; zeigen(); } },
        el("span", { class: "pl-punkt", farbe: c.farbe, "aria-hidden": "true" }), c.name)));
    const liste = el("ul", { class: "pl-liste" }, ...themen.map((t) => {
      const k = katNach.get(t.category_id);
      const antworten = Math.max(0, Number(t.posts_count || 1) - 1);
      return el("li", {}, el("button", { class: "pl-thema", type: "button", onclick: () => { s.stapel.push("uebersicht"); schritt(); thema(t.id); } },
        el("strong", { text: String(t.title || "").slice(0, 200) }),
        el("span", { class: "pl-meta" },
          k ? el("span", { class: "pl-punkt", farbe: k.farbe, "aria-hidden": "true" }) : null,
          k ? `${k.name} · ` : "", (antworten === 1 ? `1 Antwort · ${datum(t.last_posted_at || t.created_at)}` : `${antworten} Antworten · ${datum(t.last_posted_at || t.created_at)}`))));
    }));
    const neu = el("div", { class: "pl-aktionen" }, el("button", { class: "knopf", type: "button", text: "Neues Thema", onclick: () => entwurf({ kategorie: s.kat?.slug || "" }) }));
    inhalt().replaceChildren(leiste, neu, themen.length ? liste : el("p", { class: "leise", text: "Hier ist es noch ruhig." }),
      el("a", { class: "knopf breit pl-mehr", href: s.kat ? `${pl.FORUM}/c/${s.kat.slug}/${s.kat.id}` : pl.FORUM, target: "_blank", rel: "noopener noreferrer", text: "Im Platzl öffnen" }));
  }

  async function thema(id) {
    titel("Thema");
    inhalt().replaceChildren(el("p", { class: "leise", text: "Lädt …" }));
    const d = await pl.api(`/t/${Number(id)}.json`);
    titel(String(d?.title || "Thema").slice(0, 80));
    const beitraege = (d?.post_stream?.posts || []).slice(0, 50).map((p) => el("article", { class: "pl-beitrag" },
      el("div", { class: "pl-meta" }, el("strong", { text: "@" + String(p.username || "").slice(0, 60) }), " · " + datum(p.created_at)),
      el("div", { class: "pl-text" }, pl.inhaltBauen(p.cooked))));
    const slug = /^[a-z0-9-]+$/.test(String(d?.slug || "")) ? d.slug : "thema";

    const kat = (s.kats || []).find((c) => c.id === d?.category_id);
    const hatSkill = kat?.slug === "skills" && pl.skillImBeitrag(d?.post_stream?.posts?.[0]?.cooked);
    const knopf = hatSkill ? el("button", { class: "knopf haupt breit pl-skill", type: "button", text: "Skill verwenden", onclick: async (e) => {
      const k = e.currentTarget;
      k.disabled = true;
      try { skillVerwenden?.(await pl.skillHolen(id)); } catch (x) { status?.(x.message); } finally { k.disabled = false; }
    } }) : null;
    inhalt().replaceChildren(el("h3", { text: String(d?.title || "").slice(0, 200) }), knopf, ...beitraege,
      el("div", { class: "pl-aktionen" },
        el("button", { class: "knopf haupt", type: "button", text: "Antworten", onclick: () => entwurf({ thema: Number(id), themaTitel: String(d?.title || "") }) }),
        el("a", { class: "knopf", href: `${pl.FORUM}/t/${slug}/${Number(id)}`, target: "_blank", rel: "noopener noreferrer", text: "Im Platzl öffnen" })));
    inhalt().scrollTop = 0; $("#platzl").scrollTop = 0;
  }


  async function kategorienSicher() {
    if (s.kats) return;
    const d = await pl.api("/categories.json");
    s.kats = (d?.category_list?.categories || []).filter((c) => c && Number.isInteger(c.id)).map((c) => ({
      id: c.id, name: String(c.name || "").slice(0, 60), slug: String(c.slug || "").toLowerCase(), farbe: pl.kategorieFarbe(c.color),
      darf: c.permission == null || c.permission === 1,
    })).filter((c) => /^[a-z0-9-]+$/.test(c.slug));
  }

  async function entwurf(e) {
    if (!(await pl.verbunden())) {

      const d = $("#pl-noetig"); d.returnValue = ""; d.showModal();
      d.addEventListener("close", () => { if (d.returnValue === "verbinden") { auf(); verbinden(); } }, { once: true });
      return;
    }
    try { await kategorienSicher(); } catch (x) { status?.(x.message); return; }
    s.entwurf = { ...e };
    const antwort = !!e.thema;
    $("#plw-kopf").textContent = antwort ? `Antworten: ${String(e.themaTitel || "").slice(0, 60)}` : (e.fehler ? "Fehler im Platzl melden" : "Neues Thema im Platzl");
    $("#plw-titel-z").hidden = antwort; $("#plw-kat-z").hidden = antwort;
    $("#plw-grund-z").hidden = !e.fehler; $("#plw-grund").value = e.grund || "";
    $("#plw-titel").value = e.titel || "";
    const sel = $("#plw-kat"); sel.replaceChildren();
    for (const c of s.kats.filter((c) => c.darf)) sel.append(el("option", { value: String(c.id), text: c.name }));
    const vor = s.kats.find((c) => (e.kategorieId ? c.id === e.kategorieId : c.slug === e.kategorie) && c.darf);
    if (vor) sel.value = String(vor.id);
    $("#plw-text").value = e.text || "";
    $("#plw-fehler").textContent = "";
    const d = $("#pl-schreiben"); d.returnValue = ""; d.showModal();
    (e.fehler ? $("#plw-grund") : antwort || e.titel ? $("#plw-text") : $("#plw-titel")).focus();
  }
  function entwurfPruefen() {
    const e = s.entwurf, text = $("#plw-text").value.trim(), titel = $("#plw-titel").value.replace(/\s+/g, " ").trim();
    if (e.fehler && $("#plw-grund").value.trim().length < 10) return "Schreib bitte oben ins rote Feld kurz dazu, was an der Antwort falsch ist.";
    if (text.length < pl.TEXT_MIN) return `Der Text braucht mindestens ${pl.TEXT_MIN} Zeichen.`;
    if (!e.thema && titel.length < pl.TITEL_MIN) return `Der Titel braucht mindestens ${pl.TITEL_MIN} Zeichen.`;
    if (!e.thema && !$("#plw-kat").value) return "Bitte eine Kategorie wählen.";
    return "";
  }
  function verdrahtenSchreiben() {
    const w = $("#pl-schreiben"), b = $("#pl-bestaetigen");
    w.addEventListener("close", () => {
      if (w.returnValue !== "weiter" || !s.entwurf) return;
      const f = entwurfPruefen();
      if (f) { $("#plw-fehler").textContent = f; w.showModal(); return; }
      Object.assign(s.entwurf, { text: $("#plw-text").value.trim(), titel: $("#plw-titel").value.replace(/\s+/g, " ").trim(),
        kategorieId: Number($("#plw-kat").value) || null, grund: $("#plw-grund").value.trim() });
      const kat = s.kats.find((c) => c.id === s.entwurf.kategorieId);
      $("#plb-wo").textContent = s.entwurf.thema ? `Als Antwort in „${String(s.entwurf.themaTitel || "").slice(0, 80)}“.` : `Neues Thema „${s.entwurf.titel}“ in ${kat ? kat.name : "?"}.`;
      $("#plb-text").textContent = veroeffentlichterText(s.entwurf);
      $("#plb-fehler").textContent = ""; $("#plb-ja").disabled = false;
      b.returnValue = ""; b.showModal();
    });
    b.addEventListener("cancel", (ev) => { ev.preventDefault(); b.close("zurueck"); });
    b.addEventListener("close", async () => {
      const e = s.entwurf;
      if (!e) return;
      if (b.returnValue === "zurueck") { entwurf(e); return; }
      if (b.returnValue !== "ja") return;
      $("#plb-ja").disabled = true;
      try {
        const r = await pl.schreiben({ titel: e.titel, text: veroeffentlichterText(e), kategorie: e.kategorieId, thema: e.thema || null });
        s.entwurf = null;
        status?.(e.thema ? "Deine Antwort steht im Platzl." : "Dein Thema steht im Platzl. Danke!");
        if (r.thema) { if ($("#platzl").hidden) auf(); s.stapel.push("uebersicht"); schritt(); await thema(r.thema); }
      } catch (x) {
        $("#plb-fehler").textContent = x.message; $("#plb-ja").disabled = false; b.showModal();
      }
    });
  }

  function veroeffentlichterText(e) {
    return e.fehler && e.grund ? `**Was daran falsch ist:**
${e.grund}

${e.text}` : e.text;
  }
  verdrahtenSchreiben();


  function fehlerMelden({ frage = "", antwort = "", modell = "", skill = "" }) {
    const zitat = (t) => String(t || "").trim().slice(0, 3000).split("\n").map((z) => "> " + z).join("\n");
    const kurz = String(frage || "").replace(/\s+/g, " ").trim();
    const text = [
      "**Meine Frage:**", zitat(frage), "",
      "**Die Antwort von KIplatz:**", zitat(antwort), "",
      [modell ? `Modell: ${String(modell).slice(0, 60)}` : "", skill ? `Skill: ${String(skill).slice(0, 80)}` : ""].filter(Boolean).join(" · "),
    ].join("\n").trim();
    entwurf({ fehler: true, kategorie: "mitbauen", titel: ("Fehler in einer Antwort: " + kurz).slice(0, 90), text });
  }

  async function zeigen() {
    try {
      if (!(await pl.verbunden())) { await nichtVerbunden(); if (pl.wartet()) abholen({ ruhig: true }); return; }
      await uebersicht();
    } catch (e) {
      if (e.code === "PLATZL_AUS") { einstellungenZeigen(); nichtVerbunden(e.message); } else fehlerZeigen(e);
    }
  }


  function schritt() { verlauf.auf("platzl", stufeZu); }

  function stufeZu(letzter = true) {
    if (s.stapel.pop()) { if (letzter) zeigen(); }
    else { clearTimeout(s.warten); $("#platzl").hidden = true; }
  }
  function auf() { verlauf.bis("platzl"); s.stapel = []; if ($("#platzl").hidden) { $("#platzl").hidden = false; schritt(); } zeigen(); $("#platzl-titel").focus({ preventScroll: true }); }

  function zu() { s.stapel = []; if (!verlauf.schliessen("platzl")) stufeZu(); }
  function zurueck() { if (!verlauf.zurueck("platzl")) stufeZu(); }

  async function einstellungenZeigen() {
    const p = await pl.verbunden();
    $("#k-platzl-info").textContent = p ? "Verbunden" : "Nicht verbunden";
    $("#e-platzl").textContent = p ? `Verbunden${p.name ? " als @" + p.name : ""}.` : "Noch nicht verbunden.";
    $("#btn-platzl-verbinden").hidden = !!p;
    $("#platzl-verbunden").hidden = !p;
    $("#btn-platzl").hidden = !p;
  }

  $("#btn-platzl").onclick = auf;
  $("#btn-platzl-zurueck").onclick = zurueck;
  $("#btn-platzl-verbinden").onclick = () => { auf(); verbinden(); };
  $("#btn-platzl-oeffnen").onclick = auf;
  $("#btn-platzl-trennen").onclick = async () => {
    if (!confirm("Die Verbindung zum Platzl auf diesem Gerät trennen?")) return;
    await pl.trennen(); s.kats = null; einstellungenZeigen(); status?.("Vom Platzl getrennt.");
  };
  return { auf, zu, offen: () => !$("#platzl").hidden, zurueck, abholen, einstellungenZeigen, fehlerMelden };
}
