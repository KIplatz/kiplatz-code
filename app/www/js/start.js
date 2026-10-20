// SPDX-License-Identifier: AGPL-3.0-or-later
import "./sprache-laden.js";
import { nativ } from "./nativ.js";
import * as tresor from "./tresor.js";
import * as konten from "./konten.js";
import { holen, holenRoh, basisSetzen, standBewerten, ServerFehler, beiAbgemeldet } from "./schnittstelle.js";
import { Gespraeche, FARBEN, tagesgruss } from "./gespraeche.js";
import { WETTER, MIT_ORT, mitOrt, sauber } from "./einrichten.js";
import { zeichnen as antwortZeichnen, nurRueckfrage } from "./antwort.js";
import { symbol, symboleEinsetzen } from "./symbole.js";
import { APP_VERSION } from "./version.js";
import { Abgleich } from "./abgleich.js";
import { platzlSeite } from "./platzl-seite.js";
import { bestenlisteSeite } from "./bestenliste-seite.js";
import { wikiSeite } from "./wiki-seite.js";
import { mithelfenSeite } from "./mithelfen-seite.js";
import * as verlauf from "./verlauf.js";
import * as skillAblage from "./skills.js";
import * as meineKi from "./meine-ki.js";
import { trennen as platzlTrennen, entwicklungSetzen as platzlEntwicklung, skillHolen, FORUM as platzlForum, verbunden as platzlVerbunden } from "./platzl.js";
import * as anhang from "./anhang.js";
import { Sprechen, anhaengen as sprAnhaengen, GROESSE_MB as SPRACHE_MB } from "./sprache.js";
import * as zuhause from "./zuhause.js";

const $ = (s) => document.querySelector(s);
const ENTWICKLUNG = !nativ && ["localhost", "127.0.0.1"].includes(location.hostname);


if (!nativ) basisSetzen("");
if (ENTWICKLUNG) platzlEntwicklung(location.origin);

const z = { geraet: null, gespraeche: null, laufend: null, einst: { aussehen: "system", schrift: "normal", standort: false }, sperre: false, anhaenge: [], anhangLiest: false, zuhause: [] };


function ablageLesen(name, sonst) { try { return JSON.parse(localStorage.getItem("kiplatz." + konten.name(name)) ?? "null") ?? sonst; } catch { return sonst; } }
function ablageSchreiben(name, wert) { try { localStorage.setItem("kiplatz." + konten.name(name), JSON.stringify(wert)); } catch { status("Der Speicher des Geräts ist voll."); } }
const ablegen = () => ablageSchreiben("gespraeche", z.gespraeche.daten());


const AUSSEHEN = "kiplatz.aussehen";
const AUSSEHEN_WERTE = { aussehen: ["system", "hell", "dunkel"], schrift: ["normal", "gross", "sehr-gross"] };
function aussehenLesen() {
  try {
    const a = JSON.parse(localStorage.getItem(AUSSEHEN) ?? "null");
    if (!a || typeof a !== "object") return null;
    const r = {};
    for (const [k, werte] of Object.entries(AUSSEHEN_WERTE)) if (werte.includes(a[k])) r[k] = a[k];
    return r;
  } catch { return null; }
}
function aussehenSchreiben() {
  try { localStorage.setItem(AUSSEHEN, JSON.stringify({ aussehen: z.einst.aussehen, schrift: z.einst.schrift })); } catch { }
}


const projekte = () => { const p = ablageLesen("projekte", {}); return p && typeof p === "object" && !Array.isArray(p) ? p : {}; };
const projekteSetzen = (p) => ablageSchreiben("projekte", p);
const projekteZu = () => new Set(ablageLesen("projekte-zu", []));
const speichern = () => { ablegen(); abgleichBald(); };


let abgleichUhr = null;
function abgleichBald(ms = 3000) { clearTimeout(abgleichUhr); abgleichUhr = setTimeout(abgleichen, ms); }
async function abgleichen() {

  if (!z.abgleich || !z.geraet?.konto || z.laufend || document.visibilityState === "hidden") return;
  try {
    const r = await z.abgleich.abgleichen();
    z.abgleich.fehler = "";
    if (r?.geholt || r?.geloescht) { zeichneListe(); zeichneVerlauf(); }
  } catch (e) { z.abgleich.fehler = e.message; }
}

function einstAnwenden() {
  document.documentElement.dataset.aussehen = z.einst.aussehen;
  document.documentElement.dataset.schrift = z.einst.schrift;


  const a = z.einst.aussehen;
  const cs = document.querySelector('meta[name="color-scheme"]');
  if (cs) cs.content = a === "hell" ? "light" : a === "dunkel" ? "dark" : "light dark";
  for (const m of document.querySelectorAll('meta[name="theme-color"]')) {
    const dunkel = a === "dunkel" || (a === "system" && m.media.includes("dark"));
    m.content = dunkel ? "#121616" : "#f7f9f8";
  }
}


let statusUhr = 0, statusDauer = "";
function status(t) {
  $("#status").textContent = t || statusDauer;
  clearTimeout(statusUhr);
  statusUhr = t ? setTimeout(() => { statusUhr = 0; $("#status").textContent = statusDauer; }, 6000) : 0;
}
function statusDauerhaft(t) {
  statusDauer = t || "";
  if (!statusUhr) $("#status").textContent = statusDauer;
}
function knopf(icon, label, klasse = "rund") {
  const b = document.createElement("button");
  b.type = "button"; b.className = klasse; b.setAttribute("aria-label", label); b.title = label;
  b.append(symbol(icon));
  return b;
}
async function kopieren(text) {
  try { await navigator.clipboard.writeText(text); status("Kopiert."); } catch { status("Das Kopieren hat nicht geklappt. Markier den Text und kopiere ihn von Hand."); }
}


function teilText(frage, antwort) { return (frage ? `Frage: ${frage}

` : "") + `Antwort von KIplatz:
${antwort}

Erarbeitet von einem PC der KIplatz-Community (kiplatz.at)`; }
async function teilen(text) {
  try {
    if (nativ) return await nativ.teilen(text);
    if (navigator.share) return await navigator.share({ text });
  } catch (e) { if (e && e.name === "AbortError") return; }
  kopieren(text);
}
const schlafen = (ms) => new Promise((r) => setTimeout(r, ms));
function wann(t) {
  const d = new Date(t);
  if (isNaN(d)) return String(t);

  if (kiplatzSprache.aktiv() === "en") return d.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit", year: "numeric" }) + " um " + d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" }) + " Uhr";
}


const schmal = () => !matchMedia("(min-width: 900px)").matches;
function leisteAuf() { zeichneListe(); $("#leiste").inert = false; document.body.classList.add("leiste-offen"); if (schmal()) $("#schleier").hidden = false; }


function leisteZu() { if ($("#leiste").contains(document.activeElement)) document.activeElement.blur(); document.body.classList.remove("leiste-offen"); $("#schleier").hidden = true; $("#leiste").inert = schmal(); }


function sucheAuf() {
  $("#leiste-oben").hidden = true; $("#suche-feld").hidden = false; $("#btn-suche").setAttribute("aria-expanded", "true"); $("#suche").focus();
}
function sucheZu() {
  const war = !!$("#suche").value; $("#suche").value = "";
  $("#suche-feld").hidden = true; $("#leiste-oben").hidden = false; $("#btn-suche").setAttribute("aria-expanded", "false"); $("#btn-suche").focus();
  if (war) zeichneListe();
}

function zeichneListe() {
  const nav = $("#liste"); nav.replaceChildren();
  const treffer = z.gespraeche.suchen($("#suche").value);
  const angeheftet = treffer.filter((g) => g.angeheftet && g.nachrichten.length);
  const andere = treffer.filter((g) => !g.angeheftet && g.nachrichten.length);
  const eintrag = (g, imProjekt = false) => {
      const b = document.createElement("button"); b.type = "button"; b.dataset.kennung = g.kennung;
      if (imProjekt) b.classList.add("im-projekt");
      if (g.kennung === z.gespraeche.aktuellId) b.setAttribute("aria-current", "true");
      const streifen = document.createElement("span"); streifen.className = "farbstreifen"; streifen.setAttribute("aria-hidden", "true");
      if (FARBEN[g.farbe]) { streifen.style.background = FARBEN[g.farbe][1]; b.title = FARBEN[g.farbe][0]; }
      b.append(streifen);
      if (g.angeheftet) b.append(symbol("nadel"));
      const t = document.createElement("span"); t.className = "t"; t.translate = false; t.textContent = z.gespraeche.titel(g); b.append(t);
      return b;
  };
  const gruppe = (titel, liste) => {
    if (!liste.length) return;
    const h = document.createElement("h4"); h.textContent = titel; nav.append(h);
    for (const g of liste) nav.append(eintrag(g));
  };
  gruppe("Angeheftet", angeheftet);

  const suche = !!$("#suche").value.trim(), pmap = projekte(), zu = projekteZu();
  const namen = [...new Set([...Object.keys(pmap), ...andere.filter((g) => g.projekt).map((g) => g.projekt)])].sort((a, b) => a.localeCompare(b, "de"));


  if (!suche && namen.length) {
    const kopf = document.createElement("div"); kopf.className = "projekte-kopf";
    const h = document.createElement("h4"); h.textContent = "Projekte";
    const plus = document.createElement("button"); plus.type = "button"; plus.className = "projekt-neu"; plus.textContent = "+ Neues Projekt";
    plus.onclick = () => z.projektNeu?.();
    kopf.append(h, plus); nav.append(kopf);
  }
  for (const n of namen) {
    const drin = andere.filter((g) => g.projekt === n);
    if (suche && !drin.length) continue;
    const k = document.createElement("button"); k.type = "button"; k.className = "projekt"; k.dataset.projekt = n;
    const punkt = document.createElement("span"); punkt.className = "projekt-punkt"; punkt.textContent = zu.has(n) && !suche ? "○" : "●";
    if (FARBEN[pmap[n]]) punkt.style.color = FARBEN[pmap[n]][1];
    const t = document.createElement("span"); t.className = "t"; t.textContent = n;
    const anz = document.createElement("small"); anz.textContent = String(drin.length);
    k.append(punkt, t, anz); nav.append(k);
    if (!zu.has(n) || suche) for (const g of drin) nav.append(eintrag(g, true));
  }
  gruppe(suche ? "Gefunden" : "Gespräche", andere.filter((g) => !g.projekt || !namen.includes(g.projekt)));
  if (!angeheftet.length && !andere.length) {
    const p = document.createElement("p"); p.className = "leer";
    p.textContent = $("#suche").value.trim() ? "Nichts gefunden." : "Noch keine Gespräche. Stell deine erste Frage.";
    nav.append(p);
  }
  const wer = z.geraet ? (z.geraet.konto || z.geraet.name) : "KIplatz";
  $("#geraet-name").textContent = wer;
  $("#avatar").textContent = (wer.trim()[0] || "K").toUpperCase();
  $("#avatar-kopf").textContent = $("#avatar").textContent;
}


function willkommen() {
  const anrede = sauber(z.einst.anrede, 40);
  if (anrede) return `${tagesgruss(new Date().getHours())}, ${anrede}`;

  const rest = String(z.geraet?.name || "").split(/\s+/).filter((w) => w && !/^(iphone|ipad|mac|macbook|handy|tablet|android-handy|android-tablet|smartphone|android|samsung|galaxy|pixel|xiaomi|huawei|telefon|von|vom|das|mein|meins|de[rs]?|\d+\w*)$/i.test(w) && !/['’]s$/i.test(w));
  const gruss = tagesgruss(new Date().getHours());
  return rest.length && rest.join(" ").length <= 24 ? `${gruss}, ${rest.join(" ")}` : gruss;
}


function dateienKnoten(n) {
  const box = document.createElement("div"); box.className = "dateien";
  const mehrere = new Set(n.dateien.map((d) => d.pc || "")).size > 1;
  for (const d of n.dateien) {
    const l = document.createElement("label"); l.className = "datei";
    const c = document.createElement("input"); c.type = "checkbox"; c.dataset.id = d.id; c.dataset.kid = d.kid || "";
    const t = document.createElement("span");
    const name = document.createElement("span"); name.className = "datei-name"; name.translate = false; name.textContent = d.name;
    const wo = [d.art, [d.wurzel, ...(d.ordner ? d.ordner.split("\\") : [])].join(" › "), d.geaendert ? wann(new Date(d.geaendert)) : "", zuhause.groesse(d.groesse), mehrere ? d.pc : ""].filter(Boolean).join(" · ");
    const info = document.createElement("small"); info.textContent = (d.runde === "aehnlich" ? "ähnlich · " : "") + wo;
    t.append(name, info); l.append(c, t); box.append(l);
  }
  const k = document.createElement("div"); k.className = "datei-knoepfe";
  const alle = document.createElement("button"); alle.type = "button"; alle.dataset.tun = "dateien-alle"; alle.textContent = "Alle auswählen";
  const holen_ = document.createElement("button"); holen_.type = "button"; holen_.dataset.tun = "dateien-holen"; holen_.textContent = "Aufs Handy holen"; holen_.disabled = true;
  k.append(alle, holen_); box.append(k);
  box.addEventListener("change", () => { const n_ = box.querySelectorAll("input:checked").length; holen_.disabled = !n_; holen_.dataset.tun = "dateien-holen"; holen_.textContent = n_ > 1 ? `${n_} aufs Handy holen` : "Aufs Handy holen"; });
  return box;
}


async function dateienFragen(text, pcs) {
  const g = z.gespraeche.aktuell;
  z.gespraeche.hinzufuegen({ rolle: "user", text }, g.kennung); speichern();
  const k = arbeitKnoten();
  z.laufend = { gespraech: g.kennung, knoten: k.d, kennung: "", abbrechen: false };
  knoepfeLaufend(true); zeichneVerlauf(); $("#eingabe").blur();
  k.schritt.textContent = pcs.length > 1 ? `sucht auf ${pcs.length} PCs in deinen Dateien …` : `sucht auf „${pcs[0].pc_name}“ in deinen Dateien …`;
  const nachrichten = [{ role: "user", content: text }];
  const eins = async (pc) => {
    try {
      const body = { nachrichten, auszuege: [], frisch: false, zuhause: await zuhause.unterschreiben(pc, nachrichten, undefined, "dateien") };
      const kennung = (await holen("/frage-stellen", { body, geraet: z.geraet })).kennung;
      const t0 = Date.now();
      while (Date.now() - t0 < 120000 && !z.laufend?.abbrechen) {
        await schlafen(1200);
        const r = await holen("/antwort/" + encodeURIComponent(kennung), { geraet: z.geraet });
        if (r.status === "fertig") return { pc, text: r.text || "", dateien: (r.lieferschein?.dateien || []).map((d) => ({ ...d, pc: pc.pc_name, kid: pc.kid })), ls: { ...(r.lieferschein || {}), ...(r.etikett ? { etikett: r.etikett } : {}) } };
        if (r.status === "verworfen") return { pc, text: r.grund || zuhause.herkunftSatz("aus"), dateien: [] };
      }
      return { pc, text: "Dein PC daheim hat nicht rechtzeitig geantwortet.", dateien: [] };
    } catch (e) { return { pc, text: e instanceof ServerFehler ? e.message : "Das hat nicht geklappt.", dateien: [] }; }
  };
  const alle = await Promise.all(pcs.map(eins));
  const text_ = alle.length === 1 ? alle[0].text : alle.map((a) => `${a.pc.pc_name}: ${a.text}`).join("\n\n");
  const dateien = alle.flatMap((a) => a.dateien);

  const ls0 = { ...(alle[0].ls || {}) }; if (alle.length !== 1) delete ls0.etikett;
  z.gespraeche.hinzufuegen({ rolle: "assistant", text: text_, lieferschein: { ...ls0, dateien }, dateien, daheim: dateien.length ? "dateien" : "", von: pcs.map((p) => p.pc_name).join(", ") }, g.kennung);
  z.laufend = null; knoepfeLaufend(false); speichern(); zeichneVerlauf(); zeichneListe();
}


async function dateienHolen(n, auswahl) {
  if (!auswahl.length) return;
  const je = new Map();
  for (const a of auswahl) je.set(a.kid, [...(je.get(a.kid) || []), a.id]);
  const dateien = [], fehler = [];
  status(auswahl.length > 1 ? `Holt ${auswahl.length} Dateien von daheim …` : "Holt die Datei von daheim …");
  for (const [kid, ids] of je) {
    const pc = z.zuhause.find((p) => p.kid === kid) || z.zuhause[0];
    if (!pc) { fehler.push("Dieses Handy ist mit keinem PC mehr gekoppelt."); continue; }
    try {

      let offen = ids, letzter = "";
      for (let runde = 0; runde < 10 && offen.length; runde++) {
        if (runde) status(offen.length === 1 ? "Holt 1 weitere Datei von daheim …" : `Holt ${offen.length} weitere Dateien von daheim …`);
        const nachrichten = [{ role: "user", content: JSON.stringify({ holen: offen }) }];
        const body = { nachrichten, auszuege: [], frisch: false, zuhause: await zuhause.unterschreiben(pc, nachrichten, undefined, "holen") };
        const kennung = (await holen("/frage-stellen", { body, geraet: z.geraet })).kennung;
        let r = null; const t0 = Date.now();
        while (Date.now() - t0 < 360000) {
          await schlafen(1200);
          r = await holen("/antwort/" + encodeURIComponent(kennung), { geraet: z.geraet });
          if (r.status === "fertig" || r.status === "verworfen") break;
        }
        if (r?.status !== "fertig") { fehler.push(r?.grund || "Dein PC daheim hat nicht rechtzeitig geantwortet."); break; }
        for (const e of r.lieferschein?.abholen || []) {
          const blob = await holenRoh("/zuhause-ablage/" + e.token, { geraet: z.geraet });
          const daten = await zuhause.dateiEntschluesseln(pc, e.id, blob);
          dateien.push(new File([daten], e.name, { type: zuhause.dateiArt(e.name) }));
        }
        offen = (r.lieferschein?.spaeter || []).slice(0, 20);
        letzter = r.text || "";
      }

      const rest = letzter.split(/(?<=\.)\s+/).filter((s) => /zu groß|älteren Suche|nicht geklappt/i.test(s));
      fehler.push(...rest);
    } catch (e) { fehler.push(e.message || "Das Holen hat nicht geklappt."); }
  }
  status([dateien.length === 1 ? "1 Datei geholt. Tipp auf „Sichern oder teilen“." : dateien.length ? `${dateien.length} Dateien geholt. Tipp auf „Sichern oder teilen“.` : "", ...fehler].filter(Boolean).join(" "));
  return dateien;
}


function dateienTeilen(dateien) {
  if (navigator.canShare?.({ files: dateien })) {
    navigator.share({ files: dateien }).catch(() => { });
    return;
  }
  for (const f of dateien) { const a = document.createElement("a"); a.href = URL.createObjectURL(f); a.download = f.name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 60000); }
}

const WO_SUCHEN = "Willst du in deinen Dateien suchen, tipp beim Fragen auf das Plus links neben dem Eingabefeld und wähle „In meinen Dateien suchen“.";
function daheimLeiste() {
  const da = !!z.zuhause.length && !!z.geraet;


  const an = da && $("#daheim-an").checked;
  $("#daheim-leiste").hidden = !an;
  const k = $("#btn-daheim-suchen");
  k.hidden = !da;
  k.setAttribute("aria-checked", String(an));
  k.querySelector("small").textContent = an ? "ist an, tippen zum Ausschalten" : "auf deinem PC daheim, nie im Internet";
  const sel = $("#daheim-pc");
  const wert = sel.value;
  sel.replaceChildren(...z.zuhause.map((p) => new Option(p.pc_name, p.kid)), ...(z.zuhause.length > 1 ? [new Option("alle PCs", "alle")] : []));
  sel.hidden = z.zuhause.length < 2;
  if ([...sel.options].some((o) => o.value === wert)) sel.value = wert;
}
function daheimPcs() {
  const v = $("#daheim-pc").value;
  return v === "alle" ? z.zuhause : [z.zuhause.find((p) => p.kid === v) || z.zuhause[0]];
}


const pruefbar = (n) => !n.fehler && !nurRueckfrage(n.lieferschein || {}) && !n.dateien && !(n.lieferschein || {}).dateien;


function detailsZeilen(n) {
  const ls = n.lieferschein || {}, pr = ls.pruefung || {}, aus = [];
  const zeile = (k, v) => { if (v) aus.push([k, v]); };
  zeile("Woher", ls.quellen || "");
  zeile("Quellen", (ls.quellen_liste || []).map((q) => q.titel).join("\n"));
  if (pr.saetze?.length && !nurRueckfrage(ls)) zeile("Geprüft", `${pr.gruen || 0} aus Quellen, ${pr.gelb || 0} Schlussfolgerungen, ${pr.rot || 0} ohne Quelle (Wortabgleich mit den Auszügen, keine Wahrheitsprüfung)`);
  zeile("Erarbeitet von", [n.von || "einem PC der Community", ls.modell, ls.dauer_s ? Number(ls.dauer_s).toFixed(1) + " s" : ""].filter(Boolean).join(", "));
  zeile("Skill", typeof ls.skill === "string" ? ls.skill.slice(0, 80) : "");
  zeile("Gemacht", ls.gemacht || "geantwortet");
  return aus;
}


const JA_KURZ = /^(ja|jo|jup|jawohl|gern|gerne|bitte|ja,? bitte|ja,? gerne|mach(?: das| nur)?|ok(?:ay)?|passt|yes|yes,? please|yeah|yep|sure|please|go)[.!]*$/i;

function liveAngebotFrage(g) {
  const ns = g?.nachrichten || [];
  const letzte = ns[ns.length - 1];
  if (!letzte || letzte.rolle === "user" || letzte.fehler || letzte.lieferschein?.angebot !== "nachpruefen") return "";
  const frage = ns.slice(0, -1).reverse().find((x) => x.rolle === "user");
  return frage ? String(frage.text).replace(/^Live nachprüfen: /, "") : "";
}

function metaKnoten(n, i, neueste) {
  const box = document.createDocumentFragment();
  const ls = n.lieferschein || {};
  if (ls.stand?.nachgeschaut) {
    const m = document.createElement("div"); m.className = "meta";
    m.textContent = `Stand: nachgeschaut am ${wann(ls.stand.nachgeschaut)} (${ls.stand.aus_gedaechtnis ? "aus dem Gedächtnis der Community" : "jetzt nachgeschaut"}${ls.stand.gilt_bis ? ", gilt bis " + wann(ls.stand.gilt_bis) : ""}).`;
    box.append(m);
  }


  if (ls.erste_fassung && !n.fehler) {
    const m = document.createElement("div"); m.className = "meta";
    m.textContent = ls.erste_fassung === "nachgeschaut" ? "Die erste Fassung passte nicht zu den Quellen, darum wurde im Internet nachgeschaut."
      : "Die erste Fassung passte nicht zu den Quellen und wurde verworfen.";
    box.append(m);
  }
  const mp = ls.mitglied_pruefung;
  if (mp) {
    const m = document.createElement("div"); m.className = "meta";
    const urteil = { stimmt: "stimmt", stimmt_nicht: "stimmt nicht", unsicher: "unsicher" }[mp.urteil] || mp.urteil || "";
    m.textContent = mp.status === "geprueft" ? `Von einem Mitglied geprüft${mp.pruefer_name ? " (" + mp.pruefer_name + ")" : ""}: ${urteil}${mp.kommentar ? " – „" + mp.kommentar + "“" : ""}` : "Ein Mitglied schaut nach, sobald jemand Zeit hat. Das Ergebnis kommt hierher.";
    box.append(m);
  }


  const akt = document.createElement("div"); akt.className = "aktionen";
  const gut = knopf("gut", "Gute Antwort"); gut.dataset.tun = "gut"; gut.setAttribute("aria-pressed", String(n.bewertung === "gut"));
  const schlecht = knopf("schlecht", "Antwort hat nicht gepasst"); schlecht.dataset.tun = "schlecht"; schlecht.setAttribute("aria-pressed", String(n.bewertung === "schlecht"));
  const kop = knopf("kopieren", "Kopieren"); kop.dataset.tun = "kopieren";
  akt.append(kop, gut, schlecht);
  if (pruefbar(n)) { const pr = knopf("pruefen", "Stimmt das? Prüfen"); pr.dataset.tun = "pruefen"; akt.append(pr); }
  if (neueste) { const noch = knopf("nochmal", "Nochmal fragen"); noch.dataset.tun = "nochmal"; akt.append(noch); }
  const mehr = knopf("mehr", "Mehr zu dieser Antwort"); mehr.dataset.tun = "mehr"; akt.append(mehr);
  const zahl = (ls.quellen_liste || []).length;
  if (zahl && !n.fehler) {
    const q = document.createElement("button"); q.type = "button"; q.className = "quellen-kapsel"; q.dataset.tun = "details";
    q.textContent = zahl === 1 ? "1 Quelle" : `${zahl} Quellen`;
  }


  if (neueste && ls.angebot === "nachpruefen" && !n.fehler) {
    const ja = document.createElement("button"); ja.type = "button"; ja.className = "knopf live-ja"; ja.dataset.tun = "nachpruefen";
    ja.append(symbol("suche"), document.createTextNode("Ja, live nachprüfen")); box.append(ja);
  }
  box.append(akt);
  if (n.daheim && zuhause.herkunftSatz(n.daheim)) {
    const h = document.createElement("p"); h.className = "leise klein daheim"; h.textContent = zuhause.herkunftSatz(n.daheim); box.append(h);
  }
  if (n.dateien?.length) box.append(dateienKnoten(n));
  return box;
}

function zeichneVerlauf() {
  $("#daheim-an").checked = !!z.gespraeche.aktuell?.dateien;
  daheimLeiste();
  const g = z.gespraeche.aktuell;
  skillSchild(g);
  const box = $("#nachrichten"); box.replaceChildren();
  const leer = !g.nachrichten.length && !z.laufend;
  document.body.classList.toggle("leer", leer);
  $("#willkommen").hidden = !leer;
  $("#willkommen-text").textContent = willkommen();
  $("#einrichten").hidden = !leer || !!z.einst.eingerichtet || !z.geraet;
  $("#btn-heim").textContent = g.nachrichten.length ? z.gespraeche.titel(g) : "KIplatz"; $("#btn-heim").translate = !g.nachrichten.length;
  let letzte = -1; g.nachrichten.forEach((n, i) => { if (n.rolle !== "user") letzte = i; });
  g.nachrichten.forEach((n, i) => {
    const d = document.createElement("article"); d.className = "msg " + n.rolle + (n.fehler ? " fehler" : ""); d.dataset.i = i;
    if (n.rolle === "user") {
      d.translate = false;
      d.textContent = n.text;

      if (n.anhaenge?.length) {
        const a = document.createElement("div"); a.className = "msg-anhaenge";
        for (const x of n.anhaenge) { const s = document.createElement("span"); s.className = "anhang-klein"; s.append(symbol("anhang"), document.createTextNode(x.name)); a.append(s); }
        d.append(a);
      }
    }
    else {
      const w = document.createElement("div"); w.className = "who"; w.textContent = "KIplatz";
      const b = document.createElement("div"); b.className = "body";
      if (!n.fehler) b.translate = false;
      antwortZeichnen(b, n.text);

      if (!n.fehler) { d.dataset.ki = "erzeugt"; if (n.lieferschein?.etikett?.unterschrift) d.dataset.kiplatzEtikett = JSON.stringify(n.lieferschein.etikett); }
      d.append(w, b, metaKnoten(n, i, i === letzte));
    }
    box.append(d);
  });
  if (z.laufend && z.laufend.gespraech === g.kennung) box.append(z.laufend.knoten);

  if (leer && !$("#einrichten").hidden) $("#verlauf").scrollTop = 0; else runter();
}
const runter = () => { const v = $("#verlauf"); v.scrollTop = v.scrollHeight; };
const nahUnten = () => { const v = $("#verlauf"); return v.scrollHeight - v.scrollTop - v.clientHeight < 48; };


function standortHolen() {
  if (!navigator.geolocation) return Promise.resolve({ pos: null, nein: false });
  const erlaubt = ablageLesen("standort-erlaubt", false);
  if (!erlaubt) status("Bitte erlaube, dass KIplatz deinen ungefähren Standort verwenden darf.");
  return new Promise((ok) => navigator.geolocation.getCurrentPosition(
    (pos) => { ablageSchreiben("standort-erlaubt", true); ok({ pos, nein: false }); },
    (e) => { if (e?.code === 1) ablageSchreiben("standort-erlaubt", false); ok({ pos: null, nein: e?.code === 1 }); },
    { timeout: erlaubt ? 8000 : 60000, maximumAge: 600000 }));
}

async function ortErmitteln() {
  const m = ablageLesen("ort", null);
  if (m?.name && Date.now() - m.zeit < 3600000) return m.name;
  if (!navigator.geolocation) return "";
  if (ablageLesen("standort-erlaubt", false)) status("Standort wird ermittelt …");
  const { pos, nein } = await standortHolen();
  if (!pos) { status(nein ? "Ohne deine Erlaubnis kein Standort. Schreib den Ort einfach dazu." : "Ich konnte deinen Standort nicht finden. Schreib den Ort einfach dazu."); return ""; }


  if (!z.geraet) { status("Schreib den Ort einfach dazu."); return ""; }
  try {
    const r = await holen("/ort", { body: { lat: Number(pos.coords.latitude.toFixed(2)), lon: Number(pos.coords.longitude.toFixed(2)) }, geraet: z.geraet });
    const name = String(r?.ort || "").slice(0, 80);
    if (name) ablageSchreiben("ort", { name, zeit: Date.now() });
    return name;
  } catch { return ""; }
}

function arbeitKnoten() {
  const d = document.createElement("article"); d.className = "msg assistant warte";
  const w = document.createElement("div"); w.className = "who"; w.textContent = "KIplatz";
  const b = document.createElement("div"); b.className = "body"; b.translate = false;


  const ent = document.createElement("div"); ent.className = "entwurf-hinweis"; ent.textContent = "Entwurf, wird geprüft"; ent.hidden = true;
  const a = document.createElement("div"); a.className = "arbeit"; a.setAttribute("role", "status"); a.setAttribute("aria-live", "polite");
  const img = document.createElement("img"); img.src = "marke/symbol-64.png"; img.alt = "";
  const zeit = document.createElement("span"); zeit.className = "zeit"; zeit.textContent = "0 s";
  const tr = document.createElement("span"); tr.setAttribute("aria-hidden", "true"); tr.textContent = "·";
  const schritt = document.createElement("span"); schritt.className = "schritt";
  a.append(img, zeit, tr, schritt); d.append(w, ent, b, a);
  return { d, b, ent, zeit, schritt };
}

function knoepfeLaufend(an) { $("#btn-senden").hidden = an; $("#btn-stopp").hidden = !an; }

async function fragen(text, { frisch = false, wiederholen = false, anhaenge = null, vorige = "", netz = false } = {}) {
  if (!text || z.laufend || z.sperre) return;
  const g = z.gespraeche.aktuell;

  if (!frisch && !wiederholen && !anhaenge?.length && !z.anhaenge.length && JA_KURZ.test(String(text).trim())) {
    const vorige_ = liveAngebotFrage(g);
    if (vorige_) { text = vorige_; frisch = true; }
  }
  if (!frisch && !wiederholen) {

    const mitWohnort = mitOrt(text, z.einst.wohnort);
    if (mitWohnort) { text = mitWohnort; status(`Ort: ${sauber(z.einst.wohnort, 60)} (aus „Meine KI“)`); }
    else if (z.einst.standort && WETTER.test(text) && !MIT_ORT.test(text)) {
      const ort = await ortErmitteln();
      if (ort) { text = text.replace(/[?.!\s]+$/, "") + ` in ${ort}?`; status(`Standort: ${ort}`); }
    }

    const m = anhang.nachricht(text, anhaenge || []);
    const neu = { rolle: "user", text: m.text };
    if (m.mit) { neu.mit = m.mit; neu.anhaenge = anhaenge.map((a) => ({ name: a.name, zeichen: a.text.length })); }
    if (m.gekuerzt.length) status(m.gekuerzt.map((x) => `„${x.name}“ ging gekürzt mit (${x.zeichen.toLocaleString(kiplatzSprache.datumSprache())} von ${x.von.toLocaleString(kiplatzSprache.datumSprache())} Zeichen).`).join(" "));
    z.gespraeche.hinzufuegen(neu, g.kennung);
    speichern();
  }
  nativ?.tippen();
  const k = arbeitKnoten();
  z.laufend = { gespraech: g.kennung, knoten: k.d, kennung: "", abbrechen: false };
  knoepfeLaufend(true); zeichneVerlauf(); $("#eingabe").blur();
  const beginn = Date.now();
  const uhr = setInterval(() => { k.zeit.textContent = Math.round((Date.now() - beginn) / 1000) + " s"; }, 1000);
  k.schritt.textContent = frisch ? "prüft live im Netz nach …" : "schickt deine Frage an die Community …";
  let ergebnis;
  try {

    const verlauf = anhang.verlaufBauen(g.nachrichten);
    if (frisch) verlauf.push({ role: "user", content: text });


    const skMit = skillAblage.fuerGespraech(g.skill).mit;
    const sk = skMit.length ? skillAblage.alsEine(skMit) : null;


    const fg = skillAblage.holen(meineKi.NAME) ? meineKi.fachgebiete(z.einst.meineKi) : [];
    const body = { nachrichten: verlauf, auszuege: [], frisch, ...(sk ? { skill: { name: sk.name, text: sk.text } } : {}), ...(vorige ? { vorige } : {}), ...(fg.length ? { fachgebiete: fg } : {}) };


    void netz;
    z.laufend.kennung = (await holen("/frage-stellen", { body, geraet: z.geraet })).kennung;
    const t0 = Date.now(); let r = null; let seit = ""; let aussetzer = 0;
    while (Date.now() - t0 < 240000 && !z.laufend.abbrechen) {


      const weg = "/antwort/" + encodeURIComponent(z.laufend.kennung) + "?warten=15" + (seit ? "&seit=" + encodeURIComponent(seit) : "");
      try { r = await holen(weg, { geraet: z.geraet, zeitlimit: 30000 }); }
      catch (e) { if (z.laufend.abbrechen) break; if (++aussetzer >= 3) throw e; await schlafen(1500); continue; }
      aussetzer = 0;
      if (z.laufend.abbrechen) break;
      seit = r.stand || "";
      if (r.status === "fertig" || r.status === "verworfen") break;
      const folgen = nahUnten();
      if (r.status === "genommen") {


        k.ent.hidden = true;
        k.schritt.textContent = r.schritt || "ein PC aus der Community erarbeitet deine Antwort …";
      }
      else k.schritt.textContent = r.vor_dir ? `wartet auf einen freien PC (${r.vor_dir} vor dir) …` : "wartet auf einen freien PC …";
      if (g.kennung === z.gespraeche.aktuellId && folgen) runter();
    }
    if (z.laufend.abbrechen) ergebnis = { rolle: "assistant", text: "Angehalten.", lieferschein: {}, fehler: true };
    else if (r?.status === "fertig") ergebnis = { rolle: "assistant", text: r.text || "(keine Antwort erhalten)", lieferschein: { ...(r.lieferschein || {}), ki_erzeugt: true, ...(r.etikett ? { etikett: r.etikett } : {}) }, von: r.von || "", auftrag: z.laufend.kennung,
      ...(body.zuhause ? { daheim: r.zuhause ? (r.lieferschein?.zuhause === "mit_unterlagen" ? "daheim" : "daheim_ohne") : "aus" } : {}),
      ...(r.lieferschein?.dateien?.length ? { dateien: r.lieferschein.dateien.map((d) => ({ ...d, pc: z.zuhause[0]?.pc_name || "", kid: z.zuhause[0]?.kid || "" })) } : {}) };
    else ergebnis = { rolle: "assistant", text: r?.grund ? r.grund.charAt(0).toUpperCase() + r.grund.slice(1) : "Gerade sind alle PCs der Community beschäftigt. Probier es bitte in ein paar Minuten noch einmal.", lieferschein: {}, fehler: true };
  } catch (e) {
    ergebnis = { rolle: "assistant", text: e instanceof ServerFehler ? e.message : "Das hat nicht geklappt.", lieferschein: {}, fehler: true };
    if (e.status === 401) status("Dieses Handy ist abgemeldet. Melde dich bitte einfach neu an.");
  }
  clearInterval(uhr);


  const hier = g.kennung === z.gespraeche.aktuellId && k.d.isConnected && !nahUnten() ? k.b.getBoundingClientRect().top : null;
  if (frisch) z.gespraeche.hinzufuegen({ rolle: "user", text: "Live nachprüfen: " + text }, g.kennung);
  z.gespraeche.hinzufuegen(ergebnis, g.kennung);
  z.laufend = null; knoepfeLaufend(false); speichern(); zeichneVerlauf(); zeichneListe(); stand();
  const neu = hier === null ? null : [...$("#nachrichten").querySelectorAll("article.msg.assistant .body")].pop();
  if (neu) $("#verlauf").scrollTop += neu.getBoundingClientRect().top - hier;
}


function anhaengeZeichnen() {
  const box = $("#anhaenge");
  box.replaceChildren();
  for (const [i, a] of z.anhaenge.entries()) {
    const c = document.createElement("span"); c.className = "anhang-chip";
    const n = document.createElement("span"); n.className = "anhang-name"; n.textContent = a.name;

    const info = document.createElement("span"); info.className = "anhang-info"; const art = document.createElement("span"); art.textContent = a.info; const laenge = document.createElement("span"); laenge.textContent = `${a.text.length.toLocaleString(kiplatzSprache.datumSprache())} Zeichen`; info.append(art, ", ", laenge);
    const x = document.createElement("button"); x.type = "button"; x.className = "anhang-weg"; x.setAttribute("aria-label", `„${a.name}“ entfernen`); x.append(symbol("zu"));
    x.onclick = () => { z.anhaenge.splice(i, 1); anhaengeZeichnen(); };
    c.append(symbol(a.art === "bild" ? "foto" : "datei"), n, info, x);
    box.append(c);
  }
  box.hidden = !z.anhaenge.length;

  $("#anhang-hinweis").hidden = !z.anhaenge.length;
}

async function anhaengeLesen(dateien) {
  for (const datei of dateien) {
    if (z.anhaenge.length >= anhang.MAX_ANHAENGE) { status(`Höchstens ${anhang.MAX_ANHAENGE} Dateien je Frage.`); break; }
    z.anhangLiest = true; $("#btn-plus").disabled = true;
    status(`„${datei.name}“ wird gelesen …`);
    try {
      const a = await anhang.lesen(datei, (t) => statusDauerhaft(t));
      z.anhaenge.push(a);
      status(`„${a.name}“ gelesen. Frag jetzt etwas dazu.`);
    } catch (e) {
      status(e instanceof anhang.AnhangFehler ? e.message : `„${datei.name}“ ließ sich nicht lesen.`);
    } finally {
      statusDauerhaft(""); z.anhangLiest = false; $("#btn-plus").disabled = false; anhaengeZeichnen();
    }
  }
}

function anhaengeVerdrahten() {
  const menue = $("#plus-menue");
  const zu = () => { menue.hidden = true; $("#btn-plus").setAttribute("aria-expanded", "false"); };
  $("#btn-plus").onclick = (e) => { e.stopPropagation(); menue.hidden = !menue.hidden; $("#btn-plus").setAttribute("aria-expanded", String(!menue.hidden)); };
  document.addEventListener("click", (e) => { if (!menue.hidden && !e.target.closest("#plus-menue")) zu(); });
  $("#datei-waehlen").accept = anhang.DATEI_ARTEN.join(",");
  $("#btn-datei").onclick = () => { zu(); $("#datei-waehlen").click(); };
  $("#btn-foto").onclick = () => { zu(); $("#foto-waehlen").click(); };

  $("#btn-plus-skills").onclick = () => { zu(); if (z.gespraeche.aktuell) skillWaehlen(z.gespraeche.aktuell); };
  for (const id of ["#datei-waehlen", "#foto-waehlen"]) {
    $(id).onchange = async (e) => { const f = [...e.target.files]; e.target.value = ""; await anhaengeLesen(f); };
  }
  anhaengeZeichnen();
}

let sprechen = null;
function sprechenVerdrahten() {
  const knopf = $("#btn-mikro");
  const hinweis = $("#sprechen-hinweis");
  sprechen = new Sprechen({
    melden: (phase, text) => {
      knopf.classList.toggle("aufnahme", phase === "aufnahme");
      knopf.setAttribute("aria-pressed", String(phase === "aufnahme"));
      knopf.setAttribute("aria-label", phase === "aufnahme" ? "Aufnahme beenden" : "Sprechen statt tippen");
      knopf.disabled = phase === "erkennen" || phase === "holen";
      hinweis.textContent = text || "";
      hinweis.hidden = !text;
    },
    text: (t) => {
      const ta = $("#eingabe");
      ta.value = sprAnhaengen(ta.value, t);
      ta.dispatchEvent(new Event("input"));
      ta.focus();
    },
  });
  knopf.onclick = async () => {

    if (!ablageLesen("sprache-geholt", false) && sprechen.phase !== "aufnahme") {
      if (!confirm(`Für Sprechen statt Tippen holt KIplatz einmal die Spracherkennung von kiplatz.at (${SPRACHE_MB} MB). Danach versteht dein Handy dich ohne Internet, und dein Ton verlässt das Handy nie. Jetzt holen?`)) return;
      ablageSchreiben("sprache-geholt", true);
    }
    nativ?.tippen();
    sprechen.druecken();
  };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sprechen?.phase === "aufnahme") sprechen.verwerfen(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden && sprechen?.phase === "aufnahme") sprechen.verwerfen(); });
}

async function anhalten() {
  if (!z.laufend) return;
  z.laufend.abbrechen = true;
  const k = z.laufend.kennung;
  if (k) { try { await holen("/frage-aufgeben", { body: { kennung: k }, geraet: z.geraet }); } catch { } }
}


async function pruefStand() {
  const g = z.gespraeche.aktuell;
  const offen = g.nachrichten.map((n) => n.lieferschein?.mitglied_pruefung).filter((p) => p && p.status === "offen");
  if (!offen.length || !z.geraet) return;
  try {
    const r = await holen("/pruefung-stand", { body: { kennungen: offen.map((p) => p.kennung) }, geraet: z.geraet });
    let neu = 0;
    for (const p of offen) if (r.stand?.[p.kennung]?.status === "geprueft") { Object.assign(p, r.stand[p.kennung]); neu++; }
    if (neu) { speichern(); zeichneVerlauf(); }
  } catch { }
}


async function neueFassung() {
  if (nativ || document.visibilityState !== "visible") return;
  try {
    const r = await fetch(new URL("version.js", import.meta.url).href + "?t=" + Date.now(), { cache: "no-store", credentials: "omit" });
    const dort = ((await r.text()).match(/APP_VERSION = "([^"]+)"/) || [])[1];
    if (!r.ok || !dort || dort === APP_VERSION) return;
    const beschaeftigt = z.laufend || z.anhangLiest || z.anhaenge.length || $("#eingabe").value.trim() || ["holen", "aufnahme", "erkennen"].includes(sprechen?.phase);
    if (!beschaeftigt) location.reload();
  } catch { }
}

async function stand() {
  if (!z.geraet) return;
  try {
    const s = await holen("/rechenstand", { geraet: z.geraet });
    const fr = s.fragen || {};
    const on = Number(fr.rechner_da ?? fr.rechner_online ?? 0);
    statusDauerhaft(on === 1 ? "1 Gerät online" : `${on} Geräte online`);
  } catch { statusDauerhaft("Server gerade nicht erreichbar"); }
}


async function appStand() {
  let s = null;
  try { s = await holen("/app-stand", { zeitlimit: 8000 }); } catch { return; }
  const b = standBewerten(s);
  const laden = nativ?.plattform === "android" ? b.laden?.android : b.laden?.ios;
  if (b.art === "sperre") {
    z.sperre = true;
    $("#sperre-text").textContent = b.text;
    if (laden && /^https:\/\//.test(laden)) { $("#sperre-laden").href = laden; $("#sperre-laden").hidden = false; }
    $("#sperre").hidden = false;
  } else if (b.art === "hinweis" && ablageLesen("hinweis-weg", "") !== s.neueste) {
    $("#hinweis-text").textContent = b.text;
    $("#hinweis").hidden = false;
    $("#btn-hinweis-zu").onclick = () => { $("#hinweis").hidden = true; ablageSchreiben("hinweis-weg", s.neueste); };
  }
}


const ANMELDUNG = "anmeldung";
const ANMELDUNG_FRIST_MS = 10 * 60 * 1000;

function zufallsnummer(bytes = 32) {
  const b = new Uint8Array(bytes);
  crypto.getRandomValues(b);
  return btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function geraeteArt() {
  const ua = navigator.userAgent;
  if (/iPad/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)) return "iPad";
  if (/iPhone|iPod/.test(ua)) return "iPhone";
  if (/Android/.test(ua)) return /Mobile/.test(ua) ? "Android-Handy" : "Android-Tablet";
  if (/Macintosh/.test(ua)) return "Mac";
  return "Handy";
}

function anmeldeInfo(text) { $("#anmelde-info").textContent = text || ""; $("#anmelde-info").hidden = !text; }


let emailAdresse = "";


function emailFehler(feld, text) {
  const p = $(feld === "code" ? "#code-fehler" : "#adresse-fehler");
  p.textContent = text || ""; p.hidden = !text;
  if (text) p.scrollIntoView({ block: "nearest" });
}

function emailSchritt(schritt) {
  emailFehler("code", ""); emailFehler("adresse", "");
  $("#btn-konto").hidden = !!schritt;
  $("#email-form").hidden = schritt !== "adresse";
  $("#code-form").hidden = schritt !== "code";
  if (schritt === "adresse") $("#email-adresse").focus();
  if (schritt === "code") { $("#email-code").value = ""; $("#email-code").focus(); }
}

async function emailCodeSchicken() {
  const adresse = $("#email-adresse").value.trim();
  $("#anmelde-fehler").textContent = ""; anmeldeInfo("");
  emailFehler("adresse", "");
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(adresse)) { emailFehler("adresse", "Das sieht nicht wie eine E-Mail-Adresse aus."); $("#email-adresse").focus(); return; }
  $("#btn-email-code").disabled = true; $("#btn-email-neu").disabled = true;
  try {
    await holen("/konto-code", { body: { adresse } });
    emailAdresse = adresse;
    $("#code-info").textContent = `Wir haben einen Code an ${adresse} geschickt. Er gilt 10 Minuten. Kommt keine Mail, schau im Spam-Ordner nach. Nimm den Code aus der neuesten Mail an genau diese Adresse.`;
    emailSchritt("code");
  } catch (e) { emailFehler($("#code-form").hidden ? "adresse" : "code", e.message); }
  finally { $("#btn-email-code").disabled = false; $("#btn-email-neu").disabled = false; }
}


const iphoneHeim = () => !nativ && navigator.standalone === true;


const FENSTER_NAME = "kiplatz-anmeldung", FENSTER_MARKE = "kiplatz.anmeldefenster";


let anmeldefensterErkannt = false;
function anmeldeFenster() {
  if (!iphoneHeim()) return null;
  const marke = (an) => { try { if (an) sessionStorage.setItem(FENSTER_MARKE, "1"); else sessionStorage.removeItem(FENSTER_MARKE); } catch { } };
  marke(true);
  try {
    const f = window.open("about:blank", "_blank");
    if (f) { try { f.name = FENSTER_NAME; } catch { } f.opener = null; }
    return f;
  } catch { return null; } finally { marke(false); }
}
function istAnmeldefenster() {
  if (nativ) return false;
  if (anmeldefensterErkannt || window.name === FENSTER_NAME) return true;
  try { return sessionStorage.getItem(FENSTER_MARKE) === "1"; } catch { return false; }
}
function fensterFertig() {
  const fenster = istAnmeldefenster();
  $("#ff-text").textContent = fenster ? "Tipp oben links auf ✕. Dann bist du in KIplatz angemeldet."
    : "Schließ dieses Fenster und geh zurück zu KIplatz, dort geht es weiter.";
  $("#ff-zu").hidden = !fenster;
  $("#fenster-fertig").hidden = false;
  if (fenster) setTimeout(() => { try { window.close(); } catch { } }, 800);
}

async function emailCodePruefen() {
  const code = $("#email-code").value.replace(/\D/g, "");
  $("#anmelde-fehler").textContent = "";
  emailFehler("code", "");
  if (code.length !== 6) { emailFehler("code", "Der Code hat 6 Ziffern."); $("#email-code").focus(); return; }
  if ($("#btn-email-pruefen").disabled) return;
  $("#btn-email-pruefen").disabled = true;
  const fenster = anmeldeFenster();
  try {
    const d = await holen("/konto-code-pruefen", { body: { adresse: emailAdresse, code } });
    anmeldeInfo("Der Code stimmt. Gleich bist du angemeldet …");
    await kontoAnmelden("", "email", d.sitzung, fenster);
  } catch (e) {
    if (fenster && !fenster.closed) fenster.close();
    emailFehler("code", e.message);

    if (e.code === "CODE_ABGELAUFEN") { $("#email-code").value = ""; $("#btn-email-neu").focus(); } else $("#email-code").select();
  }
  finally { $("#btn-email-pruefen").disabled = false; }
}

async function kontoAnmelden(zweck = "", anbieter = "", sitzung = "", fenster = null) {
  $("#anmelde-fehler").textContent = ""; anmeldeInfo("");
  const ticket = zufallsnummer();
  ablageSchreiben(ANMELDUNG, { ticket, zeit: Date.now(), zweck });


  try { sessionStorage.setItem("kiplatz.anmeldung-hier", ticket); } catch { }
  try {


    const rueckkehr = nativ ? "https://kiplatz.at/app/" : location.origin + location.pathname;
    const d = await holen("/konto-start", { body: { ticket, rueckkehr, zweck, ...(anbieter ? { anbieter } : {}), ...(sitzung ? { sitzung } : {}) } });

    if (d.state) ablageSchreiben(ANMELDUNG, { ticket, zeit: Date.now(), zweck, state: String(d.state), fenster: !!(fenster && !fenster.closed) });
    if (!/^https:\/\//.test(String(d.adresse || "")) && !ENTWICKLUNG) throw new ServerFehler("Die Anmeldeseite hat eine unsichere Adresse.");


    if (fenster && !fenster.closed) {

      fenster.location.href = d.adresse;
      anmeldeInfo("Bestätige die Anmeldung im Fenster darüber und schließ es danach. Du bist dann hier angemeldet.");
      kontoAbholen();
      return;
    }
    location.replace(d.adresse);
  } catch (e) {
    if (fenster && !fenster.closed) fenster.close();
    localStorage.removeItem("kiplatz." + ANMELDUNG);
    $("#anmelde-fehler").textContent = e.message;
    if (zweck === "loeschen") $("#ld-meldung").textContent = e.message;
  }
}


async function kontoRueckkehr(suche = null) {
  const q = new URLSearchParams(suche ?? location.search);
  const state = q.get("state"), code = q.get("code"), fehler = q.get("error");
  if (!state || !(code || fehler)) return false;
  const begonnen = ablageLesen(ANMELDUNG, null);
  if (begonnen?.fenster && begonnen.state && begonnen.state === state) anmeldefensterErkannt = true;
  if (suche === null) history.replaceState(null, "", location.pathname);
  if (fehler) {
    $("#anmelde-fehler").textContent = "Die Anmeldung wurde abgebrochen.";
    if (ablageLesen(ANMELDUNG, null)?.zweck === "loeschen") { localStorage.removeItem("kiplatz." + ANMELDUNG); loeschenStart(); $("#ld-meldung").textContent = "Abgebrochen, es wurde nichts gelöscht."; }
    return true;
  }
  let antwort;
  try {
    antwort = await holen("/konto-zurueck", { body: { state, code, art: geraeteArt() } });
  } catch (e) {
    const loeschen = ablageLesen(ANMELDUNG, null)?.zweck === "loeschen";
    localStorage.removeItem("kiplatz." + ANMELDUNG);
    $("#anmelde-fehler").textContent = e.message;
    if (loeschen) { loeschenStart(); $("#ld-meldung").textContent = e.message; }
    return true;
  }
  if (antwort?.zweck === "loeschen" && antwort.frage) { loeschenFrage(state, antwort); return true; }


  const offen = ablageLesen(ANMELDUNG, null);
  if (antwort?.frage && offen?.state && offen.state === state && offen.zweck !== "loeschen") {
    anmeldeFrageOffen = { state, frage: String(antwort.frage) };
    try { await holen("/konto-zurueck", { body: { state, frage: String(antwort.frage), ja: true } }); }
    catch (e) { anmeldeFrageOffen = null; $("#anmelde-fehler").textContent = e.message; localStorage.removeItem("kiplatz." + ANMELDUNG); return true; }
    anmeldeFrageOffen = null;


    if (!hierBegonnen()) { fensterFertig(); return true; }
    kontoAbholen();
    return true;
  }
  if (antwort?.frage) { anmeldenFrage(state, antwort); return true; }
  if (!hierBegonnen()) fensterFertig();
  return true;
}


let anmeldeFrageOffen = null;


const mitBenutzer = (konto, benutzer) => !!benutzer && benutzer.toLowerCase() !== konto.toLowerCase();
const nameMitBenutzer = (konto, benutzer) => (mitBenutzer(konto, benutzer) ? `„${konto}“ (Benutzername ${benutzer})` : `„${konto}“`);


const PC_SYSTEM = { "Windows-PC": "Windows", "Linux-PC": "Linux", "Mac": "macOS" };
function anmeldenFrage(state, r) {
  anmeldeFrageOffen = { state, frage: String(r.frage || "") };
  const wer = nameMitBenutzer(String(r.konto || ""), String(r.benutzer || ""));
  const pc = Object.hasOwn(PC_SYSTEM, String(r.geraet || "")) ? PC_SYSTEM[String(r.geraet)] : "";
  $("#af-titel").textContent = pc ? "PC verbinden" : "Anmelden";
  $("#af-wer").textContent = pc ? `Einen neuen PC (${pc}) mit dem Konto ${wer} verbinden?` : `Mit dem Konto ${wer} anmelden?`;
  $("#af-hinweis").textContent = pc ? "Hast du das nicht gerade selbst im KIplatz-Programm an deinem PC begonnen, dann tipp auf „Nein“."
    : "Hast du die Anmeldung nicht selbst in KIplatz angetippt, dann tipp auf „Nein“.";
  $("#af-ja").textContent = pc ? "Ja, verbinden" : "Ja, anmelden";
  $("#af-meldung").textContent = ""; $("#af-knoepfe").hidden = false;
  $("#af-ja").disabled = $("#af-nein").disabled = false;
  const dlg = $("#anmelde-frage");
  if (!dlg.open) dlg.showModal();
}
async function anmeldenAntworten(ja) {
  const f = anmeldeFrageOffen, m = $("#af-meldung");
  if (!f) return;
  $("#af-ja").disabled = $("#af-nein").disabled = true;
  m.textContent = "Einen Moment …";
  let r;
  try { r = await holen("/konto-zurueck", { body: { state: f.state, frage: f.frage, ja } }); }
  catch (e) { anmeldeFrageOffen = null; $("#af-knoepfe").hidden = true; m.textContent = e.message; localStorage.removeItem("kiplatz." + ANMELDUNG); return; }
  anmeldeFrageOffen = null;
  if (!ja) localStorage.removeItem("kiplatz." + ANMELDUNG);
  if (ja && hierBegonnen()) { $("#anmelde-frage").close(); kontoAbholen(); return; }
  $("#af-knoepfe").hidden = true;
  m.textContent = r.text || "";
}

function hierBegonnen() {
  if (istAnmeldefenster()) return false;
  const offen = ablageLesen(ANMELDUNG, null);
  try { return !!offen?.ticket && sessionStorage.getItem("kiplatz.anmeldung-hier") === offen.ticket; } catch { return false; }
}
const imHomeBildschirm = () => !!navigator.standalone || matchMedia("(display-mode: standalone)").matches;

let abholenLaeuft = false;

async function kontoAbholen() {
  if (istAnmeldefenster()) return;
  const offen = ablageLesen(ANMELDUNG, null);
  if (abholenLaeuft || !offen?.ticket) return;
  const loeschen = offen.zweck === "loeschen";
  if (z.geraet && !loeschen) return;

  if (!hierBegonnen() && !(imHomeBildschirm() || nativ)) return;
  if (Date.now() - (offen.zeit || 0) > ANMELDUNG_FRIST_MS) { localStorage.removeItem("kiplatz." + ANMELDUNG); return; }
  abholenLaeuft = true;
  if (!loeschen) anmeldeInfo(iphoneHeim() ? "Bestätige die Anmeldung im Fenster darüber und schließ es danach. Du bist dann hier angemeldet." : "Anmeldung läuft …");
  let neueNummer = false;
  try {

    for (let erstes = true; erstes || ((loeschen || !z.geraet) && Date.now() - offen.zeit < ANMELDUNG_FRIST_MS && document.visibilityState === "visible"); erstes = false) {

      if (ablageLesen(ANMELDUNG, null)?.ticket !== offen.ticket) { neueNummer = true; return; }
      let r;
      try { r = await holen("/konto-ergebnis", { body: { ticket: offen.ticket } }); }
      catch (e) {
        if (e.status === 404) {
          const nochOffen = ablageLesen(ANMELDUNG, null)?.ticket === offen.ticket;
          localStorage.removeItem("kiplatz." + ANMELDUNG); anmeldeInfo("");
          if (nochOffen && !loeschen) $("#anmelde-fehler").textContent = "Die Anmeldung hat zu lange gedauert. Probier es bitte noch einmal.";
          return;
        }
        r = null;
      }
      if (r?.status === "fertig" && r.zweck === "loeschen") {
        localStorage.removeItem("kiplatz." + ANMELDUNG);
        try { sessionStorage.removeItem("kiplatz.anmeldung-hier"); } catch { }
        anmeldeInfo("");
        loeschenBestaetigen(r);
        return;
      }
      if (r?.status === "fertig") {
        const hier = await geraetMerken({ ...r, angemeldet: new Date().toISOString(), ort: nativ ? "App" : imHomeBildschirm() ? "Home-Bildschirm" : "Browser" }, r.name);
        localStorage.removeItem("kiplatz." + ANMELDUNG);
        try { sessionStorage.removeItem("kiplatz.anmeldung-hier"); } catch { }
        if (!hier) return;
        anmeldeInfo("");
        anzeigen();
        status(`Angemeldet als ${r.konto || r.name}`);


        return;
      }
      await schlafen(2000);
    }
  } finally { abholenLaeuft = false; if (neueNummer) kontoAbholen(); }
}


async function geraetMerken(d, name) {
  const neu = { kennung: String(d.kennung), schluessel: String(d.schluessel), name: String(d.name || name || "Handy"),
    konto: String(d.konto || ""), benutzer: String(d.benutzer || ""), angemeldet: String(d.angemeldet || new Date().toISOString()), ort: String(d.ort || "") };


  const da = konten.doppelt(neu);
  if (da) {
    try { await holen("/geraet-abmelden", { body: { kennung: neu.kennung }, geraet: neu, zeitlimit: 8000 }); } catch { }
    konten.wechseln(da.fach, `Mit ${konten.anzeige(da)} warst du hier schon angemeldet.`);
    return false;
  }

  if (konten.fremdesFach(neu)) {
    konten.inNeuesFach();
    await tresor.schreiben("geraet", neu);
    konten.merken(neu);
    konten.wechseln(konten.aktivesFach(), `Angemeldet als ${neu.konto || neu.name}.`);
    return false;
  }
  z.geraet = neu;
  await tresor.schreiben("geraet", z.geraet);
  konten.merken(z.geraet);
  return true;
}

async function mitAnmeldecode(text) {
  const m = /[#&?]c=([A-Za-z0-9-]{4,16})\b/.exec(String(text || "").trim());
  if (!m) return false;
  const d = await holen("/geraet-mit-anmeldecode", { body: { code: m[1] } });
  await geraetMerken(d, d.name);
  return true;
}

function codeAusLink(text) {
  try { const u = new URL(text); return (u.searchParams.get("code") || "").toUpperCase(); } catch { return ""; }
}


async function linkVonAussen(url) {
  if (/[#&]zuhause=/.test(url)) { await zuhauseVonLink(url); return; }

  const pcCode = PC_QR.exec(String(url).trim());
  if (pcCode) { history.replaceState(null, "", location.pathname + location.search); await pcAnmelden(pcCode[1], true); return; }

  let u = null;
  try { u = new URL(url); } catch { }
  if (u && u.origin === "https://kiplatz.at" && u.pathname.startsWith("/app")) {
    const state = u.searchParams.get("state");
    if (state) {


      if (ablageLesen(ANMELDUNG, null)?.state === state) await kontoRueckkehr(u.search);
      else anmeldeInfo("Dieser Anmeldelink kommt nicht aus dieser App. Melde dich hier selbst an.");
      return;
    }

    if (u.hash === "#admin" && z.geraet) { einstellungenAuf(); adminZeichnen(true); return; }
    if (u.hash === "#konto-loeschen") { loeschenStart(); return; }
  }
  if (z.geraet) return;
  try {

    if (/[#&?]c=/.test(url) && !confirm("Mit diesem Anmeldelink anmelden? Nur, wenn du ihn selbst auf deinem anderen Gerät kopiert hast.")) return;
    if (await mitAnmeldecode(url)) { anzeigen(); return; }
  } catch (e) { $("#anmelde-fehler").textContent = e.message; return; }
  const c = codeAusLink(url);
  if (c) { $("#code").value = c; $("#name").focus(); }
}

function anzeigen() {
  $("#anmelden").hidden = !!z.geraet;
  $("#k-wiki").hidden = !z.geraet; $("#k-bestenliste").hidden = !z.geraet;
  $("#k-pc-qr").hidden = !z.geraet?.konto;
  $("#k-mithelfen").hidden = !z.geraet;
  if (!z.geraet) kontenZeichnen($("#anmelden-konten"), $("#karte-andere-konten"));
  if (z.geraet) { zeichneListe(); zeichneVerlauf(); stand(); pruefStand(); }
}


function kontenZeichnen(ul, karte) {
  if (!ul) return;
  const liste = konten.liste();
  const zeigen = karte ? liste.filter((k) => k.fach !== konten.aktivesFach()) : liste;
  ul.replaceChildren();
  for (const k of zeigen) {
    const offen = k.fach === konten.aktivesFach();
    const li = document.createElement("li");
    const b = document.createElement("button"); b.type = "button"; b.className = "konto-zeile" + (offen ? " offen" : "");
    const av = document.createElement("span"); av.className = "avatar"; av.setAttribute("aria-hidden", "true"); av.textContent = (konten.anzeige(k).trim()[0] || "K").toUpperCase();
    const t = document.createElement("span"); t.className = "konto-text";
    const n = document.createElement("span"); n.textContent = (karte ? "Zurück zu " : "") + konten.anzeige(k);
    const s = document.createElement("small"); s.textContent = offen ? "Angemeldet, gerade offen" : (k.benutzer ? `@${k.benutzer}` : k.name);
    t.append(n, s); b.append(av, t);
    if (offen) { b.disabled = true; b.setAttribute("aria-current", "true"); b.append(symbol("haken")); }
    else b.onclick = () => konten.wechseln(k.fach, `Du bist jetzt bei ${konten.anzeige(k)}.`);
    li.append(b); ul.append(li);
  }
  if (karte) karte.hidden = !zeigen.length;
  if (!karte) {
    $("#k-konten-info").textContent = liste.length > 1 ? `${liste.length} Konten` : "";
    $("#btn-konto-hinzu").hidden = liste.length >= konten.MAX_KONTEN;
  }
}


function kontenBlattAuf() {
  kontenZeichnen($("#kb-liste"), null);
  $("#kb-hinzu").hidden = konten.liste().length >= konten.MAX_KONTEN;
  const d = $("#konten-blatt");
  d.returnValue = ""; d.showModal();
  d.addEventListener("close", () => {
    if (d.returnValue === "hinzu") kontoHinzufuegen();
    else if (d.returnValue === "einstellungen") einstellungenAuf();
  }, { once: true });
}


async function lernenZeichnen() {
  const s = $("#e-lernen");
  s.disabled = true; $("#e-lernen-hinweis").hidden = true;
  if (!z.geraet?.konto) { s.checked = true; $("#e-lernen-text").textContent = "Ohne KIplatz-Konto merkt sich KIplatz keine Frage, also lernt es auch nichts daraus."; return; }
  try { const r = await holen("/lernen", { body: {}, geraet: z.geraet }); s.checked = r.an !== false; s.disabled = false; }
  catch (e) { }
}

function kontoHinzufuegen() {
  if (konten.liste().length >= konten.MAX_KONTEN) { status(`Mehr als ${konten.MAX_KONTEN} Konten gehen auf einem Gerät nicht.`); return; }
  konten.wechseln(konten.neuesFach(), "Melde dich mit dem anderen Konto an. Dein bisheriges Konto bleibt angemeldet.");
}


function einstellungenAuf() {
  const ang = z.geraet?.angemeldet ? new Date(z.geraet.angemeldet) : null;
  $("#e-name").textContent = z.geraet ? (z.geraet.konto ? `${z.geraet.konto} · ${z.geraet.name}` : z.geraet.name) : "";
  $("#e-ort").textContent = ang && !isNaN(ang) ? (z.geraet.ort ? `Angemeldet im ${z.geraet.ort} am ${wann(ang)}.` : `Angemeldet am ${wann(ang)}.`) : "";
  $("#e-tresor").textContent = tresor.imTresor() ? "Der Zugang liegt im Tresor dieses Geräts." : (ENTWICKLUNG ? "Entwicklung im Browser: Der Zugang liegt im Speicher der Seite." : "Der Zugang liegt im Speicher der Seite.");
  for (const r of document.querySelectorAll('input[name="aussehen"]')) r.checked = r.value === z.einst.aussehen;
  for (const r of document.querySelectorAll('input[name="schrift"]')) r.checked = r.value === z.einst.schrift;
  for (const r of document.querySelectorAll('input[name="sprache"]')) r.checked = r.value === globalThis.kiplatzSprache.gewaehlt();
  $("#e-standort").checked = !!z.einst.standort;
  lernenZeichnen();
  $("#meine-daten").hidden = true;
  $("#k-konten-name").textContent = z.geraet ? (z.geraet.konto || z.geraet.name) : "Nicht angemeldet";
  $("#avatar-einst").textContent = $("#avatar-kopf").textContent;
  $("#k-aussehen-info").textContent = { system: "Wie das Gerät", hell: "Hell", dunkel: "Dunkel" }[z.einst.aussehen] || "";
  $("#k-geraete-info").textContent = ""; $("#k-abgleich-info").textContent = "";
  kontenZeichnen($("#konten-liste"), null);
  zuhauseZeichnen();
  geraeteZeichnen();
  adminZeichnen();
  abgleichZeichnen();
  z.platzl?.einstellungenZeigen();
  $("#e-version").textContent = `KIplatz-App ${APP_VERSION}`;

  $("#e-quelltext-text").textContent = "Der Quelltext von Programm und App ist offen (Lizenz GNU AGPL 3):";
  leisteZu();
  meineKiZeile();

  if (verlauf.offen("einstellungen")) verlauf.bis("einstellungen");
  else { verlauf.alleZu(); $("#einstellungen").hidden = false; verlauf.auf("einstellungen", einstellungenWeg); }
  $("#einstellungen").scrollTop = 0;


  $("#einstellungen-titel").focus({ preventScroll: true });
}

function einstellungenWeg() { $("#einstellungen").hidden = true; }
function einstellungenZu() { if (!verlauf.zurueck("einstellungen")) einstellungenWeg(); }


function unterseiteAuf(id) {
  const s = $("#" + id); if (!s) return;
  verlauf.bis("einstellungen");
  if (s.hidden) { s.hidden = false; verlauf.auf(id, () => unterseiteWeg(id)); }
  s.scrollTop = 0; s.querySelector("h2")?.focus({ preventScroll: true });
}
function unterseiteWeg(id) { const s = $("#" + id); if (s) s.hidden = true; $("#einstellungen-titel").focus({ preventScroll: true }); }
function unterseiteZu(id) { if (!verlauf.zurueck(id)) unterseiteWeg(id); }


function meineKiAuf() {
  $("#e-anrede").value = z.einst.anrede || ""; $("#e-wohnort").value = z.einst.wohnort || ""; $("#e-ueber-dich-ok").textContent = "";
  meineKiZeichnen();
  if (!verlauf.offen("meineki")) { verlauf.bis("einstellungen"); $("#meineki").hidden = false; verlauf.auf("meineki", meineKiWeg); }
  $("#meineki-titel").focus({ preventScroll: true });
}
function meineKiWeg() { $("#meineki").hidden = true; }
function meineKiZu() { if (!verlauf.zurueck("meineki")) meineKiWeg(); }


function zuhauseZeichnen() {
  const l = z.zuhause;
  $("#k-zuhause-info").textContent = l.map((p) => p.pc_name).join(", ");
  $("#e-zuhause").textContent = l.length ? `Verbunden mit ${l.map((p) => `„${p.pc_name}“`).join(", ")}. ${WO_SUCHEN}` : (z.geraet ? "Noch mit keinem PC verbunden." : "Melde dieses Handy zuerst an.");
  $("#zuhause-eingabe").hidden = !z.geraet;
  const ul = $("#zuhause-pcs"); ul.replaceChildren();
  for (const p of l) {
    const li = document.createElement("li"); const n = document.createElement("span"); n.textContent = p.pc_name;
    const b = document.createElement("button"); b.type = "button"; b.className = "knopf"; b.textContent = "Vergessen";
    b.onclick = async () => {
      z.zuhause = z.zuhause.filter((x) => x.kid !== p.kid); await tresor.schreiben("zuhause", z.zuhause); zuhauseZeichnen(); daheimLeiste();
      try { await holen("/zuhause-entfernen", { body: { kid: p.kid }, geraet: z.geraet }); } catch { }
      status(`„${p.pc_name}“ vergessen.`);
    };
    li.append(n, b); ul.append(li);
  }
}


async function zuhauseServerliste() {
  if (!z.geraet) return null;
  try {
    const r = await holen("/zuhause-liste", { body: {}, geraet: z.geraet });
    return Array.isArray(r?.daheim) ? new Map(r.daheim.map((d) => [String(d.kid), String(d.pc)])) : null;
  } catch { return null; }
}
async function zuhauseAbgleichen() {
  if (!z.zuhause.length) return;
  const pcVon = await zuhauseServerliste();
  if (!pcVon) return;
  const vorher = z.zuhause.length;
  z.zuhause = z.zuhause.filter((p) => pcVon.has(p.kid)).map((p) => ({ ...p, pc: pcVon.get(p.kid) }));
  if (z.zuhause.length !== vorher) { await tresor.schreiben("zuhause", z.zuhause); zuhauseZeichnen(); daheimLeiste(); }
}
async function zuhauseKoppeln(code) {
  const e = await zuhause.koppeln(code, holen, z.geraet);
  const pcVon = await zuhauseServerliste();
  const pc = pcVon?.get(e.kid) || "";

  const gleich = (x) => x.kid !== e.kid && (pc ? (pcVon.get(x.kid) === pc || x.pc === pc || (!pcVon.has(x.kid) && x.pc_name === e.pc_name)) : x.pc_name === e.pc_name);
  const alt = z.zuhause.filter(gleich);
  for (const x of alt) {
    if (pcVon?.has(x.kid)) { try { await holen("/zuhause-entfernen", { body: { kid: x.kid }, geraet: z.geraet }); } catch { } }
  }
  z.zuhause = [...z.zuhause.filter((x) => x.kid !== e.kid && !gleich(x) && (!pcVon || pcVon.has(x.kid))), { ...e, ...(pc ? { pc } : {}) }];
  await tresor.schreiben("zuhause", z.zuhause);
  zuhauseZeichnen(); daheimLeiste();
  const satz = alt.length
    ? `Dein Handy war schon mit „${e.pc_name}“ verbunden. Die Verbindung ist jetzt erneuert, es bleibt eine. ${WO_SUCHEN}`
    : `Fertig! Dein Handy ist jetzt mit „${e.pc_name}“ verbunden. ${WO_SUCHEN}`;
  $("#e-zuhause").textContent = satz; $("#e-zuhause").classList.add("gut");
  status(satz);
  nativ?.tippen();
}


let qrLauf = null;
function jsqrLaden() {
  if (window.jsQR) return Promise.resolve(window.jsQR);
  return new Promise((ok, fehler) => {
    const s = document.createElement("script"); s.src = "js/vendor/jsQR.js?v=" + encodeURIComponent(APP_VERSION);
    s.onload = () => (window.jsQR ? ok(window.jsQR) : fehler(new Error("QR-Leser fehlt")));
    s.onerror = () => fehler(new Error("QR-Leser fehlt")); document.head.append(s);
  });
}
function qrStoppen() {
  if (!qrLauf) return;
  clearInterval(qrLauf.uhr); clearTimeout(qrLauf.ende);
  for (const t of qrLauf.strom?.getTracks() || []) t.stop();
  $("#qr-video").srcObject = null; qrLauf = null;
  if ($("#qr-dialog").open) $("#qr-dialog").close();
}


const PC_QR = /^https:\/\/kiplatz\.at\/app\/#pc=([A-Za-z0-9_-]{32})$/;
async function qrScannen(art = "zuhause") {
  const pc = art === "pc";
  const meldung = (t) => { if (pc) status(t); else $("#e-zuhause").textContent = t; };
  if (!z.geraet) { meldung(pc ? "Melde dieses Handy zuerst mit deinem Konto an." : "Melde dieses Handy zuerst an, dann kannst du es mit deinem PC verbinden."); return; }
  qrStoppen();
  if (!pc) $("#e-zuhause").textContent = "";
  let lesen;
  try {
    lesen = await jsqrLaden();
    qrLauf = { strom: await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false }) };
  } catch (e) {
    qrStoppen();
    meldung(pc
      ? (e?.name === "NotAllowedError" ? "Für den QR-Code braucht KIplatz die Kamera. Du kannst sie in den Einstellungen deines Handys erlauben, oder du meldest den PC dort mit „Mit KIplatz-Konto anmelden“ an."
        : "Die Kamera lässt sich gerade nicht öffnen. Melde den PC dort mit „Mit KIplatz-Konto anmelden“ an.")
      : (e?.name === "NotAllowedError"
        ? "Ohne Kamera geht es auch: Tipp einfach den Code vom PC unten ein. Die Kamera kannst du später in den Einstellungen deines Handys erlauben."
        : "Die Kamera lässt sich gerade nicht öffnen. Tipp einfach den Code vom PC unten ein."));
    return;
  }
  const video = $("#qr-video"), leinwand = document.createElement("canvas"), ctx = leinwand.getContext("2d", { willReadFrequently: true });
  video.srcObject = qrLauf.strom;
  $("#qr-titel").textContent = pc ? "Halte die Kamera auf den QR-Code im Programm am PC" : "Halte die Kamera auf den QR-Code am PC";
  $("#qr-status").textContent = "Sobald der Code erkannt ist, geht es von selbst weiter.";
  $("#qr-dialog").showModal();
  try { await video.play(); } catch { }
  qrLauf.ende = setTimeout(() => { qrStoppen(); meldung(pc ? "Ich habe keinen Code erkannt. Probier es noch einmal." : "Ich habe keinen Code erkannt. Probier es noch einmal, oder tipp den Code unten ein."); }, 120000);
  qrLauf.uhr = setInterval(async () => {
    if (!qrLauf || video.readyState < 2 || !video.videoWidth) return;
    const f = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
    leinwand.width = Math.round(video.videoWidth * f); leinwand.height = Math.round(video.videoHeight * f);
    ctx.drawImage(video, 0, 0, leinwand.width, leinwand.height);
    const bild = ctx.getImageData(0, 0, leinwand.width, leinwand.height);
    const fund = lesen(bild.data, bild.width, bild.height, { inversionAttempts: "dontInvert" });
    ctx.clearRect(0, 0, leinwand.width, leinwand.height);
    if (!fund?.data) return;
    if (pc) {
      const m = PC_QR.exec(String(fund.data).trim());
      if (!m) { $("#qr-status").textContent = "Das ist kein Anmelde-Code von KIplatz. Halte die Kamera auf den QR-Code bei „Mit dem Handy anmelden“ im Programm."; return; }
      qrStoppen();
      await pcAnmelden(m[1], false);
      return;
    }
    if (!zuhause.codeNormal(fund.data)) { $("#qr-status").textContent = "Das ist kein Code von KIplatz. Halte die Kamera auf den QR-Code unter „Frag dein Zuhause“."; return; }
    qrStoppen();
    if (!confirm("Mit dem PC verbinden, der diesen Code zeigt? Bitte nur, wenn es dein eigener PC ist.")) return;
    try { await zuhauseKoppeln(fund.data); } catch (e) { $("#e-zuhause").textContent = e.message || "Das Verbinden hat nicht geklappt. Probier es bitte noch einmal."; }
  }, 250);
}


async function pcAnmelden(code, vonLink) {
  if (!z.geraet?.konto) { status("Melde dieses Handy zuerst mit deinem Konto an, dann kannst du damit einen PC anmelden."); return; }
  let info;
  try { info = await holen("/pc-qr-info", { body: { code }, geraet: z.geraet }); }
  catch (e) { status(e.message || "Der Code lässt sich gerade nicht prüfen. Probier es bitte noch einmal."); return; }
  const frage = `Am PC „${info.pc_name}“ mit deinem Konto ${z.geraet.konto} anmelden?\n\n`
    + (vonLink ? "Achtung: Dieser Code kam über einen Link. Bestätige nur, wenn du ihn gerade selbst an deinem PC geöffnet hast. Nie für einen Code, den dir jemand schickt."
      : "Bestätige nur, wenn du gerade selbst vor diesem PC sitzt und den Code dort im KIplatz-Programm geöffnet hast.");
  if (!confirm(frage)) { status("Nicht angemeldet. Der Code verfällt von selbst."); return; }
  try {
    const r = await holen("/pc-qr-bestaetigen", { body: { code }, geraet: z.geraet });
    status(r.text || "Der PC ist jetzt mit deinem Konto angemeldet.");
  } catch (e) { status(e.message || "Das Anmelden hat nicht geklappt. Probier es bitte noch einmal."); }
}

async function zuhauseVonLink(url) {

  if (!z.geraet) { status("Melde dieses Handy zuerst an und scanne den Code danach noch einmal."); return; }
  if (!confirm("Mit dem PC verbinden, der diesen Code zeigt? Bitte nur, wenn es dein eigener PC ist.")) return;
  try { await zuhauseKoppeln(url); } catch (e) { status(e.message || "Das Verbinden hat nicht geklappt. Probier es bitte noch einmal."); }
}


function tagText(tag) {
  if (!tag) return "";
  const heute = new Date(), d = new Date(tag + "T12:00:00Z");
  if (isNaN(d)) return "";
  const tage = Math.round((Date.UTC(heute.getFullYear(), heute.getMonth(), heute.getDate()) - Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())) / 86400000);
  return tage <= 0 ? "heute" : tage === 1 ? "gestern" : `vor ${tage} Tagen`;
}
async function geraeteZeichnen() {
  const liste = $("#geraete-liste"), meldung = $("#geraete-meldung"), alle = $("#btn-ueberall-abmelden");
  liste.replaceChildren(); alle.hidden = true;
  if (!z.geraet?.konto) { meldung.textContent = "Dieses Gerät ist ohne KIplatz-Konto angemeldet."; return; }
  meldung.textContent = "Wird geladen …";
  let d;
  try { d = await holen("/meine-geraete", { body: {}, geraet: z.geraet }); }
  catch (e) { meldung.textContent = e.message; return; }
  meldung.textContent = "";
  const geraete = [...(d.geraete || [])].sort((a, b) => (b.dieses ? 1 : 0) - (a.dieses ? 1 : 0));
  for (const g of geraete) {
    const li = document.createElement("li");
    const text = document.createElement("div");
    const name = document.createElement("strong"); name.translate = false; name.textContent = g.name || g.art;
    const info = document.createElement("small");
    const seit = g.angemeldet ? new Date(g.angemeldet) : null;

    info.textContent = [g.art, seit && !isNaN(seit) ? "angemeldet seit " + seit.toLocaleDateString(kiplatzSprache.datumSprache(), { day: "2-digit", month: "2-digit", year: "numeric" }) : "",
                        g.dieses ? "dieses Gerät" : (g.zuletzt ? "zuletzt aktiv " + tagText(g.zuletzt) : ""),
                        g.gruendung ? "Gründungsmitglied Nr. " + g.gruendung : ""].filter(Boolean).join(" · ");
    text.append(name, info);
    li.append(text);
    if (!g.dieses) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "knopf klein-knopf"; b.textContent = "Abmelden";
      b.setAttribute("aria-label", `${g.name || g.art} abmelden`);
      b.onclick = () => geraetAbmelden(g, b);
      li.append(b);
    }
    liste.append(li);
  }
  alle.hidden = (d.geraete || []).filter((g) => !g.dieses).length === 0;
  $("#k-geraete-info").textContent = String((d.geraete || []).length);
}
async function geraetAbmelden(g, knopf) {
  const pc = !g.sitzung;
  const frage = pc ? `Dein Konto von „${g.name}“ abmelden? Der PC arbeitet weiter für die Community, aber nicht mehr für dein Konto.`
                   : `„${g.name}“ abmelden? Dort musst du dich danach neu anmelden.`;
  if (!confirm(frage)) return;
  knopf.disabled = true;
  try { const r = await holen("/geraet-abmelden", { body: { kennung: g.kennung }, geraet: z.geraet }); $("#geraete-meldung").textContent = r.text || ""; }
  catch (e) { $("#geraete-meldung").textContent = e.message; knopf.disabled = false; return; }
  const meldung = $("#geraete-meldung").textContent;
  await geraeteZeichnen(); $("#geraete-meldung").textContent = meldung;
}


const admin = { geraete: [], suche: "" };
async function adminZeichnen(aufklappen = false) {
  const karte = $("#karte-admin");
  if (!z.geraet) { karte.hidden = true; return; }
  let m, g;
  try { m = await holen("/sicherheit", { body: {}, geraet: z.geraet }); } catch { karte.hidden = true; return; }
  try { g = await holen("/geraete", { body: {}, geraet: z.geraet }); } catch { karte.hidden = true; return; }
  karte.hidden = false;
  if (aufklappen) unterseiteAuf("s-admin");
  admin.geraete = g.geraete || [];
  const ml = $("#admin-meldungen"); ml.replaceChildren();
  for (const x of (m.meldungen || []).slice(0, 20)) {
    const li = document.createElement("li");
    const t = document.createElement("div");
    const kopf = document.createElement("small"); const wann = new Date(x.zeit);
    kopf.textContent = isNaN(wann) ? x.zeit : wann.toLocaleString(kiplatzSprache.datumSprache(), { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
    const satz = document.createElement("span"); satz.textContent = x.text;
    t.append(kopf, document.createElement("br"), satz); li.append(t);
    if (x.kennung) { const b = document.createElement("button"); b.type = "button"; b.className = "knopf klein-knopf"; b.textContent = "Gerät zeigen";
      b.onclick = () => { $("#admin-suche").value = x.kennung; admin.suche = x.kennung; adminGeraeteZeichnen(); }; li.append(b); }
    ml.append(li);
  }
  if (!ml.children.length) { const li = document.createElement("li"); li.textContent = "Keine Meldungen."; ml.append(li); }
  $("#k-admin-info").textContent = (m.meldungen || []).length ? String((m.meldungen || []).length) : "";
  adminGeraeteZeichnen();
  adminTeamsZeichnen();
}

async function adminTeamsZeichnen(liste = null, meldung = "") {
  const ul = $("#admin-teams");
  if (!liste) { try { liste = (await holen("/teams-admin", { geraet: z.geraet })).teams || []; } catch (e) { $("#admin-teams-meldung").textContent = e.message; return; } }
  ul.replaceChildren();
  for (const x of liste) {
    const li = document.createElement("li");
    const t = document.createElement("div");
    const n = document.createElement("b"); n.textContent = x.name;
    const i = document.createElement("small");
    i.textContent = [x.mitglieder === 1 ? "1 Mitglied" : `${x.mitglieder} Mitglieder`, x.seit ? "seit " + x.seit.split("-").reverse().join(".") : "", x.gesperrt ? `gesperrt: ${x.gesperrt.grund || ""}` : ""].filter(Boolean).join(" · ");
    t.append(n, document.createElement("br"), i); li.append(t);
    const knoepfe = document.createElement("div"); knoepfe.className = "knopf-paar";
    const knopf = (text, tun) => { const b = document.createElement("button"); b.type = "button"; b.className = "knopf klein-knopf"; b.textContent = text; b.onclick = () => tun(b); knoepfe.append(b); };
    if (x.gesperrt) knopf("Freigeben", (b) => adminTeamTun(b, { id: x.id, aktion: "entsperren", grund: "" }));
    else knopf("Sperren", (b) => { const grund = prompt(`Warum wird „${x.name}“ gesperrt? Die Mitglieder lesen den Grund.`); if (grund !== null) adminTeamTun(b, { id: x.id, aktion: "sperren", grund }); });
    knopf("Umbenennen", (b) => {
      const name = prompt("Neuer Name für das Team:", x.name); if (name === null || !name.trim() || name.trim() === x.name) return;
      const grund = prompt("Warum wird es umbenannt? Die Mitglieder lesen den Grund."); if (grund !== null) adminTeamTun(b, { id: x.id, aktion: "umbenennen", grund, name: name.trim() });
    });
    knopf("Entfernen", (b) => { const grund = prompt(`Team „${x.name}“ entfernen: Die Mitglieder sind danach in keinem Team. Warum? Sie lesen den Grund.`); if (grund !== null) adminTeamTun(b, { id: x.id, aktion: "entfernen", grund }); });
    li.append(knoepfe); ul.append(li);
  }
  if (!ul.children.length) { const li = document.createElement("li"); li.textContent = "Noch gibt es kein Team."; ul.append(li); }
  $("#admin-teams-meldung").textContent = meldung;
}
async function adminTeamTun(knopf, body) {
  knopf.disabled = true;
  try { const r = await holen("/team-admin", { body, geraet: z.geraet }); adminTeamsZeichnen(r.teams || [], r.text || "Erledigt."); }
  catch (e) { $("#admin-teams-meldung").textContent = e.message; knopf.disabled = false; }
}
function adminGeraeteZeichnen() {
  const ul = $("#admin-geraete"); ul.replaceChildren();
  const q = admin.suche.trim().toLowerCase();
  const treffer = q ? admin.geraete.filter((g) => (g.name || "").toLowerCase().includes(q) || (g.kennung || "").toLowerCase().includes(q)) : [];
  for (const g of treffer.slice(0, 10)) {
    const li = document.createElement("li");
    const t = document.createElement("div");
    const n = document.createElement("strong"); n.translate = false; n.textContent = g.name || g.kennung;
    const i = document.createElement("small"); i.textContent = [g.kennung, g.gesperrt ? (g.lebenslang ? "auf Lebenszeit gesperrt" : "gesperrt") + (g.sperrgrund ? ": " + g.sperrgrund : "") : "", g.verstoesse ? `${g.verstoesse} Verstöße` : ""].filter(Boolean).join(" · ");
    t.append(n, document.createElement("br"), i); li.append(t);
    const knoepfe = document.createElement("div"); knoepfe.className = "knopf-paar";
    const knopf = (text, f) => { const b = document.createElement("button"); b.type = "button"; b.className = "knopf klein-knopf"; b.textContent = text; b.onclick = () => f(b); knoepfe.append(b); };
    if (g.admin || g.kennung === z.geraet?.kennung) { li.append(knoepfe); ul.append(li); continue; }
    knopf(g.gesperrt ? "Sperre aufheben" : "Sperren", (b) => adminTun(b, "/geraet-sperren", { kennung: g.kennung, gesperrt: !g.gesperrt, grund: g.gesperrt ? "" : (prompt("Warum wird das Gerät gesperrt? (kurz)") ?? null) }));
    if (!g.lebenslang) knopf("Lebenslang sperren", (b) => { const grund = prompt("Auf Lebenszeit sperren: Gerät und KIplatz-Konto kommen nie wieder in die Community. Warum? (kurz)"); if (grund !== null) adminTun(b, "/geraet-lebenslang", { kennung: g.kennung, grund }); });
    knopf("Entfernen", (b) => { if (confirm(`„${g.name || g.kennung}“ ganz aus der Community entfernen?`)) adminTun(b, "/geraet-entfernen", { kennung: g.kennung }); });
    li.append(knoepfe); ul.append(li);
  }
  $("#admin-meldung").textContent = q && !treffer.length ? "Kein Gerät gefunden." : "";
}
async function adminTun(knopf, weg, body) {
  if (body.grund === null) return;
  knopf.disabled = true;
  try { await holen(weg, { body, geraet: z.geraet }); $("#admin-meldung").textContent = "Erledigt."; }
  catch (e) { $("#admin-meldung").textContent = e.message; knopf.disabled = false; return; }
  const g = await holen("/geraete", { body: {}, geraet: z.geraet }).catch(() => null);
  if (g) { admin.geraete = g.geraete || []; adminGeraeteZeichnen(); $("#admin-meldung").textContent = "Erledigt."; }
}


const STELLEN = { kiplatz: "KIplatz", werkstatt: "Mitbauen", platzl: "Mitreden" };


let loeschNachweis = null;
function loeschenDialog(schritt) {
  const dlg = $("#loeschen-dialog");
  $("#ld-start").hidden = schritt !== "start"; $("#ld-bestaetigen").hidden = schritt !== "bestaetigen"; $("#ld-browser").hidden = schritt !== "browser";
  $("#ld-ja").disabled = $("#ld-nein").disabled = false;
  $("#ld-meldung").textContent = ""; $("#ld-wort").value = ""; $("#ld-loeschen").disabled = true;
  if (!dlg.open) dlg.showModal();
}
function loeschenStart() { loeschNachweis = null; loeschenDialog("start"); }
function loeschenBestaetigen(r) {
  loeschNachweis = String(r.nachweis || "");
  const konto = String(r.konto || ""), benutzer = String(r.benutzer || "");
  loeschenDialog("bestaetigen");
  $("#ld-wer").textContent = mitBenutzer(konto, benutzer) ? `Gelöscht wird das Konto „${konto}“ (Benutzername ${benutzer}).` : `Gelöscht wird das Konto „${konto}“.`;
  $("#ld-wort").focus();
}


let loeschFrage = null;
function loeschenFrage(state, r) {
  loeschFrage = { state, frage: String(r.frage || "") };
  const konto = String(r.konto || ""), benutzer = String(r.benutzer || "");
  loeschenDialog("browser");
  $("#ld-browser-wer").textContent = mitBenutzer(konto, benutzer) ? `Gelöscht werden soll dein Konto „${konto}“ (Benutzername ${benutzer}).`
    : `Gelöscht werden soll dein Konto „${konto}“.`;
}
async function loeschenAntworten(ja) {
  const f = loeschFrage, m = $("#ld-meldung");
  if (!f) return;
  $("#ld-ja").disabled = $("#ld-nein").disabled = true;
  m.textContent = "Einen Moment …";
  let r;
  try { r = await holen("/konto-zurueck", { body: { state: f.state, frage: f.frage, ja } }); }
  catch (e) { loeschFrage = null; $("#ld-browser").hidden = true; m.textContent = e.message; return; }
  loeschFrage = null;
  $("#ld-browser").hidden = true;
  if (!ja) localStorage.removeItem("kiplatz." + ANMELDUNG);

  m.textContent = ja && hierBegonnen() ? "Einen Moment …" : (r.text || "");
  if (ja && hierBegonnen()) kontoAbholen();
}
async function loeschenAusfuehren() {
  const b = $("#ld-loeschen"), m = $("#ld-meldung");
  if (!loeschNachweis) { loeschenStart(); return; }
  b.disabled = true; m.textContent = "Einen Moment …";
  let r;
  try { r = await holen("/konto-loeschen-bestaetigt", { body: { nachweis: loeschNachweis, bestaetigung: $("#ld-wort").value.trim() }, zeitlimit: 90000 }); }
  catch (e) { m.textContent = e.message; b.disabled = false; return; }
  if (!r.geloescht) { m.textContent = r.text || "Das hat nicht ganz geklappt. Bitte noch einmal."; b.disabled = false; return; }
  loeschNachweis = null;
  $("#loeschen-dialog").close();


  const text = r.text || "Dein KIplatz-Konto ist gelöscht. Danke, dass du dabei warst.";
  abmeldeGrund = text;
  alert(text);
  if (z.geraet) { try { await holen("/meine-daten", { body: {}, geraet: z.geraet }); } catch { } }
  abmeldeGrund = "";
}

async function adminKontenSuchen() {
  const ul = $("#admin-konten"), meldung = $("#admin-konto-meldung");
  const q = $("#admin-konto-suche").value.trim();
  ul.replaceChildren(); meldung.textContent = "";
  if (q.length < 2) return;
  let r; const nr = (adminKontenSuchen.nr = (adminKontenSuchen.nr || 0) + 1);
  try { r = await holen("/konto-suchen", { body: { q }, geraet: z.geraet }); } catch (e) { if (nr === adminKontenSuchen.nr) meldung.textContent = e.message; return; }
  if (nr !== adminKontenSuchen.nr) return;
  if (r.bereit && !r.bereit.werkstatt) { meldung.textContent = "Die Kontoverwaltung ist am Server noch nicht eingerichtet."; return; }
  for (const k of r.konten || []) {
    const li = document.createElement("li");
    const t = document.createElement("div");
    const n = document.createElement("strong"); n.textContent = k.anzeigename || k.name;
    const i = document.createElement("small");
    i.textContent = [k.name, k.email, k.admin ? "Admin" : "", k.gesperrt || k.kiplatz_gesperrt ? "gesperrt" : "", k.geraete ? `${k.geraete} Geräte` : ""].filter(Boolean).join(" · ");
    t.append(n, document.createElement("br"), i); li.append(t);
    const knoepfe = document.createElement("div"); knoepfe.className = "knopf-paar";
    const knopf = (text, f) => { const b = document.createElement("button"); b.type = "button"; b.className = "knopf klein-knopf"; b.textContent = text; b.onclick = () => f(b); knoepfe.append(b); };
    if (!k.admin) {
      if (k.gesperrt || k.kiplatz_gesperrt) knopf("Überall freigeben", (b) => { if (confirm(`„${k.name}“ überall wieder freigeben? Die Person bekommt dazu eine Mail.`)) adminKontoTun(b, k, "entsperren", ""); });
      else knopf("Überall sperren", (b) => { const grund = prompt(`„${k.name}“ überall sperren. Warum? Das steht in der Mail an die Person: welche Regel, was ist passiert (ohne Namen anderer).`); if (grund !== null) adminKontoTun(b, k, "sperren", grund); });

      knopf("Überall löschen", (b) => { if (!confirm(`„${k.name}“ überall löschen, mit allen Beiträgen und Geräten? Das kann man nicht rückgängig machen. Wer nicht wiederkommen soll, wird besser gesperrt.`)) return; const grund = prompt(`Warum? Das steht in der Mail an die Person: welche Regel, was ist passiert (ohne Namen anderer).`); if (grund !== null) adminKontoTun(b, k, "loeschen", grund); });
    }
    li.append(knoepfe); ul.append(li);
  }
  if (!ul.children.length) meldung.textContent = "Kein Konto gefunden.";
}
async function adminKontoTun(knopf, k, aktion, grund) {
  const meldung = $("#admin-konto-meldung");
  knopf.disabled = true; meldung.textContent = "Einen Moment …";
  let r;
  try { r = await holen("/konto-ueberall", { body: { id: k.id, aktion, grund }, geraet: z.geraet, zeitlimit: 60000 }); }
  catch (e) { meldung.textContent = e.message; knopf.disabled = false; return; }
  const s = r.stellen || {};
  await adminKontenSuchen();
  meldung.replaceChildren(document.createTextNode(Object.keys(STELLEN).filter((x) => s[x]).map((x) => `${STELLEN[x]}: ${s[x]}`).join(" · ")));
  if (s.platzl_adresse) { const a = document.createElement("a"); a.href = s.platzl_adresse; a.target = "_blank"; a.rel = "noopener"; a.textContent = "Platzl-Verwaltung öffnen"; meldung.append(" ", a); }
}


function abEl(tag, attr = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attr)) { if (k === "onclick") e.onclick = v; else e.setAttribute(k, v); }
  for (const k of kinder) e.append(k);
  return e;
}
function abKnopf(text, onclick, art = "") { return abEl("button", { type: "button", class: "knopf" + (art ? " " + art : ""), onclick }, text); }
const abPaar = (...knoepfe) => abEl("div", { class: "knopf-paar" }, ...knoepfe);
function schluesselZeigen(box, r, titel) {
  box.replaceChildren(
    abEl("p", {}, abEl("strong", {}, titel)),
    abEl("p", { class: "leise klein" }, "Schreib ihn auf und heb ihn gut auf, etwa bei deinen Unterlagen. Gehen alle deine Geräte verloren, holst du damit deine Gespräche zurück. Er wird nur jetzt gezeigt."),
    abEl("p", { class: "wiederherstellung", translate: "no" }, r),
    abPaar(abKnopf("Kopieren", () => kopieren(r)), abKnopf("Aufgeschrieben", () => abgleichZeichnen(), "haupt")));
}
async function abgleichAktion(box, fn) {
  const knoepfe = box.querySelectorAll("button"); knoepfe.forEach((b) => { b.disabled = true; });
  try { await fn(); } catch (e) { box.prepend(abEl("p", { class: "fehler klein", role: "alert" }, e.message)); knoepfe.forEach((b) => { b.disabled = false; }); }
}
async function abgleichZeichnen() {
  const box = $("#abgleich-inhalt");
  box.replaceChildren();
  if (!z.geraet?.konto) { box.append(abEl("p", { class: "leise klein" }, "Dafür muss dieses Gerät mit deinem KIplatz-Konto angemeldet sein.")); return; }
  box.append(abEl("p", { class: "leise klein" }, "Wird geladen …"));
  let s;
  try { s = await z.abgleich.stand(); } catch (e) { box.replaceChildren(abEl("p", { class: "fehler klein" }, e.message)); return; }
  box.replaceChildren();
  $("#k-abgleich-info").textContent = !s.an ? "Aus" : s.zugelassen ? (s.anfragen?.length ? "Gerät wartet" : s.wechsel_noetig ? "Neuer Schlüssel nötig" : "Ein") : "Wartet";
  if (!s.an) {
    box.append(abKnopf("Einschalten", () => abgleichAktion(box, async () => {
      const r = await z.abgleich.einschalten();
      if (r.wiederherstellung) { schluesselZeigen(box, r.wiederherstellung, "Dein Wiederherstellungsschlüssel"); abgleichBald(500); }
      else abgleichZeichnen();
    })));
    return;
  }
  if (!s.zugelassen) {
    box.append(
      abEl("p", {}, "Dieses Gerät wartet auf dein Okay. Öffne KIplatz auf einem Gerät, auf dem der Abgleich schon läuft, und lass dieses Gerät dort in den Einstellungen zu."),
      abEl("p", {}, "Prüfzahl dieses Geräts: ", abEl("strong", {}, s.pruefzahl || "–")),
      abEl("p", { class: "leise klein" }, "Dort muss genau dieselbe Zahl stehen. Kein anderes Gerät zur Hand? Dann mit deinem Wiederherstellungsschlüssel:"));
    const feld = abEl("input", { type: "text", id: "abgleich-wieder", autocomplete: "off", spellcheck: "false", placeholder: "XXXX-XXXX-XXXX-XXXX-XXXX-XXXX", "aria-label": "Wiederherstellungsschlüssel" });
    box.append(feld,
      abPaar(abKnopf("Mit Schlüssel holen", () => abgleichAktion(box, async () => { await z.abgleich.wiederherstellen(feld.value); abgleichBald(200); abgleichZeichnen(); })),
        abKnopf("Neu nachsehen", () => abgleichZeichnen())),
      abKnopf("Abbrechen", () => abgleichAktion(box, async () => { await z.abgleich.ausschalten(); abgleichZeichnen(); }), "flach"));
    return;
  }
  const mb = (b) => (b > 0 && b < 104858 ? "unter 0,1" : (b / 1048576).toLocaleString(kiplatzSprache.datumSprache(), { maximumFractionDigits: 1 }));
  box.append(abEl("p", {}, (s.gespraeche === 1 ? `Eingeschaltet. 1 Gespräch abgeglichen, ${mb(s.belegt)} von ${mb(s.grenze)} MB.` : `Eingeschaltet. ${s.gespraeche} Gespräche abgeglichen, ${mb(s.belegt)} von ${mb(s.grenze)} MB.`)
    + (s.zuletzt ? ` Zuletzt ${new Date(s.zuletzt).toLocaleTimeString(kiplatzSprache.datumSprache(), { hour: "2-digit", minute: "2-digit" })} Uhr.` : "")));
  if (s.fehler) box.append(abEl("p", { class: "fehler klein" }, s.fehler));
  for (const q of s.anfragen) {
    box.append(abEl("div", { class: "abgleich-anfrage" },
      abEl("p", {}, abEl("strong", {}, `${q.name || "Ein Gerät"} möchte deine Gespräche.`)),
      abEl("p", {}, "Prüfzahl: ", abEl("strong", {}, q.pruefzahl)),
      abEl("p", { class: "leise klein" }, "Nur zulassen, wenn am anderen Gerät genau diese Zahl steht."),
      abPaar(abKnopf("Zulassen", () => abgleichAktion(box, async () => { await z.abgleich.zulassen(q.kennung); abgleichZeichnen(); }), "haupt"),
        abKnopf("Ablehnen", () => abgleichAktion(box, async () => { await z.abgleich.ablehnen(q.kennung); abgleichZeichnen(); })))));
  }
  if (s.wechsel_noetig) {
    box.append(abEl("div", { class: "abgleich-anfrage" },
      abEl("p", {}, abEl("strong", {}, "Ein Gerät wurde abgemeldet.")),
      abEl("p", { class: "leise klein" }, "Mach einen neuen Schlüssel, damit es nichts Neues mehr lesen kann. Du bekommst dabei einen neuen Wiederherstellungsschlüssel, der alte gilt dann nicht mehr."),
      abKnopf("Neuen Schlüssel machen", () => abgleichAktion(box, async () => { const r = await z.abgleich.schluesselWechseln(); schluesselZeigen(box, r.wiederherstellung, "Dein neuer Wiederherstellungsschlüssel"); }))));
  }
  box.append(
    abKnopf("Jetzt abgleichen", () => abgleichAktion(box, async () => { await abgleichen(); abgleichZeichnen(); }), "breit"),
    abPaar(abKnopf("Hier ausschalten", () => abgleichAktion(box, async () => {
      if (!confirm("Abgleich auf diesem Gerät ausschalten? Deine Gespräche bleiben hier, sie werden nur nicht mehr abgeglichen.")) return abgleichZeichnen();
      await z.abgleich.ausschalten(); abgleichZeichnen();
    })),
    abKnopf("Am Server löschen", () => abgleichAktion(box, async () => {
      if (!confirm("Alle abgeglichenen Gespräche am Server löschen und den Abgleich für alle deine Geräte ausschalten? Auf den Geräten selbst bleiben die Gespräche.")) return abgleichZeichnen();
      await z.abgleich.ausschalten({ amServerLoeschen: true }); abgleichZeichnen();
    }), "gefahr")));
}

let abmeldeGrund = "";
function zugangVerloren() {

  if (!z.geraet) return;
  platzlTrennen().then(() => z.platzl?.einstellungenZeigen());
  tresor.loeschen("geraet"); tresor.loeschen("abgleich"); tresor.loeschen("zuhause"); z.zuhause = []; localStorage.removeItem("kiplatz." + konten.name("abgleich-zuordnung")); z.geraet = null; verlauf.alleZu();
  konten.vergessen();
  anzeigen();
  anmeldeInfo(abmeldeGrund || "Du bist auf diesem Gerät abgemeldet worden, von einem anderen Gerät aus oder weil es 90 Tage nicht benutzt wurde. Melde dich einfach neu an.");
}


const skillTitel = (s) => s?.titel || s?.name || "";
function skillSchild(g) {


  const s = g?.skill ? skillAblage.holen(g.skill) : null;
  const alle = (g ? skillAblage.fuerGespraech(g.skill || "").mit : []).filter((x) => x.name !== meineKi.NAME || x.name === g.skill);
  $("#skill-schild").hidden = !alle.length;
  $("#btn-skill-weg").hidden = !s;
  if (alle.length) $("#skill-schild-text").textContent = skillTitel(alle[0]) + (alle.length > 1 ? ` + ${alle.length - 1}` : "");
}
function skillFuer(g, name) {
  if (!g) return;
  g.skill = name || "";
  speichern(); zeichneVerlauf();
}
let skillOffen = null;
function skillDialogAuf(s) {
  skillOffen = s;
  const vorher = skillAblage.holen(s.name);
  $("#sk-titel").textContent = skillTitel(s);
  $("#sk-beschreibung").textContent = s.beschreibung || "";
  $("#sk-text").textContent = s.text;
  const neu = vorher && vorher.text !== s.text;
  $("#sk-hinweis").textContent = neu ? "Im Platzl gibt es eine neuere Fassung. Sie ersetzt die gemerkte, auch in deinen Gesprächen." : vorher ? "Diesen Skill hast du schon, unverändert." : "";
  $("#sk-hinweis").hidden = !(neu || vorher);
  $("#sk-hier").hidden = !z.gespraeche.aktuell?.nachrichten.length;
  const d = $("#skill-dialog"); d.returnValue = ""; d.showModal();
}
function skillWaehlen(g) {
  const box = $("#skill-liste-wahl"); box.replaceChildren();
  const alle = skillAblage.liste();
  $("#sw-leer").hidden = alle.length > 0;
  $("#sw-immer-hinweis").hidden = !alle.length;
  for (const s of alle) {
    const zeile = document.createElement("div"); zeile.className = "sw-zeile";
    const k = document.createElement("button"); k.className = "zeile"; k.value = "s:" + s.name; k.textContent = skillTitel(s);
    if (g.skill === s.name) k.setAttribute("aria-current", "true");
    const weg = document.createElement("button"); weg.type = "button"; weg.className = "rund"; weg.setAttribute("aria-label", `„${skillTitel(s)}“ vergessen`);
    weg.append(symbol("loeschen"));
    weg.onclick = () => { if (confirm(`„${skillTitel(s)}“ vergessen? Gespräche damit sind danach ohne Skill.`)) { skillAblage.entfernen(s.name); zeile.remove(); zeichneVerlauf(); status(`„${skillTitel(s)}“ vergessen.`); $("#sw-leer").hidden = skillAblage.liste().length > 0; } };

    const immer = document.createElement("button"); immer.type = "button"; immer.className = "sw-immer"; immer.textContent = "Immer an";
    immer.setAttribute("aria-pressed", String(!!s.immer)); immer.setAttribute("aria-label", `„${skillTitel(s)}“ in jedem Gespräch verwenden`);
    immer.onclick = () => {
      const an = immer.getAttribute("aria-pressed") !== "true";
      skillAblage.immerSetzen(s.name, an); immer.setAttribute("aria-pressed", String(an)); zeichneVerlauf();
      const weg2 = skillAblage.fuerGespraech("").weg.some((x) => x.name === s.name);
      status(an ? (weg2 ? `„${skillTitel(s)}“ ist an, passt aber gerade nicht mehr dazu: zu viel Skill-Text auf einmal.` : `„${skillTitel(s)}“ gilt jetzt in jedem Gespräch.`)
        : `„${skillTitel(s)}“ gilt nur noch, wenn du ihn wählst.`);
    };
    zeile.append(k, immer, weg); box.append(zeile);
  }
  skillWahlFuer = g.kennung;
  const d = $("#skill-waehlen"); d.returnValue = ""; d.showModal();
}
let skillWahlFuer = "";
function skillsVerdrahten() {
  const dlg = $("#skill-dialog");
  dlg.addEventListener("close", () => {
    const s = skillOffen; skillOffen = null;
    if (!s || !dlg.returnValue) return;
    const wie = skillAblage.merken(s);
    if (dlg.returnValue === "neu") {
      verlauf.alleZu();
      z.gespraeche.neu(); skillFuer(z.gespraeche.aktuell, s.name); zeichneListe();
      status(`Skill „${skillTitel(s)}“ ist bereit. Stell deine Frage.`); $("#eingabe").focus();
    } else if (dlg.returnValue === "hier") {
      z.platzl?.zu(); skillFuer(z.gespraeche.aktuell, s.name); status(`Skill „${skillTitel(s)}“ gilt jetzt in diesem Gespräch.`);
    } else status(wie === "aktualisiert" ? `Skill „${skillTitel(s)}“ neu geladen.` : `Skill „${skillTitel(s)}“ gemerkt.`);
  });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  const wahl = $("#skill-waehlen");
  wahl.addEventListener("close", () => {
    const g = z.gespraeche.liste.find((x) => x.kennung === skillWahlFuer);
    const w = wahl.returnValue;
    if (!g || !w) return;
    skillFuer(g, w === "-" ? "" : w.slice(2));
  });
  wahl.addEventListener("click", (e) => { if (e.target === wahl) wahl.close(); });
  const menue = $("#skill-schild-menue");
  $("#btn-skill-schild").onclick = async () => {
    const s = skillAblage.holen(z.gespraeche.aktuell?.skill);
    if (!s) { if (z.gespraeche.aktuell) skillWaehlen(z.gespraeche.aktuell); return; }
    $("#ss-titel").textContent = skillTitel(s);
    $("#ss-beschreibung").textContent = s.beschreibung || "";
    const imPlatzl = Number.isInteger(s.thema);
    $("#ss-laden").hidden = !imPlatzl || !(await platzlVerbunden());
    $("#ss-platzl").hidden = !imPlatzl;
    menue.returnValue = ""; menue.showModal();
  };
  $("#btn-skill-weg").onclick = () => { skillFuer(z.gespraeche.aktuell, ""); status("Ohne Skill weiter."); };
  menue.addEventListener("click", (e) => { if (e.target === menue) menue.close(); });
  menue.addEventListener("close", async () => {
    const g = z.gespraeche.aktuell, s = skillAblage.holen(g?.skill);
    if (!s) return;
    if (menue.returnValue === "weg") { skillFuer(g, ""); status("Ohne Skill weiter."); }
    else if (menue.returnValue === "platzl") window.open(`${platzlForum}/t/${s.thema}`, "_blank", "noopener,noreferrer");
    else if (menue.returnValue === "laden") {
      status("Lädt den Skill aus dem Platzl …");
      try {
        const neu = await skillHolen(s.thema);
        if (neu.name !== s.name) { skillAblage.merken(neu); skillFuer(g, neu.name); }
        const wie = skillAblage.merken(neu);
        status(wie === "gleich" ? "Der Skill ist schon aktuell." : `Skill „${skillTitel(neu)}“ neu geladen. Probier es gleich aus.`);
        zeichneVerlauf();
      } catch (e) { status(e.message); }
    }
  });
}

function verdrahten() {
  symboleEinsetzen();
  beiAbgemeldet(zugangVerloren);
  $("#btn-leiste").onclick = leisteAuf;
  $("#btn-leiste-zu").onclick = leisteZu;
  $("#schleier").onclick = leisteZu;
  $("#btn-neu").onclick = () => { z.gespraeche.neu(); speichern(); zeichneListe(); zeichneVerlauf(); leisteZu(); $("#eingabe").focus(); };
  $("#suche").oninput = zeichneListe;
  $("#btn-suche").onclick = sucheAuf;
  $("#btn-suche-zu").onclick = sucheZu;
  $("#suche").addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); sucheZu(); } });
  $("#liste").onclick = (e) => {
    const b = e.target.closest("button[data-kennung]"); if (!b) return;
    z.gespraeche.waehlen(b.dataset.kennung); speichern(); zeichneListe(); zeichneVerlauf(); leisteZu(); pruefStand();
  };

  wischenVerdrahten();


  const ta = $("#eingabe");
  $("#eingabe-form").onsubmit = (e) => {
    e.preventDefault(); const t = ta.value.trim(); if (z.laufend || z.anhangLiest) return;
    if (!t) { if (z.anhaenge.length) status("Schreib dazu, was KIplatz mit der Datei machen soll, etwa „Fasse das zusammen“."); return; }


    const daheim = z.zuhause.length && $("#daheim-an").checked;
    const mit = z.anhaenge; z.anhaenge = []; anhaengeZeichnen();
    ta.value = ""; ta.style.height = "auto"; ta.closest(".eingabe-box").classList.remove("breit");
    if (daheim) { dateienFragen(t, daheimPcs()); return; }
    fragen(t, { anhaenge: mit });
  };
  const dateienMerken = (an) => { const g = z.gespraeche.aktuell; if (g) { g.dateien = !!an; speichern(); } daheimLeiste(); };
  $("#daheim-an").onchange = () => dateienMerken($("#daheim-an").checked);
  $("#btn-daheim-suchen").onclick = () => {
    const an = !$("#daheim-an").checked;
    $("#plus-menue").hidden = true; $("#btn-plus").setAttribute("aria-expanded", "false");
    $("#daheim-an").checked = an; dateienMerken(an); ta.focus();
  };
  anhaengeVerdrahten();
  sprechenVerdrahten();

  const verlaufBox = $("#verlauf"), pfeil = $("#btn-nach-unten");
  const pfeilPruefen = () => { pfeil.hidden = document.body.classList.contains("leer") || verlaufBox.scrollHeight - verlaufBox.scrollTop - verlaufBox.clientHeight < 240; };
  verlaufBox.addEventListener("scroll", pfeilPruefen, { passive: true });
  addEventListener("resize", pfeilPruefen);
  pfeil.onclick = () => { verlaufBox.scrollTo({ top: verlaufBox.scrollHeight, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); };
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing && !schmalTouch()) { e.preventDefault(); $("#eingabe-form").requestSubmit(); } });


  const box = ta.closest(".eingabe-box");
  const eingabeBreite = () => {
    box.classList.remove("breit");
    ta.style.height = "auto";
    const zeile = parseFloat(getComputedStyle(ta).lineHeight) || 22;
    const mehrzeilig = !!ta.value && (ta.value.includes("\n") || ta.scrollHeight > zeile * 1.5 + 18);
    box.classList.toggle("breit", mehrzeilig);
  };
  const eingabeHoehe = () => {
    const sichtbar = (window.visualViewport && window.visualViewport.height) || innerHeight;
    eingabeBreite();
    ta.style.height = "auto";
    const grenze = Math.max(72, Math.round(sichtbar * 0.4));
    ta.style.height = Math.min(ta.scrollHeight, grenze) + "px";
    if (ta.scrollHeight > grenze && ta.selectionEnd >= ta.value.length - 1) ta.scrollTop = ta.scrollHeight;

    const gruss = $("#willkommen"), verlauf = $("#verlauf"), einr = $("#einrichten");
    if (gruss && document.body.classList.contains("leer") && (!einr || einr.hidden)) {
      gruss.classList.remove("eng");
      if (gruss.scrollHeight > verlauf.clientHeight + 1) gruss.classList.add("eng");
    }
  };
  ta.addEventListener("input", eingabeHoehe);
  if (window.visualViewport) window.visualViewport.addEventListener("resize", () => { if (ta.value) eingabeHoehe(); });
  $("#btn-stopp").onclick = anhalten;


  const dankeZeile = (i, text) => {
    document.querySelectorAll("#nachrichten .danke-zeile").forEach((x) => x.remove());
    const m = document.querySelector(`#nachrichten .msg[data-i="${i}"]`); if (!m || !text) return;
    const p = document.createElement("p"); p.className = "danke-zeile"; p.setAttribute("role", "status"); p.textContent = text;
    (m.querySelector(".aktionen") || m).after(p);
    setTimeout(() => p.remove(), 6000);
  };

  $("#nachrichten").onclick = (e) => {
    const b = e.target.closest("[data-tun]"); if (!b) return;
    antwortTun(b.dataset.tun, Number(b.closest(".msg")?.dataset.i), b);
  };

  const blattWahl = (d, i) => {
    d.returnValue = ""; d.showModal();
    d.addEventListener("close", () => { if (d.returnValue) antwortTun(d.returnValue, i); }, { once: true });
  };
  const schlechtBlatt = $("#antwort-schlecht");
  $("#as-form").addEventListener("submit", (e) => {
    if (e.submitter?.value !== "senden") return;
    const grund = schlechtBlatt.querySelector("input[name=as-grund]:checked")?.value || "";
    if (!grund && $("#as-vorschlag").value.trim().length < 3) { e.preventDefault(); $("#as-fehler").hidden = false; }
  });
  schlechtBlatt.addEventListener("change", () => {
    $("#as-fehler").hidden = true;
    const gefahr = schlechtBlatt.querySelector("input[name=as-grund]:checked")?.value === "Anstößig oder gefährlich";
    $("#as-hinweis").hidden = !gefahr; $("#as-teilen-zeile").hidden = gefahr;
  });
  $("#as-vorschlag").addEventListener("input", () => { $("#as-fehler").hidden = true; });

  function rueckmeldungFragen(i, titel) {
    const g = z.gespraeche.aktuell, n = g.nachrichten[i]; if (!n) return;
    const frage = [...g.nachrichten.slice(0, i)].reverse().find((x) => x.rolle === "user");
    $("#as-titel").textContent = titel;
    schlechtBlatt.querySelectorAll("input[name=as-grund]").forEach((x) => { x.checked = false; });
    $("#as-vorschlag").value = ""; $("#as-community").checked = false;
    $("#as-fehler").hidden = true; $("#as-hinweis").hidden = true; $("#as-teilen-zeile").hidden = false;
    schlechtBlatt.returnValue = ""; schlechtBlatt.showModal();
    schlechtBlatt.addEventListener("close", async () => {
      if (schlechtBlatt.returnValue !== "senden") return;
      const grund = schlechtBlatt.querySelector("input[name=as-grund]:checked")?.value || "";
      const vorschlag = $("#as-vorschlag").value.trim();
      const gefahr = grund === "Anstößig oder gefährlich";
      const an = !gefahr && vorschlag.length >= 3 && $("#as-community").checked ? "community" : "admin";
      try {
        await holen("/rueckmeldung", { body: { frage: frage?.text || "", antwort: n.text, grund: grund || "Vorschlag zur Antwort", vorschlag, an }, geraet: z.geraet });
        dankeZeile(i, an === "community" ? "Danke. Ein anderes Mitglied prüft deinen Vorschlag, danach gilt er für alle." : "Danke, ist bei uns angekommen. Wir sehen es uns an.");
      } catch (err) { status(err.message); }
    }, { once: true });
  }

  async function antwortTun(art, i, b = null) {
    const g = z.gespraeche.aktuell; const n = g.nachrichten[i]; if (!n) return;
    const frage = [...g.nachrichten.slice(0, i)].reverse().find((x) => x.rolle === "user");
    switch (art) {
      case "pruefen": {
        const rot = Number(n.lieferschein?.pruefung?.rot || 0);
        $("#ap-titel").textContent = rot === 1 ? "1 Satz ohne Quelle. Stimmt das?" : rot > 0 ? `${rot} Sätze ohne Quelle. Stimmt das?` : "Stimmt das?";
        $("#ap-mitglied").hidden = !!n.lieferschein?.mitglied_pruefung;
        blattWahl($("#antwort-pruefen"), i);
        break;
      }
      case "mehr": blattWahl($("#antwort-mehr"), i); break;
      case "details": {
        const dl = $("#ad-inhalt"); dl.replaceChildren();
        for (const [k, v] of detailsZeilen(n)) { const dt = document.createElement("dt"); dt.textContent = k; const dd = document.createElement("dd"); dd.textContent = v; dl.append(dt, dd); }
        $("#antwort-details").returnValue = ""; $("#antwort-details").showModal();
        break;
      }
      case "antwort-melden": rueckmeldungFragen(i, "Antwort melden: was stimmt nicht?"); break;
      case "wiki-vorschlag": if (z.geraet) z.wiki.auf(frage?.text || ""); else status("Das Wiki gibt es mit einem KIplatz-Konto."); break;
      case "dateien-alle": {
        const box = b.closest(".dateien"); const c = [...box.querySelectorAll("input[type=checkbox]")]; const an = c.some((x) => !x.checked);
        c.forEach((x) => { x.checked = an; }); box.dispatchEvent(new Event("change")); b.textContent = an ? "Keine auswählen" : "Alle auswählen";
        break;
      }
      case "dateien-holen": {
        b.disabled = true; b.textContent = "Holt …";
        const geholt = await dateienHolen(n, [...b.closest(".dateien").querySelectorAll("input:checked")].map((x) => ({ id: x.dataset.id, kid: x.dataset.kid })));
        if (geholt?.length) { z.geholt = geholt; b.dataset.tun = "dateien-teilen"; b.textContent = "Sichern oder teilen"; b.disabled = false; }
        else { b.disabled = false; b.textContent = "Aufs Handy holen"; }
        break;
      }
      case "dateien-teilen":
        if (z.geholt?.length) dateienTeilen(z.geholt);
        break;
      case "gut": case "schlecht":
        n.bewertung = n.bewertung === b.dataset.tun ? "" : b.dataset.tun; speichern(); zeichneVerlauf();


        if (n.bewertung && /^[0-9a-f]{20}$/.test(n.lieferschein?.speicher_id || "")) holen(n.bewertung === "schlecht" ? "/speicher-schlecht" : "/speicher-gut", { body: { id: n.lieferschein.speicher_id }, geraet: z.geraet }).catch(() => {});

        if (n.bewertung === "schlecht") rueckmeldungFragen(i, "Was hat nicht gepasst?");
        else dankeZeile(i, n.bewertung === "gut" ? "Danke, dass du die Community unterstützt." : "");
        break;
      case "kopieren": kopieren(n.text); break;
      case "melden": z.platzl?.fehlerMelden({ frage: frage?.text || "", antwort: n.text, modell: n.lieferschein?.modell || "", skill: n.lieferschein?.skill || "" }); break;
      case "teilen": teilen(teilText(frage?.text || "", n.text)); break;
      case "nochmal":

        if (!frage || z.laufend) return;
        if (/^Live nachprüfen: /.test(frage.text)) { fragen(frage.text.replace(/^Live nachprüfen: /, ""), { frisch: true }); return; }
        g.nachrichten.splice(i, 1); speichern();
        fragen(frage.text, { wiederholen: true, vorige: n.auftrag || "" });
        break;
      case "nachpruefen": if (frage) fragen(frage.text.replace(/^Live nachprüfen: /, ""), { frisch: true }); break;
      case "mitglied":
        if (!confirm("Soll ein Mitglied nachschauen, ob diese Antwort stimmt? Frage und Antwort gehen ohne deinen Namen hin.")) return;
        try {
          const r = await holen("/pruefung-anbieten", { body: { frage: frage ? frage.text : "", antwort: n.text, quellen: (n.lieferschein?.quellen_liste || []).map((q) => q.titel) }, geraet: z.geraet });
          (n.lieferschein ||= {}).mitglied_pruefung = { kennung: r.kennung, status: "offen" }; speichern(); zeichneVerlauf();
          status("Angefragt. Das Ergebnis erscheint hier.");
        } catch (err) { status(err.message); }
        break;
    }
  }


  const blatt = $("#gespraech-menue"), umbenennen = $("#umbenennen-dialog");
  let menueFuer = "";
  const menueAuf = (kennung) => {
    const g = z.gespraeche.liste.find((x) => x.kennung === kennung) || z.gespraeche.aktuell;
    menueFuer = g.kennung;
    $("#gm-titel").textContent = z.gespraeche.titel(g); $("#gm-titel").translate = false;
    $("#gm-anheften").lastChild.textContent = g.angeheftet ? "Nicht mehr anheften" : "Anheften";
    $("#gm-farbpunkt").style.background = FARBEN[g.farbe] ? FARBEN[g.farbe][1] : "transparent";
    $("#gm-projekt-raus").hidden = !g.projekt;
    $("#gm-projekt").lastChild.textContent = g.projekt ? "In ein anderes Projekt verschieben" : "In ein Projekt verschieben";
    blatt.returnValue = "";
    blatt.showModal();

    try { getSelection()?.removeAllRanges(); } catch { }
    setTimeout(() => { try { getSelection()?.removeAllRanges(); } catch { } }, 350);
  };
  $("#btn-gespraech-menue").onclick = () => menueAuf(z.gespraeche.aktuellId);
  $("#btn-neu-kopf").onclick = () => $("#btn-neu").click();


  $("#btn-heim").onclick = () => { z.gespraeche.neu(); speichern(); zeichneListe(); zeichneVerlauf(); leisteZu(); };
  blatt.addEventListener("click", (e) => { if (e.target === blatt) blatt.close(); });
  blatt.addEventListener("close", () => {
    const g = z.gespraeche.liste.find((x) => x.kennung === menueFuer);
    if (!g) return;
    switch (blatt.returnValue) {
      case "umbenennen": $("#gm-name").value = z.gespraeche.titel(g); umbenennen.returnValue = ""; umbenennen.showModal(); $("#gm-name").select(); return;
      case "anheften": z.gespraeche.anheften(g.kennung); break;
      case "teilen": teilen(z.gespraeche.alsText(g.kennung)); return;
      case "farbe": farbeWaehlen(g); return;
      case "skill": skillWaehlen(g); return;
      case "projekt": projektWaehlen(g); return;
      case "projekt-raus": z.gespraeche.verschieben(g.kennung, ""); break;
      case "loeschen": if (confirm(`„${z.gespraeche.titel(g)}“ löschen?`)) z.gespraeche.loeschen(g.kennung); else return; break;
      default: return;
    }
    speichern(); zeichneListe(); zeichneVerlauf();
  });

  const farbeDialog = $("#farbe-dialog");
  function farbeWaehlen(g) {
    const box = $("#farbwahl"); box.replaceChildren();
    for (const [schluessel, [name, ton]] of [...Object.entries(FARBEN), ["", ["Keine Farbe", "transparent"]]]) {
      const k = document.createElement("button"); k.value = "f:" + schluessel; k.className = "farbe-knopf";
      k.setAttribute("aria-pressed", String((g.farbe || "") === schluessel));
      const p = document.createElement("span"); p.className = "farbpunkt gross"; p.style.background = ton; p.setAttribute("aria-hidden", "true");
      k.append(p, document.createTextNode(name));
      box.append(k);
    }
    farbeDialog.returnValue = ""; farbeDialog.showModal();
  }
  farbeDialog.addEventListener("click", (e) => { if (e.target === farbeDialog) farbeDialog.close(); });
  let farbeFuerProjekt = "";
  farbeDialog.addEventListener("close", () => {
    const wahl = farbeDialog.returnValue, projekt = farbeFuerProjekt; farbeFuerProjekt = "";
    if (!wahl.startsWith("f:")) return;
    if (projekt) { const p = projekte(); p[projekt] = FARBEN[wahl.slice(2)] ? wahl.slice(2) : ""; projekteSetzen(p); speichern(); zeichneListe(); return; }
    z.gespraeche.farbeSetzen(menueFuer, wahl.slice(2)); speichern(); zeichneListe();
  });

  const nameDialog = $("#name-dialog"); let nameDann = null;
  function nameFragen(titel, wert, dann) {
    $("#nd-titel").textContent = titel; $("#nd-name").value = wert; nameDann = dann; nameDialog.returnValue = ""; nameDialog.showModal(); $("#nd-name").select();
  }

  $("#nd-name").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); nameDialog.close("ok"); } });
  nameDialog.addEventListener("close", () => {
    const n = $("#nd-name").value.replace(/\s+/g, " ").trim().slice(0, 60), dann = nameDann; nameDann = null;
    if (nameDialog.returnValue === "ok" && n && dann) dann(n);
  });
  z.projektNeu = () => nameFragen("Neues Projekt", "", (n) => { const p = projekte(); if (!(n in p)) p[n] = ""; projekteSetzen(p); speichern(); zeichneListe(); });

  const projektWahl = $("#projekt-waehlen");
  function projektWaehlen(g) {
    const box = $("#projekt-liste-wahl"); box.replaceChildren();
    const pmap = projekte();
    const namen = [...new Set([...Object.keys(pmap), ...z.gespraeche.liste.filter((x) => x.projekt).map((x) => x.projekt)])].sort((a, b) => a.localeCompare(b, "de"));
    for (const n of namen) {
      const b = document.createElement("button"); b.className = "zeile"; b.value = "p:" + n;
      const punkt = document.createElement("span"); punkt.className = "farbpunkt"; punkt.style.background = FARBEN[pmap[n]] ? FARBEN[pmap[n]][1] : "transparent";
      b.append(punkt, document.createTextNode(n + (g.projekt === n ? " ✓" : "")));
      box.append(b);
    }
    projektWahl.returnValue = ""; projektWahl.showModal();
  }
  projektWahl.addEventListener("click", (e) => { if (e.target === projektWahl) projektWahl.close(); });
  projektWahl.addEventListener("close", () => {
    const w = projektWahl.returnValue, kennung = menueFuer;
    if (w.startsWith("p:")) { z.gespraeche.verschieben(kennung, w.slice(2)); speichern(); zeichneListe(); }
    else if (w === "neu") nameFragen("Neues Projekt", "", (n) => { const p = projekte(); if (!(n in p)) p[n] = ""; projekteSetzen(p); z.gespraeche.verschieben(kennung, n); speichern(); zeichneListe(); });
  });

  const projektMenue = $("#projekt-menue"); let projektFuer = "";
  function projektMenueAuf(n) {
    projektFuer = n; $("#pm-titel").textContent = n;
    const f = projekte()[n]; $("#pm-farbpunkt").style.background = FARBEN[f] ? FARBEN[f][1] : "transparent";
    projektMenue.returnValue = ""; projektMenue.showModal();
    try { getSelection()?.removeAllRanges(); } catch { }
  }
  projektMenue.addEventListener("click", (e) => { if (e.target === projektMenue) projektMenue.close(); });
  projektMenue.addEventListener("close", () => {
    const n = projektFuer, drin = z.gespraeche.liste.filter((g) => g.projekt === n);
    switch (projektMenue.returnValue) {
      case "umbenennen":
        nameFragen("Projekt umbenennen", n, (neu) => {
          if (neu === n) return;
          const p = projekte(); p[neu] = p[n] || p[neu] || ""; delete p[n]; projekteSetzen(p);
          for (const g of drin) z.gespraeche.verschieben(g.kennung, neu);
          speichern(); zeichneListe();
        });
        return;
      case "farbe": farbeFuerProjekt = n; farbeWaehlen({ farbe: projekte()[n] || "" }); return;
      case "aufloesen":
        if (!confirm(`Projekt „${n}“ auflösen? Die Gespräche bleiben und stehen wieder in der Liste.`)) return;
        for (const g of drin) z.gespraeche.verschieben(g.kennung, "");
        break;
      case "loeschen":
        if (!confirm(drin.length === 1 ? `Projekt „${n}“ samt 1 Gespräch löschen? Das lässt sich nicht rückgängig machen.` : `Projekt „${n}“ samt ${drin.length} Gesprächen löschen? Das lässt sich nicht rückgängig machen.`)) return;
        for (const g of drin) z.gespraeche.loeschen(g.kennung);
        break;
      default: return;
    }
    const p = projekte(); delete p[n]; projekteSetzen(p);
    speichern(); zeichneListe(); zeichneVerlauf();
  });
  umbenennen.addEventListener("close", () => {
    if (umbenennen.returnValue !== "ok") return;
    z.gespraeche.umbenennen(menueFuer, $("#gm-name").value); speichern(); zeichneListe(); zeichneVerlauf();
  });

  let druck = null, langGedrueckt = false;
  $("#liste").addEventListener("pointerdown", (e) => {
    const b = e.target.closest("button[data-kennung], button[data-projekt]"); if (!b) return;
    langGedrueckt = false;
    druck = setTimeout(() => { langGedrueckt = true; nativ?.tippen(); if (b.dataset.projekt !== undefined) projektMenueAuf(b.dataset.projekt); else menueAuf(b.dataset.kennung); }, 550);
  });
  $("#liste").addEventListener("click", (e) => {
    const k = e.target.closest("button[data-projekt]"); if (!k || langGedrueckt) return;
    const zu = projekteZu(); if (zu.has(k.dataset.projekt)) zu.delete(k.dataset.projekt); else zu.add(k.dataset.projekt);
    ablageSchreiben("projekte-zu", [...zu]); zeichneListe();
  });
  for (const ev of ["pointerup", "pointerleave", "pointercancel", "pointermove"]) $("#liste").addEventListener(ev, (e) => { if (ev !== "pointermove" || Math.abs(e.movementY) > 4) clearTimeout(druck); });
  $("#liste").addEventListener("click", (e) => { if (langGedrueckt) { e.stopImmediatePropagation(); e.preventDefault(); langGedrueckt = false; } }, true);
  $("#liste").addEventListener("contextmenu", (e) => {
    const p = e.target.closest("button[data-projekt]"); if (p) { e.preventDefault(); projektMenueAuf(p.dataset.projekt); return; }
    if (e.target.closest("button[data-kennung]")) e.preventDefault();
  });


  $("#btn-konto-hinzu").onclick = () => kontoHinzufuegen();
  $("#btn-konten").onclick = () => kontenBlattAuf();
  $("#btn-konto").onclick = () => emailSchritt("adresse");
  $("#email-form").onsubmit = (e) => { e.preventDefault(); emailCodeSchicken(); };
  $("#code-form").onsubmit = (e) => { e.preventDefault(); emailCodePruefen(); };
  $("#email-code").oninput = () => { if ($("#email-code").value.replace(/\D/g, "").length === 6) emailCodePruefen(); };
  $("#btn-email-neu").onclick = () => emailCodeSchicken();
  $("#btn-email-andere").onclick = () => { $("#anmelde-fehler").textContent = ""; emailSchritt("adresse"); };
  $("#btn-google").onclick = () => kontoAnmelden("", "google", "", anmeldeFenster());
  $("#btn-github").onclick = () => kontoAnmelden("", "github", "", anmeldeFenster());
  $("#btn-anmelden").onclick = async () => {
    const name = $("#name").value.trim() || "Handy", code = $("#code").value.trim().toUpperCase();
    $("#anmelde-fehler").textContent = "";
    if (!code) { $("#anmelde-fehler").textContent = "Bitte den Code eintippen."; return; }
    try { const d = await holen("/geraet-mit-code", { body: { code, name } }); if (await geraetMerken(d, name)) anzeigen(); }
    catch (e) { $("#anmelde-fehler").textContent = e.message; }
  };
  $("#btn-link").onclick = async () => {
    $("#anmelde-fehler").textContent = "";
    try { if (await mitAnmeldecode($("#link").value)) anzeigen(); else $("#anmelde-fehler").textContent = "Das ist kein Anmeldelink."; }
    catch (e) { $("#anmelde-fehler").textContent = e.message; }
  };


  $("#btn-einstellungen").onclick = einstellungenAuf;
  $("#btn-einstellungen-zu").onclick = einstellungenZu;
  for (const b of document.querySelectorAll("#einstellungen [data-seite]")) b.onclick = () => unterseiteAuf(b.dataset.seite);
  for (const b of document.querySelectorAll("#einstellungen [data-zu]")) b.onclick = () => unterseiteZu(b.dataset.zu);
  $("#btn-meineki").onclick = meineKiAuf; $("#btn-meineki-zu").onclick = meineKiZu;
  $("#admin-suche").oninput = (e) => { admin.suche = e.target.value; adminGeraeteZeichnen(); };
  let kontoWarten = 0;
  $("#admin-konto-suche").oninput = () => { clearTimeout(kontoWarten); kontoWarten = setTimeout(adminKontenSuchen, 400); };
  for (const r of document.querySelectorAll('input[name="aussehen"], input[name="schrift"]'))
    r.onchange = () => { z.einst[r.name] = r.value; ablageSchreiben("einstellungen", z.einst); aussehenSchreiben(); einstAnwenden(); };

  for (const r of document.querySelectorAll('input[name="sprache"]'))
    r.onchange = () => globalThis.kiplatzSprache.setzen(r.value);

  const ueberDich = (anrede, wohnort) => {
    z.einst.anrede = sauber(anrede, 40); z.einst.wohnort = sauber(wohnort, 60); z.einst.eingerichtet = true;
    ablageSchreiben("einstellungen", z.einst);
  };
  $("#einrichten").onsubmit = (e) => {
    e.preventDefault(); ueberDich($("#ein-name").value, $("#ein-ort").value);
    zeichneVerlauf();
    status(z.einst.anrede || z.einst.wohnort ? "Gespeichert. Ändern kannst du alles unter Einstellungen, „Meine KI“." : "Du findest die Fragen unter Einstellungen, „Meine KI“.");
    $("#eingabe").focus();
  };
  $("#btn-ein-spaeter").onclick = () => { z.einst.eingerichtet = true; ablageSchreiben("einstellungen", z.einst); zeichneVerlauf(); status("Du findest die Fragen unter Einstellungen, „Meine KI“."); };


  $("#btn-ein-meineki").onclick = () => { ueberDich($("#ein-name").value, $("#ein-ort").value); zeichneVerlauf(); einstellungenAuf(); meineKiAuf(); };

  $("#btn-mk-speichern").onclick = () => {
    const fehler = meineKiSpeichern(meineKiWahl());
    meineKiZeichnen(); meineKiZeile(); $("#mk-ok").textContent = fehler || "Gespeichert. KIplatz antwortet ab jetzt so, in jedem Gespräch.";
  };
  $("#btn-mk-weg").onclick = () => {
    if (!confirm("„Meine KI“ zurücksetzen? Der Skill „meine-ki“ wird entfernt.")) return;
    skillAblage.entfernen(meineKi.NAME); delete z.einst.meineKi; ablageSchreiben("einstellungen", z.einst);
    meineKiZeichnen(); meineKiZeile(); $("#mk-ok").textContent = "Zurückgesetzt. KIplatz antwortet wieder wie für alle.";
  };
  for (const id of ["#e-anrede", "#e-wohnort"]) $(id).onchange = () => {
    ueberDich($("#e-anrede").value, $("#e-wohnort").value); $("#e-ueber-dich-ok").textContent = "Gespeichert.";
    meineKiZeile(); zeichneVerlauf();
  };
  $("#e-standort").onchange = async (e) => {
    z.einst.standort = e.target.checked; ablageSchreiben("einstellungen", z.einst);
    $("#e-standort-hinweis").hidden = true;
    if (!e.target.checked) { localStorage.removeItem("kiplatz.ort"); return; }

    const { pos, nein } = await standortHolen();

    const hinweis = $("#e-standort-hinweis");
    if (nein) {
      e.target.checked = false; z.einst.standort = false; ablageSchreiben("einstellungen", z.einst);
      hinweis.textContent = "Ohne deine Erlaubnis bleibt der Standort aus. Erlauben kannst du ihn jederzeit in den Einstellungen deines Handys.";
    } else hinweis.textContent = pos ? "Standort für Wetterfragen ist an." : "Standort ist an. Gerade war er nicht zu finden, bei der nächsten Wetterfrage versucht es KIplatz noch einmal.";
    hinweis.hidden = false; status("");
  };
  $("#e-lernen").onchange = async (e) => {
    const an = e.target.checked, h = $("#e-lernen-hinweis");
    e.target.disabled = true;
    try {
      const r = await holen("/lernen", { body: { an }, geraet: z.geraet });
      e.target.checked = r.an !== false;
      h.textContent = r.an !== false ? "Danke. Deine Fragen helfen KIplatz ab jetzt beim Lernen." : "Ausgeschaltet. Deine Fragen, Daumen und Berichtigungen kommen nicht mehr in die Lernliste.";
    } catch (err) { e.target.checked = !an; h.textContent = err.message; }
    e.target.disabled = false; h.hidden = false;
  };

  const kamera = !!navigator.mediaDevices?.getUserMedia;
  $("#btn-zuhause-kamera").hidden = !kamera; $("#zuhause-kamera-hinweis").hidden = !kamera;
  $("#btn-zuhause-kamera").onclick = () => { $("#e-zuhause").classList.remove("gut"); qrScannen(); };
  $("#qr-abbrechen").onclick = () => qrStoppen();

  $("#btn-pc-qr").onclick = () => { verlauf.alleZu(); if (kamera) qrScannen("pc"); else status("Dieses Handy bietet keine Kamera an. Melde den PC dort mit „Mit KIplatz-Konto anmelden“ an."); };
  $("#qr-dialog").addEventListener("close", () => qrStoppen());
  document.addEventListener("visibilitychange", () => { if (document.hidden) qrStoppen(); });
  $("#e-zuhause-code").addEventListener("input", () => { $("#e-zuhause").textContent = ""; $("#e-zuhause").classList.remove("gut"); });
  $("#btn-zuhause-koppeln").onclick = async () => {
    if (!$("#e-zuhause-code").value.trim()) { $("#e-zuhause").textContent = "Tipp zuerst den Code vom PC ein, oder scanne ihn mit der Kamera."; return; }
    try { await zuhauseKoppeln($("#e-zuhause-code").value); $("#e-zuhause-code").value = ""; }
    catch (e) { $("#e-zuhause").textContent = e.message || "Das Verbinden hat nicht geklappt. Probier es bitte noch einmal."; }
  };
  $("#btn-anmeldelink").onclick = async () => {
    try {
      const d = await holen("/anmeldelink", { body: {}, geraet: z.geraet });
      await kopieren(`https://kiplatz.at/app#c=${encodeURIComponent(d.code)}`);
      status("Anmeldelink kopiert. Er gilt 10 Minuten und nur einmal.");
    } catch (e) { status(e.message); }
  };
  $("#btn-meine-daten").onclick = async () => {
    const box = $("#meine-daten");
    try {
      const d = await holen("/meine-daten", { body: {}, geraet: z.geraet }); const g = d.geraet || {};
      box.replaceChildren();
      for (const [k, v] of [["Name", g.name], ["Kennung", g.kennung], ["Schlüssel (Prüfwert)", g.schluessel], ["Dabei seit", g.angelegt ? wann(g.angelegt) : ""], ["Credits", g.credits ?? 0], ["Offene Fragen", d.offene_fragen ?? 0]]) {
        const p = document.createElement("div"); p.textContent = `${k}: ${v ?? ""}`; box.append(p);
      }
      if (d.sonst) { const p = document.createElement("p"); p.textContent = d.sonst; box.append(p); }
      box.hidden = false;
    } catch (e) { box.textContent = e.message; box.hidden = false; }
  };
  $("#btn-alle-loeschen").onclick = () => {
    if (!confirm("Alle Gespräche auf diesem Gerät löschen? Das lässt sich nicht rückgängig machen.")) return;
    z.gespraeche = new Gespraeche(); speichern(); zeichneListe(); zeichneVerlauf(); verlauf.alleZu();
  };
  $("#btn-ueberall-abmelden").onclick = async () => {
    if (!confirm("Auf allen anderen Geräten abmelden? Dort musst du dich danach neu anmelden; PCs arbeiten weiter für die Community, aber nicht mehr für dein Konto.")) return;
    try { const r = await holen("/ueberall-abmelden", { body: {}, geraet: z.geraet }); await geraeteZeichnen(); $("#geraete-meldung").textContent = r.text || ""; }
    catch (e) { $("#geraete-meldung").textContent = e.message; }
  };

  $("#btn-konto-loeschen-start").onclick = () => { verlauf.alleZu(); loeschenStart(); };
  $("#ld-weiter").onclick = () => { $("#ld-meldung").textContent = "Einen Moment …"; kontoAnmelden("loeschen", "", "", anmeldeFenster()); };

  $("#ld-wort").oninput = (e) => { $("#ld-loeschen").disabled = !["löschen", "delete"].includes(e.target.value.trim().toLowerCase()); };
  $("#ld-loeschen").onclick = () => { if (confirm("Dieses Konto jetzt löschen? Das lässt sich nicht rückgängig machen.")) loeschenAusfuehren(); };
  $("#af-ja").onclick = () => anmeldenAntworten(true);
  $("#af-nein").onclick = () => anmeldenAntworten(false);
  $("#ld-ja").onclick = () => loeschenAntworten(true);
  $("#ld-nein").onclick = () => loeschenAntworten(false);
  for (const k of document.querySelectorAll("[data-ld-zu]")) k.onclick = () => { loeschNachweis = null; $("#loeschen-dialog").close(); };
  $("#btn-abmelden").onclick = async () => {
    if (!confirm("Von diesem Gerät abmelden? Zum Wiederkommen meldest du dich wieder mit deinem KIplatz-Konto an.")) return;

    if (z.geraet?.konto) { try { await holen("/geraet-abmelden", { body: { kennung: z.geraet.kennung }, geraet: z.geraet, zeitlimit: 8000 }); } catch { } }
    await platzlTrennen();
    z.platzl?.einstellungenZeigen();
    await tresor.loeschen("geraet"); await tresor.loeschen("abgleich"); localStorage.removeItem("kiplatz." + konten.name("abgleich-zuordnung")); z.geraet = null;

    konten.vergessen();
    const weiter = konten.andere()[0];
    if (weiter) { konten.wechseln(weiter.fach, `Abgemeldet. Du bist jetzt bei ${konten.anzeige(weiter)}.`); return; }
    verlauf.alleZu(); anzeigen();
  };


  document.addEventListener("keydown", (e) => {
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === "k") { e.preventDefault(); if (schmal()) leisteAuf(); sucheAuf(); }
    else if (mod && e.shiftKey && e.key.toLowerCase() === "o") { e.preventDefault(); $("#btn-neu").click(); }
    else if (e.key === "Escape") { if (!verlauf.zurueck()) leisteZu(); }
  });
  addEventListener("resize", () => { if (!schmal()) $("#schleier").hidden = true; $("#leiste").inert = schmal() && !document.body.classList.contains("leiste-offen"); });
  $("#leiste").inert = schmal();
}

function wischenVerdrahten() {
  const leiste = $("#leiste"), schleier = $("#schleier");
  let w = null;
  const offen = () => document.body.classList.contains("leiste-offen");
  const setzen = (anteil) => {
    leiste.style.transform = `translateX(${(anteil - 1) * 102}%)`;
    schleier.hidden = false;
    schleier.style.opacity = String(anteil);
  };
  const loesen = () => { leiste.style.transition = ""; leiste.style.transform = ""; schleier.style.transition = ""; schleier.style.opacity = ""; };

  document.addEventListener("touchstart", (e) => {
    w = null;
    if (e.touches.length !== 1 || !schmal() || !z.geraet || e.target.closest?.("input, textarea, pre, table, dialog, .seite")) return;
    const t = e.touches[0];
    if (amBrowserRand(t.clientX)) return;
    w = { x0: t.clientX, y0: t.clientY, start: offen() ? 1 : 0, breite: leiste.getBoundingClientRect().width || 300, zieht: false, punkte: [[e.timeStamp, t.clientX]] };
  }, { passive: true });

  document.addEventListener("touchmove", (e) => {
    if (!w) return;
    const t = e.touches[0], dx = t.clientX - w.x0, dy = t.clientY - w.y0;
    if (!w.zieht) {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;

      if (Math.abs(dy) > Math.abs(dx) || (w.start === 0 && dx < 0) || (w.start === 1 && dx > 0)) { w = null; return; }
      w.zieht = true;
      leiste.style.transition = "none"; schleier.style.transition = "none";
    }
    e.preventDefault();
    w.punkte.push([e.timeStamp, t.clientX]);
    if (w.punkte.length > 5) w.punkte.shift();
    setzen(Math.min(1, Math.max(0, w.start + dx / w.breite)));
  }, { passive: false });

  const ende = (e) => {
    if (!w || !w.zieht) { w = null; return; }
    const t = e.changedTouches[0];
    const anteil = Math.min(1, Math.max(0, w.start + (t.clientX - w.x0) / w.breite));
    const [ta, xa] = w.punkte[0];
    const tempo = (t.clientX - xa) / Math.max(1, e.timeStamp - ta);
    const auf = Math.abs(tempo) > 0.35 ? tempo > 0 : anteil > 0.5;
    w = null;

    leiste.style.transition = "transform .2s ease-out"; schleier.style.transition = "opacity .2s ease-out";
    setzen(auf ? 1 : 0);
    setTimeout(() => { loesen(); if (auf) leisteAuf(); else leisteZu(); }, 200);
  };
  document.addEventListener("touchend", ende, { passive: true });
  document.addEventListener("touchcancel", ende, { passive: true });
}


const schmalTouch = () => matchMedia("(pointer: coarse)").matches && !matchMedia("(min-width: 900px)").matches;


function sichtbarMessen() {
  const vv = window.visualViewport;
  if (!vv) return;
  const setzen = () => {
    document.documentElement.style.setProperty("--sichtbar", `${Math.round(vv.height)}px`);
    document.documentElement.style.setProperty("--oben", `${Math.round(vv.offsetTop)}px`);
  };
  document.documentElement.classList.add("sichtbar-gemessen");
  vv.addEventListener("resize", setzen);
  vv.addEventListener("scroll", setzen);
  setzen();
}


const IOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const RAND_DES_BROWSERS = 28;
const amBrowserRand = (x) => !nativ && IOS && x < RAND_DES_BROWSERS;
function seiteWischen(seite, schliessen) {
  let w = null;
  seite.addEventListener("touchstart", (e) => {
    w = null;

    if (e.touches.length !== 1 || e.target.closest?.("input, textarea, select, pre, table, dialog, .pl-kats, .tabelle-rahmen")) return;


    const u = e.target.closest?.(".unterseite"); if (u && u !== seite) return;
    const t = e.touches[0];
    if (amBrowserRand(t.clientX)) return;
    w = { x0: t.clientX, y0: t.clientY, zieht: false, punkte: [[e.timeStamp, t.clientX]] };
  }, { passive: true });
  seite.addEventListener("touchmove", (e) => {
    if (!w) return;
    const t = e.touches[0], dx = t.clientX - w.x0, dy = t.clientY - w.y0;
    if (!w.zieht) {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      if (Math.abs(dy) > Math.abs(dx) || dx < 0) { w = null; return; }
      w.zieht = true;
      seite.style.transition = "none";
    }
    e.preventDefault();
    w.punkte.push([e.timeStamp, t.clientX]);
    if (w.punkte.length > 5) w.punkte.shift();
    seite.style.transform = `translateX(${Math.max(0, dx)}px)`;
  }, { passive: false });
  const ende = (e) => {
    if (!w || !w.zieht) { w = null; return; }
    const dx = Math.max(0, e.changedTouches[0].clientX - w.x0);
    const [t0, x0] = w.punkte[0], [t1, x1] = w.punkte[w.punkte.length - 1];
    const tempo = (x1 - x0) / Math.max(1, t1 - t0);
    w = null;
    seite.style.transition = "transform .2s ease";
    if (dx > seite.clientWidth * 0.35 || (dx > 40 && tempo > 0.5)) {
      seite.style.transform = `translateX(${seite.clientWidth}px)`;
      setTimeout(() => { schliessen(); seite.style.transition = ""; seite.style.transform = ""; }, 190);
    } else {
      seite.style.transform = "";
      setTimeout(() => { seite.style.transition = ""; }, 210);
    }
  };
  seite.addEventListener("touchend", ende);
  seite.addEventListener("touchcancel", ende);
}

function blattWischen(d) {
  let start = null;
  d.addEventListener("click", (e) => { if (e.target === d) d.close(""); });
  d.addEventListener("touchstart", (e) => {
    if (e.touches.length !== 1 || e.target.closest("input, textarea, select") || d.scrollTop > 0) { start = null; return; }
    start = { y: e.touches[0].clientY, t: Date.now(), dy: 0 };
    d.style.transition = "none";
  }, { passive: true });
  d.addEventListener("touchmove", (e) => {
    if (!start) return;
    start.dy = Math.max(0, e.touches[0].clientY - start.y);
    d.style.transform = start.dy ? `translateY(${start.dy}px)` : "";
  }, { passive: true });
  const ende = () => {
    if (!start) return;
    const { dy, t } = start; start = null;
    d.style.transition = "transform .18s ease";
    const schnell = dy > 30 && dy / Math.max(1, Date.now() - t) > 0.6;
    if (dy > Math.min(120, d.offsetHeight * 0.3) || schnell) {
      d.style.transform = `translateY(${d.offsetHeight}px)`;
      setTimeout(() => { d.close(""); d.style.transform = ""; d.style.transition = ""; }, 170);
    } else d.style.transform = "";
  };
  d.addEventListener("touchend", ende);
  d.addEventListener("touchcancel", ende);
}

async function start() {
  try { sessionStorage.removeItem("kiplatz.laden-versuche"); } catch { }
  sichtbarMessen();
  document.querySelectorAll("dialog.blatt").forEach(blattWischen);
  seiteWischen($("#einstellungen"), einstellungenZu);
  for (const s of document.querySelectorAll("#einstellungen .unterseite")) seiteWischen(s, () => unterseiteZu(s.id));
  seiteWischen($("#meineki"), meineKiZu);
  seiteWischen($("#platzl"), () => z.platzl.zurueck());
  seiteWischen($("#mithelfen"), () => z.mithelfen.zurueck());
  seiteWischen($("#wiki"), () => z.wiki.zurueck());
  seiteWischen($("#bestenliste"), () => z.bestenliste.zurueck());
  z.einst = Object.assign(z.einst, ablageLesen("einstellungen", {}));
  const handy = aussehenLesen();
  if (handy) Object.assign(z.einst, handy); else aussehenSchreiben();
  einstAnwenden();
  z.gespraeche = Gespraeche.aus(ablageLesen("gespraeche", null));


  z.gespraeche.neu();
  try { z.geraet = await tresor.lesen("geraet"); } catch { z.geraet = null; }
  z.abgleich = new Abgleich({ holen, tresor, gespraeche: () => z.gespraeche, geraet: () => z.geraet, speichern: () => ablegen(), projekte, projekteSetzen });
  if (z.geraet && !(z.geraet.kennung && z.geraet.schluessel)) z.geraet = null;
  if (z.geraet) konten.merken(z.geraet);
  verdrahten();
  z.platzl = platzlSeite({ holen, geraet: () => z.geraet, status, skillVerwenden: skillDialogAuf });
  skillsVerdrahten();
  z.platzl.einstellungenZeigen();
  $("#btn-platzl").addEventListener("click", () => leisteZu());
  z.bestenliste = bestenlisteSeite({ holen, geraet: () => z.geraet, status });
  z.wiki = wikiSeite({ holen, geraet: () => z.geraet, status });
  z.mithelfen = mithelfenSeite({ holen, geraet: () => z.geraet, platzlAuf: () => z.platzl.auf() });


  const rueckkehr = await kontoRueckkehr();
  $("#ff-zu").addEventListener("click", () => { try { window.close(); } catch { } });
  if (!rueckkehr && istAnmeldefenster()) fensterFertig();
  try { z.zuhause = zuhause.liste(await tresor.lesen("zuhause")); } catch { z.zuhause = []; }
  daheimLeiste();
  zuhauseAbgleichen();
  if (!rueckkehr && /[?&]code=|#c=|#zuhause=|#pc=/.test(location.href)) { const url = location.href; history.replaceState(null, "", location.pathname); await linkVonAussen(url); }
  nativ?.beiLink(linkVonAussen);

  if (!nativ && IOS && !navigator.standalone && !matchMedia("(display-mode: standalone)").matches) $("#ios-tipp").hidden = false;
  nativ?.beiRueckkehr(() => { appStand(); stand(); pruefStand(); });
  nativ?.beiZurueck?.(() => {
    const dlg = $("#gespraech-menue");
    if (dlg.open) { dlg.close(); return true; }
    if (verlauf.zurueck()) return true;
    if (document.body.classList.contains("leiste-offen")) { leisteZu(); return true; }
    return false;
  });
  anzeigen();
  const gewechselt = konten.nachricht();
  if (gewechselt) { if (z.geraet) status(gewechselt); else anmeldeInfo(gewechselt); }
  appStand();
  kontoAbholen();

  if (z.geraet && (await import("./platzl.js")).wartet()) z.platzl.auf();

  if (z.geraet && location.hash === "#admin") { history.replaceState(null, "", location.pathname); einstellungenAuf(); adminZeichnen(true); }

  if (location.hash === "#konto-loeschen") { history.replaceState(null, "", location.pathname); loeschenStart(); }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") { kontoAbholen(); z.platzl.abholen({ ruhig: true }); abgleichBald(500); neueFassung(); } });
  addEventListener("pageshow", neueFassung);
  abgleichBald(1500);
  setInterval(abgleichen, 60000);
  addEventListener("pageshow", () => kontoAbholen());
  addEventListener("focus", () => kontoAbholen());
}

start();


function meineKiZeichnen() {
  const MK_WIE = [["laenge", "Länge"], ["aufbau", "Aufbau"], ["anrede", "Anrede"], ["niveau", "Wissen"]];
  const w = meineKi.bereinigen(z.einst.meineKi), B = meineKi.BAUSTEINE, box = $("#mk-fragen");
  const feld = (legende, kinder) => { const f = document.createElement("fieldset"); f.className = "wahl"; const l = document.createElement("legend"); l.textContent = legende; f.append(l, ...kinder); return f; };
  const wahl = (typ, name, wert, titel, an) => {
    const l = document.createElement("label"), i = document.createElement("input");
    i.type = typ; i.name = name; i.value = wert; i.checked = an; l.append(i, " " + titel); return l;
  };
  const eingabe = (id, beschriftung, platz, max, wert, hinweis = "") => {
    const l = document.createElement("label"), i = document.createElement("input");
    i.id = id; i.maxLength = max; i.placeholder = platz; i.value = wert; l.append(beschriftung);
    if (hinweis) { const s = document.createElement("small"); s.textContent = hinweis; l.append(s); }
    l.append(i); return l;
  };
  const sprache = eingabe("mk-sprache", "Welche Programmiersprache?", "z. B. Python, Rust", 40, w.sprache);

  const quellen = document.createElement("p");
  quellen.className = "leise klein";
  quellen.append("Zu Programmieren, Web und KI am eigenen PC hat die Community geprüfte, frei verwendbare Quellen: die Python-Dokumentation, die Web-Dokumentation MDN und die Ollama-Dokumentation. Wählst du so ein Thema, zieht KIplatz bei einer passenden Frage Fundstellen daraus vor. Dafür reisen nur die Namen deiner Themen mit der Frage mit. ");
  const vorschlagen = document.createElement("a");
  vorschlagen.href = "https://kiplatz.at/wiki/meldung-schreiben/"; vorschlagen.target = "_blank"; vorschlagen.rel = "noopener"; vorschlagen.id = "mk-quelle-vorschlagen";
  vorschlagen.textContent = "Fehlt dir eine Quelle? Quelle vorschlagen";
  quellen.append(vorschlagen);
  box.replaceChildren(
    feld("Wofür willst du KIplatz vor allem?", B.wofuer.map((b) => wahl("checkbox", "mk-wofuer", b.id, b.titel, w.wofuer.includes(b.id)))),
    quellen,
    sprache,
    ...MK_WIE.map(([f, t]) => feld(t, [wahl("radio", "mk-" + f, "", "egal", !w[f]), ...B[f].map((b) => wahl("radio", "mk-" + f, b.id, b.titel, w[f] === b.id))])),
    feld("Was soll KIplatz nie tun?", B.nie.map((b) => wahl("checkbox", "mk-nie", b.id, b.titel, w.nie.includes(b.id)))),
    eingabe("mk-frei", "Sonst noch etwas?", "z. B. Beispiele bitte aus der Praxis", 300, w.frei, "Geht mit jeder Frage mit, bitte nichts Persönliches eintragen."));
  const prog = box.querySelector('input[name="mk-wofuer"][value="programmieren"]');
  const zeigen = () => { sprache.hidden = !prog.checked; };
  prog.onchange = zeigen; zeigen();
  const da = !!skillAblage.holen(meineKi.NAME);
  $("#mk-vorschau").textContent = da && !meineKi.leer(w) ? meineKi.skillText(w) : "Noch nichts gespeichert.";
  $("#btn-mk-weg").hidden = !da; $("#mk-ok").textContent = "";
}

function meineKiSpeichern(roh) {
  const wahl = meineKi.bereinigen(roh);
  if (meineKi.leer(wahl)) return "Tipp mindestens eine Antwort an.";
  let s;
  try { s = skillAblage.lesen(meineKi.alsSkillMd(wahl)); } catch (e) { return e.message; }
  skillAblage.merken({ ...s, titel: "Meine KI" }); skillAblage.immerSetzen(s.name, true);
  z.einst.meineKi = wahl; ablageSchreiben("einstellungen", z.einst);
  return "";
}

function meineKiZeile() {
  const w = meineKi.bereinigen(z.einst.meineKi), titel = w.wofuer.map((x) => meineKi.BAUSTEINE.wofuer.find((b) => b.id === x).titel);
  const teile = [z.einst.anrede, ...(skillAblage.holen(meineKi.NAME) ? titel : [])].filter(Boolean);
  $("#k-meineki-info").textContent = teile.length ? teile.join(", ") : "Name, Ort, wofür und wie";
}
function meineKiWahl() {
  const alle = (n) => [...document.querySelectorAll(`input[name="${n}"]:checked`)].map((i) => i.value);
  const eins = (f) => document.querySelector(`input[name="mk-${f}"]:checked`)?.value || "";
  return { wofuer: alle("mk-wofuer"), sprache: $("#mk-sprache").value, laenge: eins("laenge"), aufbau: eins("aufbau"), anrede: eins("anrede"), niveau: eins("niveau"), nie: alle("mk-nie"), frei: $("#mk-frei").value };
}
