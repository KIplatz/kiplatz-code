// SPDX-License-Identifier: AGPL-3.0-or-later
import "./oberflaeche-sprache.js";

const s = globalThis.kiplatzSprache;
let geholt = false;

async function holen() {
  if (geholt) return;
  try {
    const r = await fetch(new URL("../sprache/en.json", import.meta.url).href, { cache: "no-cache", credentials: "omit" });
    if (r.ok) { s.katalog(await r.json()); geholt = true; }
  } catch (e) { }
}

s.beiWechsel((l) => { if (l === "en") holen(); });

if (s.sprache() === "en") await Promise.race([holen(), new Promise((ok) => setTimeout(ok, 3000))]);
