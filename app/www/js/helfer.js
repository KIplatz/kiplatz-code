// SPDX-License-Identifier: AGPL-3.0-or-later
import { HELFER_SHA256 } from "./helfer-pruefsummen.js";

export class HelferFehler extends Error {}


export function helferBasis(ort = globalThis.location, nativ = !!globalThis.Capacitor?.isNativePlatform?.()) {
  if (nativ || !/^https?:$/.test(ort?.protocol || "")) return "https://kiplatz.at/ki-helfer/";
  return new URL("/ki-helfer/", ort.origin).href;
}

const hex = (puffer) => Array.from(new Uint8Array(puffer), (b) => b.toString(16).padStart(2, "0")).join("");


export async function stimmt(pfad, bytes) {
  const soll = HELFER_SHA256[pfad];
  if (!soll) return false;
  return hex(await crypto.subtle.digest("SHA-256", bytes)) === soll;
}

const geholt = new Map();
const ABLAGE = "kiplatz-helfer";

async function ablage() {
  try { return await caches.open(ABLAGE); } catch { return null; }
}


export async function bytes(pfad, basis = helferBasis(), fortschritt = null) {
  const soll = HELFER_SHA256[pfad];
  if (!soll) throw new HelferFehler(`${pfad} gehört nicht zu den Helfern`);
  const schluessel = `https://ki-helfer.invalid/${soll}/${pfad}`;
  const a = await ablage();
  try {
    const alt = await a?.match(schluessel);
    if (alt) {
      const b = await alt.arrayBuffer();
      if (await stimmt(pfad, b)) return b;
      await a.delete(schluessel);
    }
  } catch { }
  let r;
  try { r = await fetch(basis + pfad, { credentials: "omit", redirect: "error" }); }
  catch { throw new HelferFehler("Keine Verbindung zu kiplatz.at."); }
  if (!r.ok) throw new HelferFehler(`kiplatz.at hat ${pfad} nicht geliefert (${r.status}).`);
  const b = await lesen(r, fortschritt);
  if (!(await stimmt(pfad, b))) throw new HelferFehler(`${pfad} stimmt nicht mit der Prüfsumme in der App überein, sie wird nicht verwendet.`);
  try { await a?.put(schluessel, new Response(b)); } catch { }
  return b;
}


export async function lesen(r, fortschritt = null) {
  const gesamt = Number(r.headers.get("Content-Length")) || 0;
  if (!fortschritt || !r.body) return r.arrayBuffer();
  const leser = r.body.getReader();
  const teile = [];
  let n = 0;
  for (;;) {
    const { done, value } = await leser.read();
    if (done) break;
    teile.push(value); n += value.length;
    fortschritt(n, Math.max(gesamt, n));
  }
  const aus = new Uint8Array(n);
  let p = 0;
  for (const t of teile) { aus.set(t, p); p += t.length; }
  return aus.buffer;
}


export function adresse(pfad, basis = helferBasis(), fortschritt = null) {
  if (!geholt.has(pfad)) {
    const typ = pfad.endsWith(".wasm") ? "application/wasm" : "text/javascript";
    const p = bytes(pfad, basis, fortschritt).then((b) => URL.createObjectURL(new Blob([b], { type: typ })));
    p.catch(() => geholt.delete(pfad));
    geholt.set(pfad, p);
  }
  return geholt.get(pfad);
}


export async function modul(pfad, basis = helferBasis()) {
  return import(await adresse(pfad, basis));
}
