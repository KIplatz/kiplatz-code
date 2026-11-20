// SPDX-License-Identifier: AGPL-3.0-or-later
import * as fk from "./frage-krypto.js";
import * as R from "./regeln.js";
import { REGELN } from "./regeln-daten.js";


export const WURZELN = Array.isArray(REGELN.beglaubigung) ? REGELN.beglaubigung : [];
export const bereit = () => WURZELN.length > 0;
export const ABSCHNITTE_MAX = 16;
const SPERRE = "kiplatz.sperrliste";

function ablageLesen() { try { return JSON.parse(globalThis.localStorage?.getItem(SPERRE) || "null"); } catch { return null; } }
function ablageSchreiben(w) { try { globalThis.localStorage?.setItem(SPERRE, JSON.stringify(w)); } catch { } }


export async function empfaengerAuswerten(antwort) {
  const st = await new fk.Sperrstand(WURZELN, ablageLesen()).laden();
  if (await st.nehmen(antwort?.sperrliste)) ablageSchreiben(st.liste);
  const gesperrt = st.gesperrt, empf = {}, unterschriften = new Set();
  for (const e of Array.isArray(antwort?.empfaenger) ? antwort.empfaenger : []) {
    const pub = await fk.empfaengerPruefen(e, WURZELN, { gesperrt });
    if (pub) { empf[String(e.kennung || "").slice(0, 32)] = pub; unterschriften.add(String(e.unterschrift.punkt)); }
  }
  const a = antwort?.abschnitt;
  const abschnitt = a?.schluessel && await fk.beglaubigungPruefen(WURZELN, a.schluessel, a.beglaubigung, undefined, "abschnitt") ? a.schluessel : null;
  const online = Number(antwort?.fragen?.rechner_online);

  return { empf, unterschriften, anzahl: Object.keys(empf).length, online: Number.isFinite(online) ? online : null, notAus: antwort?.not_aus || null, abschnitt };
}


export function vorher(text) {
  return { krise: R.krisenhilfeAntwort(text), haus: R.hausordnungPruefen(text) };
}
export const KRISENHILFE = R.KRISENHILFE;
export const HAUSORDNUNG = R.HAUSORDNUNG;
export const speicherFreigabe = R.speicherFreigabe;


export async function verschliessen(nachrichten, empf, { skill = null, fachgebiete = [], zone = null, frisch = false, speicher = true } = {}) {
  const gemasked = (nachrichten || []).filter((n) => n && typeof n.content === "string")
    .map((n) => ({ role: n.role, content: n.role === "user" ? R.unkenntlich(n.content) : n.content }));
  const [schl, kern] = speicher && !frisch ? await R.speicherFreigabe(gemasked, { skill }) : ["", ""];
  const inhalt = { nachrichten: gemasked, frisch: !!frisch, ...(skill ? { skill } : {}), ...(fachgebiete?.length ? { fachgebiete } : {}),
    ...(Number.isInteger(zone) ? { zone } : {}), speicher_ok: !!schl, ...(schl ? { speicher_frage: kern } : {}) };
  const v = await fk.frageVerschliessen(inhalt, empf);
  return { v, body: { verschlossen: v.paket, skill: !!skill, ...(schl ? { speicher: schl, speicher_frage: kern } : {}) } };
}

export const empfang = (v) => new fk.Empfang(v);


export function offenAnnehmen(r, freigegeben) {
  return !!freigegeben && typeof r?.text === "string" && R.hausordnungPruefen(r.text).ok;
}


export async function teile(r, e) {
  const aus = { schritt: "", teil: "" };
  const felder = [["schritt_v", "schritt"], ["teil_v", "teil"]].filter(([f]) => r?.[f]).sort((a, b) => (r[a[0]].n || 0) - (r[b[0]].n || 0));
  for (const [feld, ziel] of felder) {
    if (!e.istNeu(r[feld])) continue;
    try { aus[ziel] = String((await e.oeffnen(r[feld])).daten.text || "").slice(0, 12000); } catch { }
  }
  return aus;
}


const vonEmpfaenger = (r, unterschriften) => !!r?.sig_schluessel && unterschriften instanceof Set && unterschriften.has(String(r.sig_schluessel.punkt));

export async function lesen(r, v, e, { abschnitt = null, unterschriften = null } = {}) {
  let offen, gel;
  try {
    offen = await e.oeffnen(r.nachricht);
    gel = await e.antwortLesen(offen, r.sig_schluessel);
  } catch { return { ok: false, code: "OEFFNEN" }; }
  if (!gel.ok || !vonEmpfaenger(r, unterschriften)) return { ok: false, code: "UNTERSCHRIFT" };
  if (!R.hausordnungPruefen(gel.text).ok) return { ok: false, code: "PLATZORDNUNG" };
  const ls = { ...gel.lieferschein };
  const ab = ls.abschnitte;
  delete ls.abschnitte;
  if ("uebersetzt_s" in ls) {
    ls.pruefung_selbst = false;
  } else if ((Array.isArray(ab) && ab.length) || (ls.pruefung && typeof ls.pruefung === "object")) {

    const auszuege = [];
    let bestaetigt = 0;
    for (const a of (Array.isArray(ab) ? ab : []).slice(0, ABSCHNITTE_MAX)) {
      if (!a || typeof a !== "object" || typeof a.text !== "string") continue;
      if (abschnitt && a.sig && await fk.abschnittPruefen(abschnitt, String(a.kennung ?? ""), a.text, a.sig)) bestaetigt++;
      const n = Number(a.nummer || 0);
      if (Number.isInteger(n)) auszuege.push([n, a.text]);
    }
    const pr = R.pruefen(gel.text, auszuege, { englisch: ls.sprache === "en" });
    ls.pruefung = pr; ls.erfunden = pr.text; ls.pruefung_selbst = true;
    ls.abschnitte_bestaetigt = { bestaetigt, gesamt: auszuege.length };
  }
  if (r?.lieferschein?.kleineres_modell || r?.kleineres_modell) ls.kleineres_modell = true;
  return {
    ok: true, text: gel.text, lieferschein: ls,
    beweis: { frage_id: v.frageId, frage_roh: v.roh, antwort: gel.innen, sig: String(offen.daten.sig || "") },
    etikett: { frage_id: v.frageId, pruefsumme: await fk.textPruefsumme(gel.text), etikett_sig: String(offen.daten.etikett_sig || "") },
  };
}


export async function zweitePruefen(z, e, unterschriften = null) {
  if (!z?.nachricht) return null;
  try {
    const gel = await e.antwortLesen(await e.oeffnen(z.nachricht), z.sig_schluessel);
    if (!gel.ok || !vonEmpfaenger(z, unterschriften)) return "UNTERSCHRIFT";
    return R.hausordnungPruefen(gel.text).ok ? "" : "PLATZORDNUNG";
  } catch { return "OEFFNEN"; }
}

export const b64 = (bytes) => { let s = ""; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s); };


const BESUCHER_QUELLEN_MAX = 5, BESUCHER_QUELLEN_ARTEN = ["seite", "nachgeschaut", "wikipedia"];
const BESUCHER_GEMACHT = ["geantwortet", "live nachgeprüft", "nachgeschaut und geantwortet"];
const STEUER = /[\x00-\x1f\x7f<>]/g;
const ZEIT_Z = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/;
const lauter = (t) => String(t ?? "").replace(STEUER, " ").split(/\s+/).filter(Boolean).join(" ");
const zeichen = (t, n) => [...String(t)].slice(0, n).join("");

export function oeffentlicherLink(adresse) {
  const a = String(adresse ?? "").trim();
  if (!a || laenge(a) > 300 || /[\s<>"'`\\]/.test(a)) return "";
  let u;
  try { u = new URL(a); } catch { return ""; }
  const host = u.hostname.toLowerCase();
  if (u.protocol !== "https:" || u.username || u.password || a.split("/")[2]?.includes("@") || !host || !host.includes(".")) return "";
  if (/\.(local|lan|home|internal|localhost)$/.test(host) || /^\d+\.\d+\.\d+\.\d+$/.test(host) || host.startsWith("[")) return "";
  return a;
}
const laenge = (t) => [...String(t)].length;

export function besucherQuellen(ls) {
  const out = [], gesehen = new Set();
  for (const q of Array.isArray(ls?.quellen_liste) ? ls.quellen_liste : []) {
    if (!q || typeof q !== "object" || q.privat || !BESUCHER_QUELLEN_ARTEN.includes(String(q.art ?? ""))) continue;
    const link = oeffentlicherLink(q.adresse);
    const titel = zeichen(lauter(q.titel).replace(/^Nachgeschaut:\s*/, ""), 120);
    if (!link || !titel || gesehen.has(link)) continue;
    gesehen.add(link);
    const n = Number.parseInt(q.nummer || 0, 10);
    out.push({ nummer: Number.isFinite(n) && n > 0 && n < 100 ? n : 0, titel, adresse: link });
    if (out.length >= BESUCHER_QUELLEN_MAX) break;
  }
  return out;
}


export function fuerBesucher(text, ls, dauer) {
  ls = ls && typeof ls === "object" ? ls : {};
  const saetze = [];
  for (const s of Array.isArray(ls.pruefung?.saetze) ? ls.pruefung.saetze : []) {
    if (s && typeof s === "object" && s.text) saetze.push({ text: zeichen(s.text, 2000), farbe: zeichen(s.farbe ?? "", 12) });
  }
  const aus = { status: "fertig", text: String(text ?? ""), saetze, quellen: besucherQuellen(ls), dauer_s: Math.round(Number(dauer || 0) * 10) / 10, ki_erzeugt: true };
  if (ls.angebot === "nachpruefen") aus.angebot = "nachpruefen";
  if (BESUCHER_GEMACHT.includes(String(ls.gemacht ?? ""))) aus.gemacht = String(ls.gemacht);
  if (String(ls.modell ?? "").includes("ohne Modell")) aus.ohne_modell = true;
  if (["verworfen", "nachgeschaut"].includes(String(ls.erste_fassung ?? ""))) aus.erste_fassung = String(ls.erste_fassung);
  const videos = [];
  for (const v of Array.isArray(ls.videos) ? ls.videos : []) {
    const nummer = v && typeof v === "object" ? String(v.nummer ?? "") : "";
    if (/^[A-Za-z0-9_-]{11}$/.test(nummer) && !videos.some((x) => x.nummer === nummer)) videos.push({ nummer, titel: zeichen(lauter(v.titel), 160) });
    if (videos.length >= 2) break;
  }
  if (videos.length) aus.videos = videos;
  const st = ls.stand;
  if (st && typeof st === "object" && ZEIT_Z.test(String(st.nachgeschaut ?? ""))) {
    aus.stand = { nachgeschaut: String(st.nachgeschaut) };
    if (ZEIT_Z.test(String(st.gilt_bis ?? ""))) aus.stand.gilt_bis = String(st.gilt_bis);
  }
  return aus;
}
