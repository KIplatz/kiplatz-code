// SPDX-License-Identifier: AGPL-3.0-or-later
const stapel = [];
let still = 0;
let spaeter = [];

if (history.state?.kiplatz) history.replaceState(null, "");

export const offen = (name) => stapel.some((e) => e.name === name);
export const oben = () => stapel.at(-1)?.name || "";
export const tiefe = () => stapel.length;


export function auf(name, zu) {
  const e = { name, zu, zustand: { kiplatz: stapel.length + 1 }, drin: false };
  stapel.push(e);
  if (still) spaeter.push(e);
  else { history.pushState(e.zustand, ""); e.drin = true; }
}

function zuMachen(weg) { weg.reverse().forEach((e, n) => e.zu(n === weg.length - 1)); }

function schliessenAb(i) {
  if (i < 0 || i >= stapel.length) return false;
  const weg = stapel.splice(i);
  const imVerlauf = weg.filter((e) => e.drin).length;
  spaeter = spaeter.filter((e) => !weg.includes(e));
  zuMachen(weg);
  if (imVerlauf) { still++; history.go(-imVerlauf); }
  return true;
}


export function zurueck(name) {
  if (!stapel.length) return false;
  if (!name || stapel.at(-1).name === name) return schliessenAb(stapel.length - 1);
  return schliessen(name);
}

export function schliessen(...namen) { return schliessenAb(stapel.findIndex((e) => namen.includes(e.name))); }

export function bis(name) { const i = stapel.findIndex((e) => e.name === name); return i >= 0 && schliessenAb(i + 1); }
export const alleZu = () => schliessenAb(0);

addEventListener("popstate", (ev) => {
  if (still) {
    if (--still === 0) { for (const e of spaeter) { history.pushState(e.zustand, ""); e.drin = true; } spaeter = []; }
    return;
  }
  const ziel = Number(ev.state?.kiplatz) || 0;
  if (ziel < stapel.length) zuMachen(stapel.splice(ziel));
});
