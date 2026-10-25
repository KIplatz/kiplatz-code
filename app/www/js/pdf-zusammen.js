// SPDX-License-Identifier: AGPL-3.0-or-later
import * as helfer from "./helfer.js";

export const MAX_DATEIEN = 30;
export const MAX_BYTES = 100 * 1024 * 1024;
export const MAX_SEITEN = 5000;

export class PdfFehler extends Error {}


export function zielname(jetzt = new Date()) {
  const z = (n) => String(n).padStart(2, "0");
  return `Zusammengefügt ${jetzt.getFullYear()}-${z(jetzt.getMonth() + 1)}-${z(jetzt.getDate())} ${z(jetzt.getHours())}${z(jetzt.getMinutes())}.pdf`;
}

const istPdf = (f) => /\.pdf$/i.test(f.name || "") || f.type === "application/pdf";


export async function zusammenfuegen(dateien, laden = () => helfer.modul("pdflib/pdf-lib.esm.min.js")) {
  const liste = [...dateien].sort((a, b) => String(a.name).toLowerCase().localeCompare(String(b.name).toLowerCase()));
  if (liste.length < 2) throw new PdfFehler("Wähle mindestens zwei PDF-Dateien aus.");
  if (liste.length > MAX_DATEIEN) throw new PdfFehler(`Höchstens ${MAX_DATEIEN} Dateien auf einmal.`);
  for (const f of liste) if (!istPdf(f)) throw new PdfFehler(`„${f.name}“ ist keine PDF-Datei.`);
  if (liste.reduce((s, f) => s + (f.size || 0), 0) > MAX_BYTES) throw new PdfFehler("Die Dateien sind zusammen größer als 100 MB.");
  let lib;
  try { lib = await laden(); } catch (e) { throw new PdfFehler(e?.message || "Das Werkzeug zum Zusammenfügen ließ sich nicht laden."); }
  const ziel = await lib.PDFDocument.create();
  let seiten = 0;
  for (const f of liste) {
    let quelle;
    try {
      quelle = await lib.PDFDocument.load(await f.arrayBuffer(), { ignoreEncryption: false, updateMetadata: false });
    } catch (e) {
      if (e?.name === "EncryptedPDFError" || /encrypt/i.test(e?.message || "")) {
        throw new PdfFehler(`„${f.name}“ ist mit einem Kennwort geschützt. Öffne sie, speichere sie ohne Kennwort und versuch es noch einmal.`);
      }
      throw new PdfFehler(`„${f.name}“ ließ sich nicht als PDF lesen.`);
    }

    let n, kopiert;
    try { n = quelle.getPageCount(); } catch { n = 0; }
    if (!n) throw new PdfFehler(`„${f.name}“ ließ sich nicht als PDF lesen.`);
    if (seiten + n > MAX_SEITEN) throw new PdfFehler(`Zusammen wären es mehr als ${MAX_SEITEN} Seiten.`);
    try { kopiert = await ziel.copyPages(quelle, quelle.getPageIndices()); } catch { throw new PdfFehler(`„${f.name}“ ließ sich nicht als PDF lesen.`); }
    for (const s of kopiert) ziel.addPage(s);
    seiten += n;
  }
  const bytes = await ziel.save();
  return { datei: new File([bytes], zielname(), { type: "application/pdf" }), dateien: liste.length, seiten, reihenfolge: liste.map((f) => f.name) };
}
