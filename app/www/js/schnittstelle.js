// SPDX-License-Identifier: AGPL-3.0-or-later
import { APP_VERSION } from "./version.js";

export const SERVER = "https://kiplatz.at";
let basis = SERVER;

export function basisSetzen(b) { basis = b; }
export const basisAdresse = () => basis;

export class ServerFehler extends Error {
  constructor(text, status = 0, code = "") { super(text); this.status = status; this.code = code; }
}


const WEG = /^\/[a-z0-9\-/]*(\?[a-z0-9\-_.~%=&]*)?$/i;


let abgemeldet = null;
export function beiAbgemeldet(f) { abgemeldet = f; }


const sprachKopf = () => (globalThis.kiplatzSprache ? globalThis.kiplatzSprache.kopf() : {});


export async function holen(weg, { body = null, geraet = null, zeitlimit = 20000 } = {}) {
  if (!WEG.test(weg)) throw new ServerFehler("ungültiger Weg");
  const kopf = { "Accept": "application/json", "X-App-Version": APP_VERSION, ...sprachKopf() };
  if (geraet) { kopf["X-Geraet"] = geraet.kennung; kopf["X-Geraet-Schluessel"] = geraet.schluessel; kopf["X-Geraet-Art"] = "handy"; }
  if (body) kopf["Content-Type"] = "application/json";
  const abbruch = new AbortController();
  const uhr = setTimeout(() => abbruch.abort(), zeitlimit);
  let r;
  try {
    r = await fetch(basis + weg, { method: body ? "POST" : "GET", headers: kopf, body: body ? JSON.stringify(body) : undefined,
      cache: "no-store", credentials: "omit", redirect: "error", signal: abbruch.signal });
  } catch (e) {
    throw new ServerFehler(e.name === "AbortError" ? "Der Server hat nicht rechtzeitig geantwortet." : "Keine Verbindung zum Server. Bist du online?");
  } finally { clearTimeout(uhr); }
  let d = {};
  try { d = await r.json(); } catch { d = {}; }
  if (!r.ok) {
    if (geraet && r.status === 401 && d.fehler === "GERAET" && abgemeldet) abgemeldet();
    const text = typeof d.text === "string" && d.text ? d.text : `Der Server antwortet mit ${r.status}.`;
    throw new ServerFehler(text.charAt(0).toUpperCase() + text.slice(1), r.status, d.fehler || "");
  }
  return d;
}


export async function holenRoh(weg, { geraet = null, zeitlimit = 120000 } = {}) {
  if (!WEG.test(weg)) throw new ServerFehler("ungültiger Weg");
  const kopf = { "X-App-Version": APP_VERSION, ...sprachKopf() };
  if (geraet) { kopf["X-Geraet"] = geraet.kennung; kopf["X-Geraet-Schluessel"] = geraet.schluessel; kopf["X-Geraet-Art"] = "handy"; }
  const abbruch = new AbortController();
  const uhr = setTimeout(() => abbruch.abort(), zeitlimit);
  try {
    const r = await fetch(basis + weg, { headers: kopf, cache: "no-store", credentials: "omit", redirect: "error", signal: abbruch.signal });
    if (!r.ok) {
      let d = {}; try { d = await r.json(); } catch { d = {}; }
      throw new ServerFehler(typeof d.text === "string" && d.text ? d.text.charAt(0).toUpperCase() + d.text.slice(1) : `Der Server antwortet mit ${r.status}.`, r.status, d.fehler || "");
    }
    return new Uint8Array(await r.arrayBuffer());
  } catch (e) {
    if (e instanceof ServerFehler) throw e;
    throw new ServerFehler(e.name === "AbortError" ? "Das Holen hat zu lange gedauert." : "Keine Verbindung zum Server. Bist du online?");
  } finally { clearTimeout(uhr); }
}


export function fassungVergleich(a, b) {
  const t = (v) => String(v || "").split(".").map((x) => parseInt(x, 10) || 0);
  const x = t(a), y = t(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] || 0) - (y[i] || 0);
    if (d) return d < 0 ? -1 : 1;
  }
  return 0;
}


export function standBewerten(stand, eigene = APP_VERSION) {
  if (!stand || typeof stand !== "object") return { art: "ok" };
  const laden = stand.laden || {};
  if (stand.mindestens && fassungVergleich(eigene, stand.mindestens) < 0)
    return { art: "sperre", text: stand.text || "Diese Fassung der App ist zu alt. Bitte hol dir die neue aus dem App Store oder von Google Play.", laden };
  if (stand.neueste && fassungVergleich(eigene, stand.neueste) < 0)
    return { art: "hinweis", text: stand.text || "Es gibt eine neue Fassung der App.", laden };
  return { art: "ok" };
}
