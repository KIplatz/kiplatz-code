// SPDX-License-Identifier: AGPL-3.0-or-later
import { REGELN } from "./regeln-daten.js";

const rx = (o, extra = "") => new RegExp(o.q, o.f + extra);
const KRISE_DE = rx(REGELN.krisenhilfe.de), KRISE_EN = rx(REGELN.krisenhilfe.en);
const HART = REGELN.hausordnung.hart.map(([m, g]) => [rx(m), g]);
const WEICH = REGELN.hausordnung.weich.map(([m, g]) => [rx(m, "g"), g]);
const EMAIL = rx(REGELN.unkenntlich.email, "g"), IBAN = rx(REGELN.unkenntlich.iban, "g"), TELEFON = rx(REGELN.unkenntlich.telefon, "g");
const W = REGELN.woerter, P = REGELN.pruefung;
const STOPP = new Set(W.stopp), WORT = rx(W.wort, "g");
const RAHMEN = new Set(P.rahmen), RAHMEN_BEIDE = new Set(P.rahmen_beide);
const SATZ_ENDE = rx(P.satz_ende), QUELLE = rx(P.quelle, "g"), QUELLE_AM_ANFANG = rx(P.quelle, "y"), QUELLE_MARKE = rx(P.quelle_marke, "g");
const ZAHL = rx(P.zahl, "g");
const EINHEITEN = P.einheiten.map(([m, e]) => [rx(m, "g"), e]), EINHEITEN_EN = P.einheiten_en.map(([m, e]) => [rx(m, "g"), e]);
const laenge = (s) => [...s].length;


export function krisenhilfeSprache(text) {
  const t = String(text || "").split(/\s+/).filter(Boolean).join(" ");
  if (!t) return null;
  if (KRISE_DE.test(t)) return "de";
  if (KRISE_EN.test(t)) return "en";
  return null;
}
export function krisenhilfeAntwort(text) {
  const s = krisenhilfeSprache(text);
  return s === "de" ? REGELN.krisenhilfe.text_de : s === "en" ? REGELN.krisenhilfe.text_en : null;
}
export const KRISENHILFE = { gemacht: REGELN.krisenhilfe.gemacht, woher: REGELN.krisenhilfe.woher };


export function hausordnungPruefen(text) {
  let t = String(text || "");
  if (!t.trim()) return { ok: true, grund: "", wort: "", text: "" };
  t = t.replace(/[\u200b\u00ad]/g, "");
  for (const [m, grund] of HART) {
    const f = m.exec(t);
    if (f) return befund(grund, [...f[0]].slice(0, 40).join(""));
  }
  const grenze = Math.max(REGELN.hausordnung.weich_grenze, Math.floor(laenge(t) / REGELN.hausordnung.weich_je_zeichen));
  for (const [m, grund] of WEICH) {
    const treffer = [...t.matchAll(m)];
    if (treffer.length >= grenze) return befund(grund, [...(treffer[0][1] ?? treffer[0][0])].slice(0, 40).join(""));
  }
  return { ok: true, grund: "", wort: "", text: "" };
}
function befund(grund, wort) {
  return { ok: false, grund, wort, text: `Das verstößt gegen die Platzordnung (${grund}) und wird nicht gemerkt.` };
}
export const HAUSORDNUNG = REGELN.hausordnung.text;


export function unkenntlich(text) {
  let t = String(text || "").replace(EMAIL, "[E-Mail-Adresse entfernt]").replace(IBAN, "[Kontonummer entfernt]");
  return t.replace(TELEFON, (m) => (m.replace(/\D/g, "").length >= 8 ? "[Telefonnummer entfernt]" : m));
}


export function woerter(text) {
  const klein = [...String(text || "").toLowerCase()].map((c) => W.umlaut[c] ?? c).join("");
  const out = [];
  for (const m of klein.matchAll(WORT)) {
    let w = m[0];
    if (w.length < 3 || STOPP.has(w)) continue;
    for (let i = 0; i < 3; i++) {
      for (const end of W.enden) {
        if (w.length - end.length >= 4 && w.endsWith(end)) { w = w.slice(0, -end.length); break; }
      }
    }
    out.push(w);
  }
  return out;
}


function einheitlich(text, englisch) {
  let t = String(text || "");
  for (const [m, e] of EINHEITEN.concat(englisch ? EINHEITEN_EN : [])) t = t.replace(m, e);
  return t;
}
function pWoerter(text, englisch) {
  const rahmen = englisch ? RAHMEN_BEIDE : RAHMEN;
  return woerter(einheitlich(text, englisch)).filter((w) => !rahmen.has(w)).map((w) => P.gleich[w] ?? w);
}
const zahlen = (text) => [...String(text || "").matchAll(ZAHL)].map((m) => m[0].replace(",", "."));
function gedeckt(w, pw) {
  if (pw.has(w)) return true;
  if (w.length < P.praefix_ab) return false;
  for (const p of pw) {
    if (p.length >= P.praefix_ab && (p.startsWith(w) || w.startsWith(p) || (w.length >= P.infix_ab && p.length > w.length + 2 && p.includes(w)))) return true;
  }
  return false;
}
export function saetze(text) {
  const out = [];
  for (let zeile of String(text || "").split(/\n+/)) {
    zeile = zeile.trim();
    if (!zeile) continue;
    for (let s of zeile.split(SATZ_ENDE)) {
      s = (s || "").trim();
      if (!s) continue;
      QUELLE_AM_ANFANG.lastIndex = 0;
      const m = QUELLE_AM_ANFANG.exec(s);
      if (out.length && m) {
        out[out.length - 1] = out[out.length - 1] + " " + m[0].trim();
        s = s.slice(m[0].length).trim();
        if (!s) continue;
      }
      out.push(s);
    }
  }
  return out;
}
export function genannteQuellen(satz) {
  const n = new Set();
  for (const m of String(satz).matchAll(QUELLE)) for (const z of (m[1] || "").match(/\d+/g) || []) n.add(Number(z));
  return [...n].sort((a, b) => a - b);
}
const ohneMarkeImSatz = (satz) => String(satz).replace(QUELLE, " ");
export function ohneQuellenmarke(text) {
  return String(text || "").replace(QUELLE_MARKE, "").replace(/\s+([.,;:!?])/g, "$1").trim();
}


export function pruefen(antwort, auszuege, { englisch = false } = {}) {
  const passagen = auszuege.map(([n, t]) => [n, new Set([...pWoerter(t, englisch), ...zahlen(t)])]);
  const ergebnis = [];
  for (const s of saetze(antwort)) {
    const genannt = genannteQuellen(s);
    const kern = ohneMarkeImSatz(s);
    const zl = zahlen(kern);
    const wl = pWoerter(kern, englisch).concat(zl);
    if (!wl.length || (wl.length < P.min_woerter && !passagen.length) || kern.trimEnd().endsWith("?")) {
      ergebnis.push({ text: s, farbe: "unbestimmt", deckung: 0, quelle: null, genannt, widerspruch: false });
      continue;
    }
    let besteN = null, beste = 0, zahlenDa = false;
    for (const [n, pw] of passagen) {
      const d = wl.filter((w) => gedeckt(w, pw)).length / wl.length;
      if (d > beste) { besteN = n; beste = d; zahlenDa = zl.length > 0 && zl.every((z) => pw.has(z)); }
    }
    if (zahlenDa && P.gelb_ab <= beste && beste < P.gruen_ab) beste = P.gruen_ab;
    let farbe;
    if (wl.length < P.min_woerter && beste < P.gruen_ab && !zl.length) farbe = "unbestimmt";
    else if (beste >= P.gruen_ab) farbe = "gruen";
    else if (beste >= P.gelb_ab) farbe = "gelb";
    else farbe = "rot";
    if (zl.length && passagen.length && farbe !== "unbestimmt" && !passagen.some(([, pw]) => zl.some((z) => pw.has(z)))) farbe = "rot";
    const widerspruch = farbe === "rot" && beste === 0 && (genannt.length > 0 || /\bQuelle/.test(s));
    ergebnis.push({ text: s, farbe, deckung: beste, quelle: farbe === "gruen" || farbe === "gelb" ? besteN : null, genannt, widerspruch });
  }
  const zaehl = (f) => ergebnis.filter((x) => x.farbe === f).length;
  const gruen = zaehl("gruen"), gelb = zaehl("gelb"), rot = zaehl("rot"), unbestimmt = zaehl("unbestimmt");
  const wid = ergebnis.filter((x) => x.widerspruch).length, n = ergebnis.length;
  let text;
  if (n === 0) text = "keine Sätze";
  else if (!auszuege.length) text = n === 1 ? "1 Satz, alle ohne Quelle (der Speicher hatte nichts Passendes)." : `${n} Sätze, alle ohne Quelle (der Speicher hatte nichts Passendes).`;
  else {
    const teile = [`${gruen} aus Quellen`, `${gelb} Schlussfolgerungen`, `${rot} ohne Quelle`];
    if (unbestimmt) teile.push(`${unbestimmt} zu kurz zum Prüfen oder Fragen an dich`);
    text = (n === 1 ? "1 Satz: " : `${n} Sätze: `) + teile.join(", ") + ".";
    if (wid) text += wid === 1 ? " 1 Satz nennt eine Quelle, deckt sich aber nicht damit (Widerspruch)." : ` ${wid} Sätze nennen eine Quelle, deckt sich aber nicht damit (Widerspruch).`;
    text += " Wortabgleich mit den Auszügen, keine Wahrheitsprüfung.";
  }
  return {
    saetze: ergebnis.map((x) => ({ ...x, text: ohneQuellenmarke(x.text), deckung: Math.round(x.deckung * 100) / 100 })),
    gruen, gelb, rot, unbestimmt, widersprueche: wid, text,
  };
}


const SP = REGELN.speicher;
const SP_FUELL = new Set(SP.fuell), SP_EN = new Set(SP.en_frage), SP_NIE = new Set(SP.nie), SP_WANDEL_EN = new Set(SP.wandel_en), SP_VGL = new Set(SP.vergleich);
const ZWEI_NAMEN = rx(SP.zwei_namen);
const PY_LEER = /[\t\n\v\f\r\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/;
const WIE_VIELE = new RegExp(String.raw`(?:(?<=[\p{L}\p{N}_])(?![\p{L}\p{N}_])|(?<![\p{L}\p{N}_])(?=[\p{L}\p{N}_]))wie\s+viele?(?:(?<=[\p{L}\p{N}_])(?![\p{L}\p{N}_])|(?<![\p{L}\p{N}_])(?=[\p{L}\p{N}_]))`, "gu");
const WIEVIELE = new RegExp(String.raw`(?:(?<=[\p{L}\p{N}_])(?![\p{L}\p{N}_])|(?<![\p{L}\p{N}_])(?=[\p{L}\p{N}_]))wieviele(?:(?<=[\p{L}\p{N}_])(?![\p{L}\p{N}_])|(?<![\p{L}\p{N}_])(?=[\p{L}\p{N}_]))`, "gu");
const pyStrip = (t) => String(t).replace(new RegExp("^" + PY_LEER.source + "|" + PY_LEER.source + "$", "gu"), "");

function spWoerter(text) {
  let t = String(text || "").normalize("NFKC").toLowerCase();
  t = t.replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss");
  t = t.replace(WIE_VIELE, "wieviel").replace(WIEVIELE, "wieviel");
  return t.match(/[a-z0-9]+/g) || [];
}
const wandeltSich = (w) => w.some((x) => SP.wandel.some((s) => (s === "kost" ? x.startsWith(s) : x.includes(s)))) || w.some((x) => SP_WANDEL_EN.has(x));

export function frageTaugt(nachrichten, { frisch = false, skill = null } = {}) {
  if (frisch || skill || !Array.isArray(nachrichten) || nachrichten.length !== 1) return "";
  const n = nachrichten[0];
  if (!n || n.role !== "user" || typeof n.content !== "string") return "";
  const text = pyStrip(n.content);
  if (!text || laenge(text) > SP.max_frage) return "";
  const w = spWoerter(text);
  if (!w.length || w.length > SP.max_woerter || w.some((x) => SP_NIE.has(x)) || wandeltSich(w)) return "";
  if (w.some((x) => SP_VGL.has(x))) return "";
  const englisch = SP_EN.has(w[0]);
  const kern = [...new Set(w.filter((x) => !SP_FUELL.has(x) && !(englisch && x === "was")).map((x) => SP.gleich[x] ?? x))].sort();
  return kern.length >= 2 ? kern.join(" ") : "";
}


export async function speicherFreigabe(nachrichten, { skill = null } = {}) {
  const kern = frageTaugt(nachrichten, { skill });
  if (!kern) return ["", ""];
  const teile = String(nachrichten[0].content || "").split(PY_LEER).filter(Boolean);

  const m = String(nachrichten[0].content || "").match(new RegExp("^(?:" + PY_LEER.source + ")?[^" + PY_LEER.source.slice(1, -2) + "]+(?:" + PY_LEER.source + ")(.*)$", "su"));
  const rest = teile.length > 1 && m ? m[1] : "";
  if (ZWEI_NAMEN.test(rest)) return ["", ""];
  const h = new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(`kiplatz-antwortspeicher/${SP.format}/${kern}`)));
  return [[...h].map((x) => x.toString(16).padStart(2, "0")).join(""), kern];
}
