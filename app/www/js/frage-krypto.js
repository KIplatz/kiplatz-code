// SPDX-License-Identifier: AGPL-3.0-or-later
import { KryptoFehler, b64, unb64, neuesGeraet, fachPacken, hkdf, aesZu, aesAuf, privatLaden, rohAusJwk, verbinden, zufall } from "./abgleich-krypto.js";

export { KryptoFehler };
const S = globalThis.crypto.subtle;
const text = new TextEncoder();
const KURVE_DH = { name: "ECDH", namedCurve: "P-256" };
const KURVE_SIG = { name: "ECDSA", namedCurve: "P-256" };
export const FASSUNG = 1;
const AUFFUELLEN = 4096;
const ARTEN = ["teil", "schritt", "antwort"];
const ANTWORTSCHLUESSEL_TAGE = 2;

const hexZuBytes = (h) => {
  if (typeof h !== "string" || !/^[0-9a-f]{32}$/.test(h)) throw new KryptoFehler("die Frage-Kennung hat nicht 32 Zeichen");
  return Uint8Array.from(h.match(/../g).map((x) => parseInt(x, 16)));
};
const bytesZuHex = (b) => [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
const sha256 = async (b) => new Uint8Array(await S.digest("SHA-256", b));
const auffuellen = (roh, stufe) => {
  const rest = (stufe - (roh.length % stufe)) % stufe;
  if (!rest) return roh;
  const p = new Uint8Array(roh.length + rest).fill(0x20);
  p.set(roh);
  return p;
};
const bis8 = (n) => { const b = new Uint8Array(8); let x = BigInt(n); for (let i = 7; i >= 0; i--) { b[i] = Number(x & 0xffn); x >>= 8n; } return b; };

function punktPruefen(oeffentlich) {
  if (!oeffentlich || oeffentlich.art !== "p256" || typeof oeffentlich.punkt !== "string") throw new KryptoFehler("unbekannte Art des Schlüssels");
  return unb64(oeffentlich.punkt);
}


async function rohPruefen(oeffentlich, daten, sig) {
  try {
    const s = unb64(String(sig || ""));
    if (s.length !== 64) return false;
    const k = await S.importKey("raw", punktPruefen(oeffentlich), KURVE_SIG, false, ["verify"]);
    return await S.verify({ name: "ECDSA", hash: "SHA-256" }, k, s, daten);
  } catch { return false; }
}
export async function schluesselKennung(oeffentlich) { return bytesZuHex(await sha256(punktPruefen(oeffentlich))); }


const ROLLEN = { pc: "kiplatz-beglaubigung-v1\0", abschnitt: "kiplatz-beglaubigung-abschnitt-v1\0" };
async function beglaubigungDaten(unterschrift, bis, rolle = "pc") {
  if (!(rolle in ROLLEN)) throw new KryptoFehler("unbekannte Rolle der Beglaubigung");
  return verbinden(text.encode(ROLLEN[rolle]), await sha256(punktPruefen(unterschrift)), bis8(bis));
}
async function antwortschluesselDaten(antwort, bis) {
  return verbinden(text.encode("kiplatz-antwortschluessel-v1\0"), await sha256(punktPruefen(antwort)), bis8(bis));
}
const wurzeln = (w) => (Array.isArray(w) ? w : w ? [w] : []);
export async function beglaubigungPruefen(wurzel, unterschrift, beglaubigung, jetzt = Date.now() / 1000, rolle = "pc") {
  try {
    if (!beglaubigung || !Number.isInteger(beglaubigung.bis) || beglaubigung.bis < Math.floor(jetzt)) return false;
    const daten = await beglaubigungDaten(unterschrift, beglaubigung.bis, rolle);
    for (const w of wurzeln(wurzel)) if (await rohPruefen(w, daten, beglaubigung.sig)) return true;
    return false;
  } catch { return false; }
}
export async function antwortschluesselPruefen(e, jetzt = Date.now() / 1000) {
  try {
    const t = Math.floor(jetzt), bis = e.antwort_bis;
    return Number.isInteger(bis) && t <= bis && bis <= t + (ANTWORTSCHLUESSEL_TAGE + 1) * 86400
      && await rohPruefen(e.unterschrift, await antwortschluesselDaten(e.antwort, bis), e.antwort_sig);
  } catch { return false; }
}
export async function sperrlistePruefen(wurzel, liste) {
  try {
    const eintraege = [...new Set((liste.gesperrt || []).map(String))].sort();
    const daten = verbinden(text.encode("kiplatz-sperrliste-v1\0"), bis8(liste.stand), await sha256(text.encode(eintraege.join("\n"))));
    for (const w of wurzeln(wurzel)) if (await rohPruefen(w, daten, liste.sig)) return true;
    return false;
  } catch { return false; }
}

export class Sperrstand {
  constructor(wurzel, gespeichert = null) { this.wurzel = wurzel; this.liste = null; this._gespeichert = gespeichert; }
  async laden() {
    const g = this._gespeichert;
    this._gespeichert = null;
    if (g && wurzeln(this.wurzel).length && await sperrlistePruefen(this.wurzel, g)) this.liste = g;
    return this;
  }
  get gesperrt() { return new Set(this.liste ? this.liste.gesperrt : []); }
  async nehmen(neu) {
    if (!wurzeln(this.wurzel).length || !neu || typeof neu !== "object" || !Number.isInteger(neu.stand)) return false;
    if (!(await sperrlistePruefen(this.wurzel, neu))) return false;
    if (this.liste && neu.stand <= this.liste.stand) return false;
    this.liste = { stand: neu.stand, gesperrt: [...neu.gesperrt].map(String).sort(), sig: neu.sig };
    return true;
  }
}

export async function empfaengerPruefen(e, wurzel, { jetzt = Date.now() / 1000, gesperrt = new Set() } = {}) {
  if (!wurzeln(wurzel).length || !e || typeof e !== "object") return null;
  try {
    if (gesperrt.has(await schluesselKennung(e.unterschrift))) return null;
    if (!(await beglaubigungPruefen(wurzel, e.unterschrift, e.beglaubigung, jetzt))) return null;
    if (!(await antwortschluesselPruefen(e, jetzt))) return null;
    return { art: "p256", punkt: e.antwort.punkt };
  } catch { return null; }
}
export async function abschnittPruefen(oeffentlich, quelle, inhalt, sig) {
  const daten = verbinden(text.encode("kiplatz-abschnitt-v1\0"), await sha256(text.encode(String(quelle))), await sha256(text.encode(String(inhalt))));
  return rohPruefen(oeffentlich, daten, sig);
}
async function sigDaten(frageId, frageRoh, antwortRoh) {
  return verbinden(text.encode("kiplatz-antwort-sig-v1\0"), hexZuBytes(frageId), await sha256(frageRoh), await sha256(antwortRoh));
}
export async function unterschriftPruefen(oeffentlich, frageId, frageRoh, antwortRoh, sig) {
  try { return await rohPruefen(oeffentlich, await sigDaten(frageId, frageRoh, antwortRoh), sig); } catch { return false; }
}

export async function textPruefsumme(t) {

  const n = String(t).normalize("NFC").split(/[\t\n\v\f\r\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/).filter(Boolean).join(" ");
  return bytesZuHex(await sha256(text.encode(n)));
}


export async function frageVerschliessen(inhalt, empfaenger, { zeit = null, frageId = null, rueck = null, k = null, iv = null } = {}) {
  const liste = Object.entries(empfaenger || {});
  if (!liste.length) throw new KryptoFehler("keine Empfänger");
  if (liste.length > 64) throw new KryptoFehler("zu viele Empfänger");
  const fid = frageId || bytesZuHex(zufall(16));
  const r = rueck || await neuesGeraet();
  const voll = { ...inhalt, fassung: FASSUNG, frage_id: fid, zeit: Math.floor(zeit ?? Date.now() / 1000), rueck: r.oeffentlich };
  const roh = auffuellen(text.encode(JSON.stringify(voll)), AUFFUELLEN);
  if (roh.length > 256 * 1024) throw new KryptoFehler("die Frage ist zu lang");
  const kk = k || zufall(32), ivv = iv || zufall(12);
  const schl = await S.importKey("raw", kk, "AES-GCM", false, ["encrypt"]);
  const blob = verbinden(new Uint8Array([FASSUNG]), ivv, await aesZu(schl, ivv, roh, verbinden(text.encode("kiplatz-frage-v1:"), hexZuBytes(fid))));
  const bindung = await sha256(blob);
  const faecher = {};
  for (const [kennung, oeff] of liste) {
    punktPruefen(oeff);
    faecher[String(kennung)] = await fachPacken(kk, oeff, { info: "kiplatz-frage-fach-v1", aad: bindung });
  }
  return { paket: { fassung: FASSUNG, frage_id: fid, inhalt: b64(blob), faecher }, rueck: r, frageId: fid, roh };
}


const antwortAad = (fid, epkRoh, art, n) => verbinden(text.encode("kiplatz-antwort-v1:"), hexZuBytes(fid), epkRoh, text.encode(art + ":" + String(n)));

export class Empfang {
  constructor(v) { this.v = v; this.schluessel = new Map(); this.zuletzt = new Map(); }


  static reihe(n) { return `${String(n.epk || "")}:${String(n.art || "")}`; }

  istNeu(n) { return !!n && Number.isInteger(n.n) && n.n > (this.zuletzt.get(Empfang.reihe(n)) || 0); }

  async oeffnen(n) {
    if (!n || n.fassung !== FASSUNG) throw new KryptoFehler("unbekannte Fassung der Nachricht");
    if (!ARTEN.includes(n.art) || !Number.isInteger(n.n) || n.n < 1) throw new KryptoFehler("Art oder Zähler der Nachricht fehlen");
    const epk = String(n.epk || ""), epkRoh = unb64(epk);
    let k = this.schluessel.get(epk);
    if (!k) {
      if (this.schluessel.size >= 8) throw new KryptoFehler("zu viele Helfer für eine Frage");
      const rueckRoh = await rohAusJwk(this.v.rueck.privat);
      let pub;
      try { pub = await S.importKey("raw", epkRoh, KURVE_DH, false, []); } catch { throw new KryptoFehler("kein gültiger P-256-Punkt"); }
      const geteilt = new Uint8Array(await S.deriveBits({ name: "ECDH", public: pub }, await privatLaden(this.v.rueck.privat), 256));
      k = await hkdf(geteilt, verbinden(epkRoh, rueckRoh), "kiplatz-antwort-v1");
      this.schluessel.set(epk, k);
    }
    if (n.n <= (this.zuletzt.get(Empfang.reihe(n)) || 0)) throw new KryptoFehler("diese Nachricht ist alt oder wiederholt");
    const roh = await aesAuf(k, unb64(n.iv), unb64(n.ct), antwortAad(this.v.frageId, epkRoh, n.art, n.n),
      "die Nachricht passt nicht zu dieser Frage oder wurde verändert");
    this.zuletzt.set(Empfang.reihe(n), n.n);
    let daten;
    try { daten = JSON.parse(new TextDecoder().decode(roh)); } catch { throw new KryptoFehler("die Nachricht ist kein gültiges JSON"); }
    if (!daten || typeof daten !== "object") throw new KryptoFehler("die Nachricht ist kein Objekt");
    return { art: n.art, daten, epk, n: n.n };
  }


  async antwortLesen(offen, sigOeffentlich) {
    if (offen.art !== "antwort") throw new KryptoFehler("keine Endantwort");
    const innen = text.encode(String(offen.daten.antwort || ""));
    let d;
    try { d = JSON.parse(new TextDecoder().decode(innen)); } catch { throw new KryptoFehler("die Antwort ist kein gültiges JSON"); }
    if (!d || typeof d.text !== "string") throw new KryptoFehler("der Antwort fehlt der Text");
    const ok = !!sigOeffentlich && await unterschriftPruefen(sigOeffentlich, this.v.frageId, this.v.roh, innen, offen.daten.sig);
    return { text: d.text, lieferschein: d.lieferschein && typeof d.lieferschein === "object" ? d.lieferschein : {}, ok, innen };
  }
}
