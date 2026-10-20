// SPDX-License-Identifier: AGPL-3.0-or-later
import * as verlauf from "./verlauf.js";

const $ = (s) => document.querySelector(s);

const stuecke = (teile) => teile.flatMap((t, i) => [i ? " · " : null, el("span", { text: t })]);
function el(tag, attrs = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "onclick") e.onclick = v; else if (k === "text") e.textContent = v;
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const k of kinder) if (k != null) e.append(k);
  return e;
}

export function wikiSeite({ holen, geraet, status }) {
  const inhalt = () => $("#wiki-inhalt");
  let offen = false, nr = 0, vorbelegt = "";

  async function laden() {
    const g = geraet();
    const meine = ++nr;
    if (!g) { zeichnen(null, null, true); return; }
    const [abstimmen, eigene] = await Promise.all([
      holen("/cwiki", { body: { aktion: "offen" }, geraet: g }).catch((e) => (e.code === "KONTO_FEHLT" ? { ohne_konto: true } : null)),
      holen("/cwiki", { body: { aktion: "meine" }, geraet: g }).catch(() => null),
    ]);
    if (meine !== nr || !offen) return;
    zeichnen(abstimmen, eigene, !!abstimmen?.ohne_konto);
  }

  function quelleZeile(z) {
    const k = el("small", { class: "leise" }, "Quelle: ");
    if (/^https?:\/\//i.test(z.link || "")) k.append(el("a", { href: z.link, target: "_blank", rel: "noopener noreferrer", text: z.quelle }));
    else k.append(el("span", { text: z.quelle }));
    return k;
  }

  function zeichnen(abstimmen, eigene, ohneKonto) {
    const teile = [];
    teile.push(el("div", { class: "karte" },
      el("h3", { text: "So funktioniert das Wiki" }),
      el("p", { class: "leise", text: "Du kennst eine bessere Antwort? Schreib sie in eigenen Worten und gib die Quelle an. Wenn mindestens 5 Mitglieder mit Ja stimmen und mehr Ja als Nein da sind, bekommt jeder diese Antwort, mit der Quelle darunter. Dein Name bleibt unsichtbar, die Frage und dein Text sehen angemeldete Mitglieder." })));
    if (ohneKonto) {
      teile.push(el("div", { class: "karte" }, el("p", { class: "leise klein", text: "Das Wiki gibt es mit einem KIplatz-Konto. Melde dieses Handy mit deinem Konto an, unter „Konto und Einstellungen“ und „Konten“." })));
      inhalt().replaceChildren(...teile);
      return;
    }
    if (!abstimmen) {
      teile.push(el("div", { class: "karte" }, el("p", { class: "leise klein", text: "Der Community-Server ist gerade nicht erreichbar." })));
      inhalt().replaceChildren(...teile);
      return;
    }
    teile.push(vorschlagKarte());
    teile.push(abstimmenKarte(abstimmen));
    teile.push(meineKarte(eigene));
    inhalt().replaceChildren(...teile);
    if (vorbelegt) { $("#wiki-text")?.focus({ preventScroll: false }); vorbelegt = ""; }
  }

  function vorschlagKarte() {
    const frage = el("input", { id: "wiki-frage", maxlength: "200", placeholder: "z. B. Wie hoch ist der Großglockner?", autocomplete: "off" });
    frage.value = vorbelegt;
    const text = el("textarea", { id: "wiki-text", rows: "5", maxlength: "1200", placeholder: "Deine Antwort in eigenen Worten, ohne Link" });
    const quelle = el("input", { id: "wiki-quelle", maxlength: "300", placeholder: "Internetadresse, oder Titel und Verfasser", autocomplete: "off", spellcheck: "false" });
    return el("div", { class: "karte", id: "wiki-vorschlag-karte" },
      el("h3", { text: "Antwort vorschlagen" }),
      el("p", { class: "leise klein", text: "Nur allgemeine Wissensfragen. Keine Telefonnummern oder Adressen, keine Fragen über dich." }),
      el("label", { for: "wiki-frage", text: "Frage" }), frage,
      el("label", { for: "wiki-text", text: "Antwort" }), text,
      el("label", { for: "wiki-quelle", text: "Quelle (Pflicht)" }), quelle,
      el("button", { class: "knopf haupt breit", type: "button", text: "Vorschlag abschicken", onclick: () => {
        if (!frage.value.trim() || !text.value.trim() || !quelle.value.trim()) { status("Bitte Frage, Antwort und Quelle ausfüllen."); return; }
        tun({ aktion: "vorschlagen", frage: frage.value, text: text.value, quelle: quelle.value }, true);
      } }));
  }

  function abstimmenKarte(a) {
    const k = el("div", { class: "karte" }, el("h3", { text: "Abstimmen" }));
    const liste = a.liste || [];
    if (!liste.length) { k.append(el("p", { class: "leise klein", text: "Im Moment wartet nichts auf deine Stimme." })); return k; }
    k.append(el("p", { class: "leise klein", text: `Stimmt die Antwort, und passt die Quelle dazu? Ab ${a.ab_ja} Ja und mehr Ja als Nein gilt sie.` }));
    for (const z of liste) {
      k.append(el("div", { class: "wiki-vorschlag" },
        el("p", {}, el("b", { text: z.frage })),
        el("p", { text: z.text }),
        quelleZeile(z),
        el("p", { class: "leise klein" }, ...stuecke([`${z.ja} Ja, ${z.nein} Nein`, z.status === "gilt" ? "gilt gerade" : ""].filter(Boolean))),
        el("div", { class: "knopf-paar" },
          el("button", { class: "knopf", type: "button", text: "Ja", onclick: () => stimme(z.id, "ja") }),
          el("button", { class: "knopf", type: "button", text: "Nein", onclick: () => stimme(z.id, "nein") }))));
    }
    return k;
  }

  const STATUS = {
    offen: "wartet auf Stimmen", gilt: "gilt für alle", abgelehnt: "abgelehnt", ersetzt: "durch einen besseren ersetzt",
    zurueckgezogen: "zurückgezogen", entfernt: "vom Admin entfernt",
  };

  function meineKarte(e) {
    const k = el("div", { class: "karte" }, el("h3", { text: "Meine Vorschläge" }));
    const liste = e?.liste || [];
    if (!liste.length) { k.append(el("p", { class: "leise klein", text: "Du hast noch nichts vorgeschlagen." })); return k; }
    for (const z of liste) {
      k.append(el("div", { class: "wiki-vorschlag" },
        el("p", {}, el("b", { text: z.frage })),
        el("p", { class: "leise klein" }, ...stuecke([STATUS[z.status] || z.status, `${z.ja} Ja, ${z.nein} Nein`])),
        z.status === "offen" || z.status === "gilt"
          ? el("button", { class: "knopf", type: "button", text: "Zurückziehen", onclick: () => { if (confirm("Den Vorschlag zurückziehen?")) tun({ aktion: "zurueck", id: z.id }); } })
          : null));
    }
    return k;
  }

  async function stimme(id, art) {
    for (const b of inhalt().querySelectorAll("button")) b.disabled = true;
    try { const r = await holen("/cwiki", { body: { aktion: "stimme", id, art }, geraet: geraet() }); status(r.text || "Danke."); }
    catch (e) { status(e.message); }
    await laden();
  }

  async function tun(body, leeren = false) {
    for (const b of inhalt().querySelectorAll("button")) b.disabled = true;
    let ok = false;
    try { const r = await holen("/cwiki", { body, geraet: geraet() }); status(r.text || "Erledigt."); ok = true; }
    catch (e) { status(e.message); }
    if (ok || !leeren) await laden();
    else for (const b of inhalt().querySelectorAll("button")) b.disabled = false;
  }


  function schliessen() { offen = false; $("#wiki").hidden = true; }
  function auf(frage = "") {
    vorbelegt = typeof frage === "string" ? frage.replace(/^Live nachprüfen:\s*/i, "").slice(0, 200) : "";
    if (!offen) { offen = true; $("#wiki").hidden = false; verlauf.auf("wiki", schliessen); }
    inhalt().replaceChildren(el("p", { class: "leise mitte", text: "Einen Moment …" }));
    $("#wiki-titel").focus({ preventScroll: true });
    laden();
  }
  function zu() { if (!verlauf.schliessen("wiki")) schliessen(); }
  function zurueck() { if (!verlauf.zurueck("wiki")) schliessen(); }

  $("#btn-wiki").onclick = () => auf();
  $("#btn-wiki-zurueck").onclick = zurueck;
  return { auf, zu, zurueck, offen: () => offen };
}
