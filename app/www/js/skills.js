// SPDX-License-Identifier: AGPL-3.0-or-later
import { name as fachName } from "./konten.js";

const schluessel = () => "kiplatz." + fachName("skills");
export const MAX_SKILLS = 50;
export const MAX_TEXT = 12000;


export function lesen(roh) {
  const text = String(roh || "").replace(/\r\n/g, "\n").trim();
  if (text.length < 20 || text.length > MAX_TEXT) throw new Error(`Ein Skill braucht zwischen 20 und ${MAX_TEXT} Zeichen.`);
  let name = "", beschreibung = "";
  const kopf = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (kopf) {
    for (const z of kopf[1].split("\n")) {
      const m = z.match(/^(name|description)\s*:\s*(.*)$/i);
      if (m) { const w = m[2].trim().replace(/^["']|["']$/g, ""); if (m[1].toLowerCase() === "name") name = w; else beschreibung = w; }
    }
  }
  if (!name) { const h = text.match(/^#\s+(.+)$/m); if (h) name = h[1].trim(); }
  name = name.replace(/\s+/g, " ").trim().slice(0, 80);
  if (!name) throw new Error("Der Skill hat keinen Namen (Zeile „name:“ oben).");
  return { name, beschreibung: beschreibung.slice(0, 300), text };
}

const alle = () => { try { const l = JSON.parse(localStorage.getItem(schluessel()) || "[]"); return Array.isArray(l) ? l.filter((s) => s && s.name && s.text) : []; } catch { return []; } };
const ablegen = (l) => { try { localStorage.setItem(schluessel(), JSON.stringify(l.slice(0, MAX_SKILLS))); } catch { } };

export const liste = () => alle().sort((a, b) => (b.geladen || 0) - (a.geladen || 0));
export const holen = (name) => alle().find((s) => s.name === name) || null;


export function merken(skill) {
  const l = alle();
  const alt = l.find((s) => s.name === skill.name);
  const eintrag = { name: skill.name, titel: String(skill.titel || skill.name).slice(0, 80), beschreibung: skill.beschreibung || "", text: skill.text,
    thema: Number.isInteger(skill.thema) ? skill.thema : null, geladen: Date.now(), ...(alt?.immer ? { immer: alt.immer } : {}) };
  ablegen([eintrag, ...l.filter((s) => s.name !== skill.name)]);
  return !alt ? "neu" : alt.text === skill.text ? "gleich" : "aktualisiert";
}
export function entfernen(name) { ablegen(alle().filter((s) => s.name !== name)); }


export function immerSetzen(name, an) {
  const l = alle(), naechste = Math.max(0, ...l.map((s) => Number(s.immer) || 0)) + 1;
  ablegen(l.map((s) => (s.name !== name ? s : an ? { ...s, immer: s.immer || naechste } : (({ immer, ...rest }) => rest)(s))));
}

export const immer = () => alle().filter((s) => s.immer).sort((a, b) => (b.name === "meine-ki") - (a.name === "meine-ki") || a.immer - b.immer);


export function fuerGespraech(gewaehlt) {
  const liste = [];
  for (const s of [...(gewaehlt ? [holen(gewaehlt)] : []), ...immer()]) if (s && !liste.some((x) => x.name === s.name)) liste.push(s);
  const mit = [], weg = [];
  for (const s of liste) { const probe = [...mit, s]; if (alsEine(probe).text.length <= MAX_TEXT) mit.push(s); else weg.push(s); }
  return { mit, weg };
}


export function alsEine(liste) {
  if (liste.length === 1) return { name: liste[0].name, text: liste[0].text };
  const koerper = (t) => String(t).replace(/^---\n[\s\S]*?\n---\n?/, "").trim();
  const name = liste.map((s) => s.name).join(" und ").slice(0, 80);
  const text = `---\nname: ${name}\ndescription: Mehrere Skills zusammen: ${liste.map((s) => s.name).join(", ").slice(0, 160)}\n---\n\n`
    + liste.map((s) => `# Skill „${s.name}“${s.beschreibung ? ` (${s.beschreibung})` : ""}\n\n${koerper(s.text)}`).join("\n\n");
  return { name, text };
}
