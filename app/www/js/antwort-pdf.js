// SPDX-License-Identifier: AGPL-3.0-or-later
import * as helfer from "./helfer.js";
import { bloecke, stuecke } from "./antwort.js";

export const A4 = [595.28, 841.89];
const RAND = 56, GROSS = 11, ZEILE = 15.5, CODE = 9.5;


export function dateiname(text, jetzt = new Date()) {
  const b = bloecke(text).find((x) => x.art === "ueberschrift");
  const titel = (b ? stuecke(b.text).map((s) => s.text).join("") : "").replace(/[\\/:*?"<>|\u0000-\u001f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 60);
  const z = (n) => String(n).padStart(2, "0");
  return `${titel || `KIplatz-Antwort ${jetzt.getFullYear()}-${z(jetzt.getMonth() + 1)}-${z(jetzt.getDate())}`}.pdf`;
}


export function zeichenFuer(kann) {
  return (text) => {
    let aus = "";
    for (const c of String(text)) {
      if (kann.has(c.codePointAt(0))) { aus += c; continue; }
      if (/\p{Extended_Pictographic}|[️‍]/u.test(c)) continue;
      const ohne = c.normalize("NFD").replace(/\p{M}/gu, "").replace("ł", "l").replace("Ł", "L").replace("đ", "d").replace("ı", "i");
      aus += [...ohne].every((x) => kann.has(x.codePointAt(0))) ? ohne : c === "\t" ? "    " : "?";
    }
    return aus;
  };
}


export async function alsPdf(text, laden = () => helfer.modul("pdflib/pdf-lib.esm.min.js"), jetzt = new Date()) {
  const lib = await laden();
  const doc = await lib.PDFDocument.create();
  const schrift = { n: await doc.embedFont(lib.StandardFonts.Helvetica), f: await doc.embedFont(lib.StandardFonts.HelveticaBold), c: await doc.embedFont(lib.StandardFonts.Courier) };
  const sauber = zeichenFuer(new Set(schrift.n.getCharacterSet()));
  const breite = A4[0] - 2 * RAND;
  let seite = null, y = 0;
  const neueSeite = () => { seite = doc.addPage(A4); y = A4[1] - RAND; };
  const platz = (h) => { if (!seite || y - h < RAND) neueSeite(); };

  const zeilen = (laeufe, groesse, max) => {
    const woerter = [];
    for (const l of laeufe) for (const w of sauber(l.text).split(/(\s+)/)) if (w) woerter.push({ text: w, f: l.f });
    const aus = [[]]; let x = 0;
    for (const w of woerter) {
      const font = w.f ? schrift.f : schrift.n;
      const leer = /^\s+$/.test(w.text);
      let wb = font.widthOfTextAtSize(leer ? " " : w.text, groesse);
      if (leer) { if (aus.at(-1).length) { aus.at(-1).push({ text: " ", f: w.f, b: wb }); x += wb; } continue; }
      if (x + wb > max && aus.at(-1).length) { while (aus.at(-1).at(-1)?.text === " ") x -= aus.at(-1).pop().b; aus.push([]); x = 0; }
      let rest = w.text;
      while (wb > max) {
        let n = rest.length; while (n > 1 && font.widthOfTextAtSize(rest.slice(0, n), groesse) > max) n--;
        aus.at(-1).push({ text: rest.slice(0, n), f: w.f, b: font.widthOfTextAtSize(rest.slice(0, n), groesse) }); aus.push([]);
        rest = rest.slice(n); wb = font.widthOfTextAtSize(rest, groesse);
      }
      aus.at(-1).push({ text: rest, f: w.f, b: wb }); x += wb;
    }
    return aus.filter((z, i) => z.length || i === 0);
  };
  const schreiben = (laeufe, { groesse = GROSS, einzug = 0, zeile = ZEILE, vor = "" } = {}) => {
    const liste = zeilen(laeufe, groesse, breite - einzug);
    liste.forEach((z, i) => {
      platz(zeile);
      y -= zeile;
      if (i === 0 && vor) seite.drawText(sauber(vor), { x: RAND + einzug - schrift.n.widthOfTextAtSize(sauber(vor), groesse) - 5, y, size: groesse, font: schrift.n });

      let x = RAND + einzug;
      const stuecke_ = [];
      for (const w of z) { const l = stuecke_.at(-1); if (l && l.f === w.f) { l.text += w.text; l.b += w.b; } else stuecke_.push({ ...w }); }
      for (const s of stuecke_) { seite.drawText(s.text, { x, y, size: groesse, font: s.f ? schrift.f : schrift.n }); x += s.b; }
    });
  };
  const laeufe = (t, fett = false) => stuecke(t).map((s) => ({ text: s.text, f: fett || s.art === "fett" }));
  let erste = true;
  for (const b of bloecke(text)) {
    if (b.art === "ueberschrift") {
      const g = erste ? 18 : 13.5;
      if (!erste) y -= 8;
      schreiben(laeufe(b.text, true), { groesse: g, zeile: g * 1.35 });
      y -= 4;
    } else if (b.art === "absatz") {
      for (const z of b.text.split("\n")) schreiben(laeufe(z));
      y -= 6;
    } else if (b.art === "punkte" || b.art === "nummern") {
      b.punkte.forEach((p, i) => schreiben(laeufe(p), { einzug: 16, vor: b.art === "punkte" ? "•" : `${i + 1}.` }));
      y -= 6;
    } else if (b.art === "tabelle") {

      schreiben([{ text: b.kopf.join("  |  "), f: true }]);
      for (const r of b.reihen) schreiben([{ text: r.map((c) => stuecke(c).map((s) => s.text).join("")).join("  |  "), f: false }]);
      y -= 6;
    } else if (b.art === "codeblock") {
      for (const z of b.text.split("\n")) {
        platz(CODE * 1.4); y -= CODE * 1.4;
        seite.drawText(sauber(z).slice(0, 95), { x: RAND, y, size: CODE, font: schrift.c });
      }
      y -= 6;
    }
    erste = false;
  }
  if (!seite) neueSeite();
  doc.setTitle(dateiname(text, jetzt).replace(/\.pdf$/, ""));
  doc.setCreator("KIplatz"); doc.setProducer("KIplatz");
  const bytes = await doc.save();
  return new File([bytes], dateiname(text, jetzt), { type: "application/pdf" });
}
