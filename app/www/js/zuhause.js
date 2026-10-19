// SPDX-License-Identifier: AGPL-3.0-or-later
export const VERSION = "KIplatz Zuhause 1";
export const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export const CODE_ZEICHEN = 20;

const enc = new TextEncoder();
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const vonHex = (h) => new Uint8Array((h.match(/../g) || []).map((x) => parseInt(x, 16)));
const sha256 = async (text) => hex(await crypto.subtle.digest("SHA-256", enc.encode(text)));

async function hmac(schluessel, text) {
  const k = await crypto.subtle.importKey("raw", schluessel, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, enc.encode(text)));
}


export function codeNormal(text) {
  let t = String(text || "");
  if (t.includes("zuhause=")) t = t.split("zuhause=")[1];
  t = t.replace(/[\s-]/g, "").toUpperCase();
  return t.length === CODE_ZEICHEN && [...t].every((c) => ALPHABET.includes(c)) ? t : null;
}

export async function schluesselAus(code) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(`${VERSION}\n${code}`)));
}

export async function kennung(schluessel) {
  return (await hmac(schluessel, "kennung")).slice(0, 32);
}


export async function inhalt(nachrichten, skill, modus = "") {
  let s = "";
  for (const n of nachrichten) s += `${n.role}\n${await sha256(n.content)}\n`;
  if (skill) s += `skill\n${await sha256(String(skill.name || "") + "\n" + String(skill.text || ""))}\n`;
  if (modus) s += `modus\n${modus}\n`;
  return sha256(s);
}


export async function unterschreiben(eintrag, nachrichten, skill, modus = "") {
  const schl = vonHex(eintrag.schluessel);
  const zeit = Math.floor(Date.now() / 1000);
  const einmal = hex(crypto.getRandomValues(new Uint8Array(8)));
  const sig = await hmac(schl, `${VERSION}\n${eintrag.kid}\n${zeit}\n${einmal}\n${await inhalt(nachrichten, skill, modus)}`);
  return { kid: eintrag.kid, zeit, einmal, sig, ...(modus ? { modus } : {}) };
}


export async function koppeln(code, holen, geraet) {
  const c = codeNormal(code);
  if (!c) throw new Error(`Der Code hat ${CODE_ZEICHEN} Zeichen. Schau bitte noch einmal, ob alle stimmen, oder halte die Kamera auf den QR-Code.`);
  const schl = await schluesselAus(c);
  const kid = await kennung(schl);
  const r = await holen("/zuhause-koppeln", { body: { kid }, geraet });
  return { kid, schluessel: hex(schl), pc_name: String(r.pc_name || "dein PC").slice(0, 60), seit: new Date().toISOString() };
}


export function herkunftSatz(wert) {
  return {
    daheim: "Beantwortet von deinem PC daheim, mit deinen Unterlagen.",
    dateien: "Gefunden auf deinem PC daheim. Hak an, was du brauchst.",
    daheim_ohne: "Beantwortet von deinem PC daheim, diesmal ohne deine Dateien: Dort ist das Suchen gerade ausgeschaltet, oder dieses Handy ist nicht mehr verbunden.",
    aus: "Dein PC daheim ist aus. Die Community hat ohne deine Unterlagen geantwortet.",
  }[wert] || "";
}


const W = "[\\p{L}\\p{N}_]", VOR = `(?<!${W})`, NACH = `(?!${W})`;
const DATEI_WORT = "(?:datei|dateien|dokument|dokumente|dokumenten|ordner|unterlagen|pdfs?|pdf-datei|word-?datei|word-?dokument|docx?|excel-?datei|excel-?tabelle|xlsx?|scans?)";
const BESITZ = `(?:meine?[nmrs]?|unsere?[nmrs]?)\\s+(?:${W}+\\s+){0,2}?${W}*(?:datei|dateien|dokument${W}*|ordner|unterlagen|pdfs?|word${W}*|excel${W}*|fotos?|bilder|scans?|bewerbung${W}*|rechnung${W}*|vertr(?:a|ä)g${W}*|lebenslauf|zeugnis${W}*|bescheid${W}*|befund${W}*)${NACH}`;
const TUN = /(?:such|find|wo\s+(?:ist|sind|liegt|liegen|hab|habe|finde)|zeig|hol|schick|brauch|gib\s+mir|öffne|oeffne|hast\s+du|gibt\s+es)/u;
const WIE = new RegExp(`^\\s*(?:wie|warum|wieso|weshalb|was\\s+(?:ist|sind|bedeutet|heißt|heisst|macht)|kann\\s+man|welches?\\s+programm)${NACH}`, "u");

const DATEI_WORT_EN = String.raw`(?:files?|documents?|folders?|paperwork|pdfs?|spreadsheets?|scans?)`;
const DATEI_BESITZ_EN = String.raw`(?:my|our)\s+(?:\S+\s+){0,2}?(?:files?|documents?|folders?|paperwork|pdfs?|spreadsheets?|photos?|pictures?|scans?|applications?|invoices?|bills?|contracts?|cv|resume|certificates?|payslips?|tax\s+returns?|receipts?|letters?)`;
const DATEI_TUN_EN = String.raw`(?:find|search|look\s+for|where\s+(?:is|are|did\s+i\s+(?:put|save))|where's|show\s+me|fetch|get\s+me|send\s+me|i\s+need|open|do\s+you\s+have|is\s+there)`;
const DATEI_WIE_EN = String.raw`\s*(?:how|why|what|which|should|explain|write|can\s+you\s+(?:explain|write|tell))`;
export function istDateifrage(text) {
  const t = String(text || "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
  if (!t || WIE.test(t) || new RegExp("^" + DATEI_WIE_EN + NACH, "u").test(t)) return false;
  if (new RegExp(VOR + DATEI_WORT + NACH, "u").test(t) && TUN.test(t)) return true;
  if (new RegExp(VOR + BESITZ, "u").test(t) && TUN.test(t)) return true;
  return new RegExp(VOR + DATEI_TUN_EN + NACH, "u").test(t)
    && (new RegExp(VOR + DATEI_WORT_EN + NACH, "u").test(t) || new RegExp(VOR + DATEI_BESITZ_EN + NACH, "u").test(t));
}


export async function dateiEntschluesseln(eintrag, id, blob) {
  if (blob.length < 29 || blob[0] !== 1) throw new Error("Die Datei kam in einer unbekannten Form an.");
  const roh = await crypto.subtle.importKey("raw", vonHex(eintrag.schluessel), "HKDF", false, ["deriveKey"]);
  const k = await crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: enc.encode("kiplatz-zuhause-datei-v1") },
    roh, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  try {
    return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: blob.slice(1, 13), additionalData: enc.encode(`kiplatz-datei:${id}`) }, k, blob.slice(13)));
  } catch { throw new Error("Die Datei ließ sich nicht entschlüsseln; unterwegs wurde sie verändert oder der Schlüssel passt nicht."); }
}

const ARTEN = { pdf: "application/pdf", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", doc: "application/msword",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", xls: "application/vnd.ms-excel", jpg: "image/jpeg", jpeg: "image/jpeg",
  png: "image/png", heic: "image/heic", txt: "text/plain", mp4: "video/mp4", mov: "video/quicktime", zip: "application/zip" };
export const dateiArt = (name) => ARTEN[String(name).split(".").pop().toLowerCase()] || "application/octet-stream";


export function liste(wert) {
  const l = Array.isArray(wert) ? wert : (wert ? [wert] : []);
  return l.filter((e) => e && e.kid && e.schluessel);
}


export function groesse(b) {
  const n = Number(b) || 0;
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  return `${(n / 1024 / 1024).toLocaleString(kiplatzSprache.datumSprache(), { maximumFractionDigits: 1 })} MB`;
}
