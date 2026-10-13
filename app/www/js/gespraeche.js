// SPDX-License-Identifier: AGPL-3.0-or-later
export const MAX_GESPRAECHE = 100;
export const MAX_NACHRICHTEN = 200;
export const TITEL_LAENGE = 48;


export const FARBEN = { blau: ["Blau", "#2f7fd8"], gruen: ["Grün", "#2e9e5b"], gelb: ["Gelb", "#d4a106"], orange: ["Orange", "#e07a1f"],
  rot: ["Rot", "#d64541"], violett: ["Violett", "#8b5cc7"], rosa: ["Rosa", "#d9579a"], grau: ["Grau", "#8a949c"] };


export function tagesgruss(stunde) {
  if (stunde >= 5 && stunde < 11) return "Guten Morgen";
  if (stunde >= 11 && stunde < 14) return "Mahlzeit";
  if (stunde >= 14 && stunde < 18) return "Schönen Nachmittag";
  if (stunde >= 18 && stunde < 23) return "Guten Abend";
  return "Noch munter";
}

export function neueKennung() {
  const b = new Uint8Array(8);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

export function titelAus(nachrichten) {
  const u = (nachrichten || []).find((n) => n.rolle === "user");
  if (!u) return "Neues Gespräch";
  const t = String(u.text).replace(/\s+/g, " ").trim();
  return t.length > TITEL_LAENGE ? t.slice(0, TITEL_LAENGE).trimEnd() + "…" : t;
}

export class Gespraeche {
  constructor(liste = [], aktuell = "") {
    this.liste = Array.isArray(liste) ? liste.filter((g) => g && typeof g.kennung === "string" && Array.isArray(g.nachrichten)) : [];
    this.aktuellId = aktuell;
    if (!this.liste.length) this.neu();
    if (!this.liste.some((g) => g.kennung === this.aktuellId)) this.aktuellId = this.sortiert()[0].kennung;
  }

  static aus(daten) { return new Gespraeche(daten?.liste, daten?.aktuell); }
  daten() { this.aufraeumen(); return { liste: this.liste, aktuell: this.aktuellId }; }

  get aktuell() { return this.liste.find((g) => g.kennung === this.aktuellId); }
  titel(g) { return (g.eigenerTitel || "").trim() || titelAus(g.nachrichten); }


  neu() {
    const leer = this.liste.find((g) => !g.nachrichten.length);
    if (leer) { this.aktuellId = leer.kennung; leer.zeit = Date.now(); return leer; }
    const g = { kennung: neueKennung(), nachrichten: [], zeit: Date.now(), angeheftet: false, eigenerTitel: "" };
    this.liste.unshift(g);
    this.aktuellId = g.kennung;
    return g;
  }

  waehlen(kennung) { if (this.liste.some((g) => g.kennung === kennung)) this.aktuellId = kennung; }

  loeschen(kennung) {
    this.liste = this.liste.filter((g) => g.kennung !== kennung);
    if (!this.liste.length) this.neu();
    if (this.aktuellId === kennung) this.aktuellId = this.sortiert()[0].kennung;
  }

  umbenennen(kennung, titel) {
    const g = this.liste.find((x) => x.kennung === kennung);
    if (g) g.eigenerTitel = String(titel || "").replace(/\s+/g, " ").trim().slice(0, 80);
  }


  verschieben(kennung, projekt) {
    const g = this.liste.find((x) => x.kennung === kennung);
    if (g) g.projekt = String(projekt || "").replace(/\s+/g, " ").trim().slice(0, 60);
  }


  farbeSetzen(kennung, farbe) {
    const g = this.liste.find((x) => x.kennung === kennung);
    if (g) g.farbe = FARBEN[farbe] ? farbe : "";
  }

  anheften(kennung) {
    const g = this.liste.find((x) => x.kennung === kennung);
    if (g) g.angeheftet = !g.angeheftet;
  }

  hinzufuegen(nachricht, kennung = this.aktuellId) {
    const g = this.liste.find((x) => x.kennung === kennung);
    if (!g) return;
    g.nachrichten.push({ zeit: Date.now(), ...nachricht });
    g.zeit = Date.now();
  }


  sortiert() {
    return [...this.liste].sort((a, b) => (b.angeheftet ? 1 : 0) - (a.angeheftet ? 1 : 0) || (b.zeit || 0) - (a.zeit || 0));
  }


  suchen(text) {
    const s = String(text || "").trim().toLocaleLowerCase("de");
    if (!s) return this.sortiert();
    return this.sortiert().filter((g) => this.titel(g).toLocaleLowerCase("de").includes(s)
      || g.nachrichten.some((n) => String(n.text).toLocaleLowerCase("de").includes(s)));
  }


  alsText(kennung = this.aktuellId) {
    const g = this.liste.find((x) => x.kennung === kennung);
    if (!g) return "";
    const zeilen = [this.titel(g), ""];
    for (const n of g.nachrichten) zeilen.push((n.rolle === "user" ? "Du" : "KIplatz") + ":", n.text, "");
    return zeilen.join("\n").trim();
  }


  aufraeumen() {
    for (const g of this.liste) if (g.nachrichten.length > MAX_NACHRICHTEN) g.nachrichten = g.nachrichten.slice(-MAX_NACHRICHTEN);
    if (this.liste.length > MAX_GESPRAECHE) {
      const bleiben = new Set(this.sortiert().slice(0, MAX_GESPRAECHE).map((g) => g.kennung));
      this.liste = this.liste.filter((g) => bleiben.has(g.kennung) || g.angeheftet || g.kennung === this.aktuellId);
    }
  }
}
