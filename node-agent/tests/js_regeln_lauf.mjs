// Für test_ende_zu_ende_js_2026_11_19.py: liest Fälle als JSON von stdin, wendet die Regeln der App an (app/www/js/regeln.js) und schreibt
// die Ergebnisse als JSON nach stdout. Nur zum Vergleich mit dem Programm, nie ausgeliefert.
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const wurzel = resolve(process.argv[2]);
const R = await import(pathToFileURL(resolve(wurzel, "app/www/js/regeln.js")).href);
let roh = "";
for await (const teil of process.stdin) roh += teil;
const faelle = JSON.parse(roh);
const aus = {
  krise: faelle.texte.map((t) => R.krisenhilfeSprache(t)),
  haus: faelle.texte.map((t) => { const b = R.hausordnungPruefen(t); return [b.ok, b.grund]; }),
  unkenntlich: faelle.texte.map((t) => R.unkenntlich(t)),
  woerter: faelle.texte.map((t) => R.woerter(t)),
  saetze: faelle.texte.map((t) => R.saetze(t)),
  speicher: await Promise.all(faelle.texte.map((t) => R.speicherFreigabe([{ role: "user", content: t }]))),
  pruefen: faelle.paare.map(([a, ausz, en]) => {
    const p = R.pruefen(a, ausz, { englisch: en });
    return [p.saetze.map((s) => [s.farbe, s.quelle, s.genannt, s.widerspruch, s.text]), p.gruen, p.gelb, p.rot, p.unbestimmt, p.widersprueche, p.text];
  }),
};
process.stdout.write(JSON.stringify(aus));
