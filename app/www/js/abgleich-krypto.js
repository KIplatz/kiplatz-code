// SPDX-License-Identifier: AGPL-3.0-or-later
const S = globalThis.crypto.subtle;
const text = new TextEncoder();
export const FASSUNG = 1;
export const AUFFUELLEN = 4096;
const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const KURVE = { name: "ECDH", namedCurve: "P-256" };

export class KryptoFehler extends Error {}

export function b64(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
export function unb64(t) {
  let s;
  try { s = atob(String(t)); } catch { throw new KryptoFehler("kein gültiges Base64"); }
  const b = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
  return b;
}
const verbinden = (...teile) => { const n = teile.reduce((a, t) => a + t.length, 0), b = new Uint8Array(n); let o = 0; for (const t of teile) { b.set(t, o); o += t.length; } return b; };
const zufall = (n) => globalThis.crypto.getRandomValues(new Uint8Array(n));

async function hkdf(stoff, salt, info) {
  const basis = await S.importKey("raw", stoff, "HKDF", false, ["deriveBits"]);
  const bits = await S.deriveBits({ name: "HKDF", hash: "SHA-256", salt, info: text.encode(info) }, basis, 256);
  return S.importKey("raw", bits, "AES-GCM", false, ["encrypt", "decrypt"]);
}
async function aesZu(schluessel, iv, klar, aad) { return new Uint8Array(await S.encrypt({ name: "AES-GCM", iv, additionalData: text.encode(aad) }, schluessel, klar)); }
async function aesAuf(schluessel, iv, ct, aad, fehler) {
  try { return new Uint8Array(await S.decrypt({ name: "AES-GCM", iv, additionalData: text.encode(aad) }, schluessel, ct)); }
  catch { throw new KryptoFehler(fehler); }
}

export const neuerKontoschluessel = () => zufall(32);


export async function siegel(k, kennung, oeffentlich) {
  const basis = await S.importKey("raw", k, "HKDF", false, ["deriveBits"]);
  const bits = await S.deriveBits({ name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: text.encode("kiplatz-abgleich-siegel-v1") }, basis, 256);
  const m = await S.importKey("raw", bits, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64(new Uint8Array(await S.sign("HMAC", m, text.encode(String(kennung) + ":" + String(oeffentlich.punkt)))));
}
export async function siegelPruefen(k, kennung, oeffentlich, wert) {
  try { const s = await siegel(k, kennung, oeffentlich); return s.length === String(wert).length && s === String(wert); } catch { return false; }
}


export async function blockVerschluesseln(k, id, gespraech, iv = zufall(12)) {
  let roh = text.encode(JSON.stringify(gespraech));
  const rest = (AUFFUELLEN - (roh.length % AUFFUELLEN)) % AUFFUELLEN;
  if (rest) { const p = new Uint8Array(roh.length + rest).fill(0x20); p.set(roh); roh = p; }
  const ct = await aesZu(await hkdf(k, new Uint8Array(0), "kiplatz-abgleich-block-v1"), iv, roh, "kiplatz-block:" + id);
  return b64(verbinden(new Uint8Array([FASSUNG]), iv, ct));
}
export async function blockEntschluesseln(k, id, daten) {
  const roh = unb64(daten);
  if (roh.length < 29 || roh[0] !== FASSUNG) throw new KryptoFehler("unbekannte Fassung des Blocks");
  const klar = await aesAuf(await hkdf(k, new Uint8Array(0), "kiplatz-abgleich-block-v1"), roh.subarray(1, 13), roh.subarray(13), "kiplatz-block:" + id,
    "der Block passt nicht zu diesem Schlüssel oder wurde verändert");
  return JSON.parse(new TextDecoder().decode(klar));
}


export async function neuesGeraet() {
  const p = await S.generateKey(KURVE, true, ["deriveBits"]);
  return { privat: await S.exportKey("jwk", p.privateKey), oeffentlich: { art: "p256", punkt: b64(new Uint8Array(await S.exportKey("raw", p.publicKey))) } };
}
async function privatLaden(jwk) { return S.importKey("jwk", jwk, KURVE, false, ["deriveBits"]); }
async function rohAusJwk(jwk) {
  const { d, ...oeff } = jwk;
  return new Uint8Array(await S.exportKey("raw", await S.importKey("jwk", { ...oeff, key_ops: [] }, KURVE, true, [])));
}
export async function pruefzahl(oeffentlich) {
  const h = new Uint8Array(await S.digest("SHA-256", unb64(oeffentlich.punkt)));
  const n = ((h[0] * 2 ** 24) + (h[1] << 16) + (h[2] << 8) + h[3]) % 1000000;
  const s = String(n).padStart(6, "0");
  return s.slice(0, 3) + " " + s.slice(3);
}
export async function fachPacken(k, geraetOeffentlich, { wegwerf = null, iv = zufall(12) } = {}) {
  if (geraetOeffentlich?.art !== "p256") throw new KryptoFehler("unbekannte Art des Geräteschlüssels");
  const gRoh = unb64(geraetOeffentlich.punkt);
  const g = await S.importKey("raw", gRoh, KURVE, false, []);
  const eJwk = wegwerf || (await neuesGeraet()).privat;
  const eRoh = await rohAusJwk(eJwk);
  const geteilt = new Uint8Array(await S.deriveBits({ name: "ECDH", public: g }, await privatLaden(eJwk), 256));
  const w = await hkdf(geteilt, verbinden(eRoh, gRoh), "kiplatz-abgleich-fach-v1");
  return { art: "p256", epk: b64(eRoh), iv: b64(iv), ct: b64(await aesZu(w, iv, k, "kiplatz-fach")) };
}
export async function fachOeffnen(fach, privatJwk) {
  if (fach?.art !== "p256") throw new KryptoFehler("unbekannte Art des Fachs");
  const eRoh = unb64(fach.epk), gRoh = await rohAusJwk(privatJwk);
  const e = await S.importKey("raw", eRoh, KURVE, false, []);
  const geteilt = new Uint8Array(await S.deriveBits({ name: "ECDH", public: e }, await privatLaden(privatJwk), 256));
  const k = await aesAuf(await hkdf(geteilt, verbinden(eRoh, gRoh), "kiplatz-abgleich-fach-v1"), unb64(fach.iv), unb64(fach.ct), "kiplatz-fach",
    "das Fach gehört nicht zu diesem Gerät oder wurde verändert");
  if (k.length !== 32) throw new KryptoFehler("der Kontoschlüssel hat nicht die erwartete Länge");
  return k;
}


export function wiederherstellungZeigen(r) {
  let n = 0n;
  for (const b of r) n = (n << 8n) | BigInt(b);
  let s = "";
  for (let i = 0; i < 24; i++) { s = CROCKFORD[Number(n & 31n)] + s; n >>= 5n; }
  return s.match(/.{4}/g).join("-");
}
export function wiederherstellungLesen(t) {
  const s = String(t).toUpperCase().replace(/[-\s]/g, "").replace(/O/g, "0").replace(/[IL]/g, "1");
  if (s.length !== 24 || [...s].some((c) => !CROCKFORD.includes(c))) throw new KryptoFehler("der Wiederherstellungsschlüssel hat 24 Zeichen aus Ziffern und Buchstaben");
  let n = 0n;
  for (const c of s) n = (n << 5n) | BigInt(CROCKFORD.indexOf(c));
  const r = new Uint8Array(15);
  for (let i = 14; i >= 0; i--) { r[i] = Number(n & 255n); n >>= 8n; }
  return r;
}
export const neuerWiederherstellungsschluessel = () => wiederherstellungZeigen(zufall(15));
export async function wiederherstellungPacken(k, rText, iv = zufall(12)) {
  const w = await hkdf(wiederherstellungLesen(rText), text.encode("kiplatz-wiederherstellung"), "kiplatz-abgleich-wieder-v1");
  return { art: "wieder", iv: b64(iv), ct: b64(await aesZu(w, iv, k, "kiplatz-wieder")) };
}
export async function wiederherstellungOeffnen(fach, rText) {
  if (fach?.art !== "wieder") throw new KryptoFehler("unbekannte Art des Fachs");
  const w = await hkdf(wiederherstellungLesen(rText), text.encode("kiplatz-wiederherstellung"), "kiplatz-abgleich-wieder-v1");
  return aesAuf(w, unb64(fach.iv), unb64(fach.ct), "kiplatz-wieder", "dieser Wiederherstellungsschlüssel passt nicht");
}
