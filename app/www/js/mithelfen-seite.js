// SPDX-License-Identifier: AGPL-3.0-or-later
const $ = (s) => document.querySelector(s);
function el(tag, attrs = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "onclick") e.onclick = v; else if (k === "text") e.textContent = v;
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const k of kinder) if (k != null) e.append(k);
  return e;
}
const URTEILE = [["stimmt", "Stimmt"], ["stimmt_nicht", "Stimmt nicht"], ["unsicher", "Unsicher"]];
export const EMPFEHLUNG = "Ich nutze KIplatz, die KI aus Österreich, die von ihrer Community lebt: mit Quellen unter jeder Antwort und ohne Rechenzentrum. Probier es aus: https://kiplatz.at/";

function wann(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(kiplatzSprache.datumSprache(), { day: "numeric", month: "long" });
}

export function mithelfenSeite({ holen, geraet, platzlAuf }) {
  const inhalt = () => $("#mithelfen-inhalt");
  let offen = false, nr = 0, meldung = "";

  async function laden() {
    const meine = ++nr;
    let liste = null;
    try { liste = (await holen("/pruefungen", { body: {}, geraet: geraet() })).pruefungen || []; } catch { liste = null; }
    if (meine !== nr || !offen) return;
    zeichnen(liste);
  }

  function pruefKarte(p) {
    const satz = el("input", { class: "eingabe", "aria-label": "Wenn du magst: ein Satz dazu", placeholder: "Wenn du magst: ein Satz dazu", maxlength: "600", autocomplete: "off" });
    const knoepfe = URTEILE.map(([wert, text]) => el("button", { class: wert === "stimmt" ? "knopf haupt" : "knopf", type: "button", text,
      onclick: () => abgeben(p.kennung, wert, satz.value.trim(), karte) }));
    const karte = el("div", { class: "karte mh-pruefung" },
      el("div", { class: "leise klein", text: `Frage eines Mitglieds${p.zeit ? ", " + wann(p.zeit) : ""}` }),
      el("p", {}, el("strong", { text: String(p.frage || "") })),
      el("div", { class: "mh-antwort", text: String(p.antwort || "") }),
      Array.isArray(p.quellen) && p.quellen.length ? el("p", { class: "leise klein", text: "Quellen: " + p.quellen.map(String).join("; ") }) : null,
      satz,
      el("div", { class: "knopf-reihe" }, ...knoepfe));
    return karte;
  }

  async function abgeben(kennung, urteil, kommentar, karte) {
    for (const b of karte.querySelectorAll("button, input")) b.disabled = true;
    try {
      await holen("/pruefung-abgeben", { body: { kennung, urteil, kommentar }, geraet: geraet() });
      meldung = "Danke fürs Nachschauen. Das Mitglied sieht dein Urteil unter seiner Antwort, und du hast 2 Credits dafür bekommen.";
    } catch (e) { meldung = e.message || "Das hat nicht geklappt. Probier es bitte noch einmal."; }
    await laden();
  }

  async function empfehlen() {
    try {
      if (navigator.share) { await navigator.share({ text: EMPFEHLUNG }); return; }
      await navigator.clipboard.writeText(EMPFEHLUNG);
      meldung = "Kopiert. Füg den Text ein, wo du magst, etwa in einer Nachricht an Freunde.";
    } catch (e) { if (e?.name !== "AbortError") meldung = "Teilen ging nicht. Erzähl einfach von kiplatz.at."; }
    if (offen) laden();
  }

  function zeichnen(liste) {
    const teile = [];
    if (meldung) { teile.push(el("p", { class: "karte mh-meldung", role: "status", text: meldung })); meldung = ""; }
    teile.push(el("p", { class: "leise", text: "Mithelfen geht auch ohne PC. Alles hier machst du selbst, wann du magst. Am Handy rechnet nichts, und nichts läuft im Hintergrund." }));


    teile.push(el("h3", { class: "mh-titel", text: "Antworten prüfen" }));
    teile.push(el("p", { class: "leise klein", text: "Fragen und Antworten, die ein Mitglied bestätigt haben will, ohne Namen. Lies, schau in die Quellen und sag, ob es stimmt. 2 Credits je Prüfung, im Zweifel „Unsicher“." }));
    if (liste === null) teile.push(el("p", { class: "karte leise", text: "Der Community-Server ist gerade nicht erreichbar. Schau später wieder vorbei." }));
    else if (!liste.length) teile.push(el("p", { class: "karte leise", text: "Gerade wartet nichts auf eine Prüfung. Schau später wieder vorbei." }));
    else teile.push(...liste.map(pruefKarte));


    teile.push(el("div", { class: "karte" },
      el("h3", { text: "Antworten berichtigen" }),
      el("p", { class: "leise klein", text: "Stimmt eine Antwort nicht? Tipp darunter auf den Daumen nach unten, schreib, wie es richtig ist, und lass „Mit der Community teilen“ an. Bestätigt ein PC der Community deine Berichtigung, gilt sie für alle, und du bekommst 2 Credits." })));


    teile.push(el("div", { class: "karte" },
      el("h3", { text: "Skills für alle" }),
      el("p", { class: "leise klein", text: "Ein Skill sagt KIplatz, wie es bei einem Thema antworten soll. Im Platzl findest du die Skills der anderen und teilst deine eigenen." }),
      el("button", { class: "knopf", type: "button", text: "Platzl öffnen", onclick: platzlStatt })));


    teile.push(el("div", { class: "karte" },
      el("h3", { text: "KIplatz weiterempfehlen" }),
      el("p", { class: "leise klein", text: "Je mehr mitmachen, desto schneller und besser werden die Antworten für alle. Schick einen Link an Freunde oder Familie, kein Code nötig." }),
      el("button", { class: "knopf haupt", type: "button", text: "Link teilen", onclick: empfehlen })));
    inhalt().replaceChildren(...teile);
  }


  let imVerlauf = false;
  addEventListener("popstate", () => { if (imVerlauf && offen) { imVerlauf = false; schliessen(); } });
  function schliessen() { offen = false; $("#mithelfen").hidden = true; }
  function auf() {
    if (!offen) { offen = true; $("#mithelfen").hidden = false; history.pushState({ mithelfen: 1 }, ""); imVerlauf = true; }
    inhalt().replaceChildren(el("p", { class: "leise mitte", text: "Einen Moment …" }));
    $("#mithelfen-titel").focus({ preventScroll: true });
    laden();
  }
  function zu() { if (imVerlauf) { imVerlauf = false; history.back(); } schliessen(); }

  function platzlStatt() {
    schliessen();
    if (imVerlauf) { imVerlauf = false; addEventListener("popstate", () => platzlAuf(), { once: true }); history.back(); }
    else platzlAuf();
  }
  function zurueck() { if (imVerlauf) history.back(); else schliessen(); }

  $("#btn-mithelfen").onclick = auf;
  $("#btn-mithelfen-zurueck").onclick = zurueck;
  return { auf, zu, zurueck, offen: () => offen };
}
