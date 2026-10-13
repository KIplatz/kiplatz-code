// SPDX-License-Identifier: AGPL-3.0-or-later
import { nativ } from "./nativ.js";
import { name as fachName } from "./konten.js";

const VORSILBE = "kiplatz.";

export const imTresor = () => !!nativ?.tresor;

export async function lesen(name) {
  name = fachName(name);
  if (nativ?.tresor) {
    const w = await nativ.tresor.lesen(name);
    return typeof w === "string" ? JSON.parse(w) : w;
  }
  try { return JSON.parse(localStorage.getItem(VORSILBE + name) ?? "null"); } catch { return null; }
}

export async function schreiben(name, wert) {
  name = fachName(name);
  if (nativ?.tresor) return nativ.tresor.schreiben(name, JSON.stringify(wert));
  localStorage.setItem(VORSILBE + name, JSON.stringify(wert));
}

export async function loeschen(name) {
  name = fachName(name);
  if (nativ?.tresor) return nativ.tresor.loeschen(name);
  localStorage.removeItem(VORSILBE + name);
}
