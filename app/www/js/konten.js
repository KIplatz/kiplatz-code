// SPDX-License-Identifier: AGPL-3.0-or-later
const LISTE = "kiplatz.konten";
const AKTIV = "kiplatz.konto-aktiv";
const NACHRICHT = "kiplatz.konto-nachricht";
const BESITZER = "kiplatz.fach-besitzer";
export const MAX_KONTEN = 5;

const JE_KONTO = new Set([
  "geraet", "abgleich", "zuhause", "platzl", "platzl-client",
  "gespraeche", "projekte", "projekte-zu", "einstellungen", "skills", "abgleich-zuordnung", "platzl-anfrage",
  "anfrage",
]);

const sicher = (f) => (typeof f === "string" && /^(?:|k[0-9a-f]{8})$/.test(f) ? f : "");
let fach = (() => { try { return sicher(localStorage.getItem(AKTIV) || ""); } catch { return ""; } })();

export const aktivesFach = () => fach;


export function name(n) {
  return fach && JE_KONTO.has(n) ? `${n}.${fach}` : n;
}

export function liste() {
  try {
    const l = JSON.parse(localStorage.getItem(LISTE) || "[]");

    return Array.isArray(l) ? l.filter((k) => k && typeof k === "object" && typeof k.fach === "string" && sicher(k.fach) === k.fach).map((k) => ({
      fach: sicher(k.fach), konto: String(k.konto || "").slice(0, 80), benutzer: String(k.benutzer || "").slice(0, 80), name: String(k.name || "").slice(0, 60),
    })) : [];
  } catch { return []; }
}

function listeSetzen(l) {
  const gesehen = new Set();
  const sauber = l.filter((k) => !gesehen.has(k.fach) && gesehen.add(k.fach));
  try { localStorage.setItem(LISTE, JSON.stringify(sauber)); } catch { }
}


export const kennzeichen = (g) => (g?.benutzer ? "b:" + String(g.benutzer) : g?.konto ? "k:" + String(g.konto) : "");

function besitzerAlle() {
  try { const b = JSON.parse(localStorage.getItem(BESITZER) || "{}"); return b && typeof b === "object" && !Array.isArray(b) ? b : {}; } catch { return {}; }
}


export function fremdesFach(geraet) {
  const b = besitzerAlle()[fach], k = kennzeichen(geraet);
  return !!b && !!k && b !== k;
}


export function inNeuesFach() {
  const f = neuesFach();
  try { localStorage.setItem(AKTIV, f); } catch { }
  fach = f;
  return f;
}


export function merken(geraet) {
  if (!geraet) return;
  const k = kennzeichen(geraet);
  if (k) {
    const b = besitzerAlle();
    if (!b[fach]) { b[fach] = k; try { localStorage.setItem(BESITZER, JSON.stringify(b)); } catch { } }
  }
  const eintrag = { fach, konto: String(geraet.konto || ""), benutzer: String(geraet.benutzer || ""), name: String(geraet.name || "") };
  const l = liste();
  const i = l.findIndex((k) => k.fach === fach);
  if (i >= 0) l[i] = eintrag; else l.push(eintrag);
  listeSetzen(l);
}


export function vergessen() {
  listeSetzen(liste().filter((k) => k.fach !== fach));
}


export function doppelt(geraet) {
  const b = String(geraet?.benutzer || "");
  return b ? liste().find((k) => k.fach !== fach && k.benutzer === b) || null : null;
}

export const andere = () => liste().filter((k) => k.fach !== fach);


export function neuesFach() {
  const belegt = new Set(liste().map((k) => k.fach));
  for (;;) {
    const b = new Uint8Array(4); crypto.getRandomValues(b);
    const f = "k" + [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
    if (!belegt.has(f)) return f;
  }
}


export function wechseln(ziel, nachricht = "") {
  try {
    localStorage.setItem(AKTIV, sicher(ziel));
    localStorage.removeItem("kiplatz.anmeldung");
    if (nachricht) localStorage.setItem(NACHRICHT, String(nachricht).slice(0, 200)); else localStorage.removeItem(NACHRICHT);
  } catch { return false; }
  location.reload();
  return true;
}


export function nachricht() {
  try { const n = localStorage.getItem(NACHRICHT) || ""; localStorage.removeItem(NACHRICHT); return n; } catch { return ""; }
}


export const anzeige = (k) => k.konto || k.name || "Ohne Konto";
