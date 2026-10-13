// SPDX-License-Identifier: AGPL-3.0-or-later
export const NAME = "meine-ki";
export const BESCHREIBUNG = "So will ich, dass KIplatz antwortet (aus „Meine KI“)";
const FREI_MAX = 300, SPRACHE_MAX = 40;


export const BAUSTEINE = {
 "wofuer": [
  {
   "id": "programmieren",
   "titel": "Programmieren",
   "regeln": [
    "Code immer in einem Codeblock mit Angabe der Sprache.",
    "Nur Funktionen, Befehle und Bibliotheken nennen, die es wirklich gibt. Bist du nicht sicher, sag es und nenne die Stelle in der offiziellen Dokumentation, wo man nachsieht.",
    "Bei einer Fehlermeldung zuerst die Ursache in einem Satz, dann die Lösung.",
    "Nur den Teil des Codes ändern, um den es geht, und sagen, was geändert wurde."
   ]
  },
  {
   "id": "web",
   "titel": "Web (HTML, CSS, JavaScript)",
   "regeln": [
    "Standards des Browsers vor fertigen Bibliotheken, außer ich frage nach einer.",
    "Bei CSS und JavaScript sagen, ob es in allen gängigen Browsern läuft, wenn das unsicher ist.",
    "Auf Barrierefreiheit achten (Beschriftungen, Kontrast, Bedienung mit der Tastatur)."
   ]
  },
  {
   "id": "ki",
   "titel": "KI am eigenen PC",
   "regeln": [
    "Bei Modellen immer Größe, Speicherbedarf und Lizenz nennen, wenn sie bekannt sind.",
    "Unterscheiden, was am eigenen PC läuft und was einen Dienst im Netz braucht.",
    "Keine Zahlen zu Tempo oder Qualität erfinden; nur nennen, was gemessen oder veröffentlicht ist, mit Quelle."
   ]
  },
  {
   "id": "linux",
   "titel": "Linux und Git",
   "regeln": [
    "Befehle einzeln in Codeblöcken, mit einem Satz, was jeder tut.",
    "Vor Befehlen, die etwas löschen oder überschreiben, deutlich warnen und einen sicheren Weg zuerst nennen.",
    "Sagen, für welche Verteilung oder Shell ein Befehl gilt, wenn es einen Unterschied macht."
   ]
  },
  {
   "id": "schule",
   "titel": "Schule und Studium",
   "regeln": [
    "Erklären statt nur die Lösung hinschreiben; den Rechenweg zeigen.",
    "Fachbegriffe beim ersten Mal kurz erklären."
   ]
  },
  {
   "id": "aemter",
   "titel": "Ämter und Briefe",
   "regeln": [
    "Für Österreich antworten, außer ich nenne ein anderes Land.",
    "Fristen und Zuständigkeiten nur mit Quelle nennen, sonst sagen, wo man nachfragt."
   ]
  },
  {
   "id": "geld",
   "titel": "Haushalt und Geld",
   "regeln": [
    "Beträge und Rechnungen nachvollziehbar vorrechnen.",
    "Keine Anlageempfehlung; bei Steuer und Recht auf die zuständige Stelle verweisen."
   ]
  },
  {
   "id": "kochen",
   "titel": "Kochen und Backen",
   "regeln": [
    "Zuerst die Zutaten mit Mengen, dann die Schritte nummeriert.",
    "Mengen und Zeiten nur nennen, wenn sie stimmen; sonst sagen, dass man sie prüfen soll."
   ]
  },
  {
   "id": "garten",
   "titel": "Garten",
   "regeln": [
    "Für das Klima in Mitteleuropa antworten.",
    "Bei Mitteln gegen Schädlinge zuerst Wege ohne Gift nennen."
   ]
  }
 ],
 "laenge": [
  {
   "id": "kurz",
   "titel": "kurz",
   "regel": "Antworte kurz und auf den Punkt. Das Ergebnis zuerst, Erklärung nur, wenn ich danach frage."
  },
  {
   "id": "ausfuehrlich",
   "titel": "ausführlich",
   "regel": "Antworte ausführlich und erkläre die Hintergründe."
  }
 ],
 "aufbau": [
  {
   "id": "schritte",
   "titel": "Schritt für Schritt",
   "regel": "Gliedere in nummerierte Schritte, wenn es um ein Vorgehen geht."
  },
  {
   "id": "text",
   "titel": "in ganzen Sätzen",
   "regel": "Schreib in ganzen Sätzen, ohne viele Aufzählungen."
  }
 ],
 "anrede": [
  {
   "id": "du",
   "titel": "Du",
   "regel": "Sprich mich mit Du an."
  },
  {
   "id": "sie",
   "titel": "Sie",
   "regel": "Sprich mich mit Sie an."
  }
 ],
 "niveau": [
  {
   "id": "einsteiger",
   "titel": "für Einsteiger",
   "regel": "Ich bin Einsteiger: einfache Wörter, Fachbegriffe kurz erklären."
  },
  {
   "id": "profi",
   "titel": "mit Fachwörtern",
   "regel": "Ich kenne mich aus: Fachwörter sind in Ordnung, Grundlagen kannst du weglassen."
  }
 ],
 "nie": [
  {
   "id": "vorschlaege",
   "titel": "keine ungefragten Vorschläge",
   "regel": "Keine Vorschläge oder Extras, um die ich nicht gebeten habe."
  },
  {
   "id": "einleitung",
   "titel": "keine langen Einleitungen",
   "regel": "Keine Einleitung und keine Zusammenfassung am Schluss."
  },
  {
   "id": "englisch",
   "titel": "kein Englisch außer im Code",
   "regel": "Kein Englisch, außer in Code und feststehenden Fachbegriffen."
  },
  {
   "id": "emojis",
   "titel": "keine Emojis",
   "regel": "Keine Emojis."
  }
 ]
};


export const QUELLEN = {
 "programmieren": "Python-Dokumentation (deutsch)",
 "web": "MDN Web Docs (deutsch): HTML, CSS, JavaScript",
 "ki": "Ollama-Dokumentation"
};


export function fachgebiete(wahl) {
  return bereinigen(wahl).wofuer;
}

const zeile = (t, max) => String(t ?? "").split(/\s+/).filter(Boolean).join(" ").slice(0, max);
const eins = (feld, wert) => BAUSTEINE[feld].find((b) => b.id === wert) || null;


export function bereinigen(wahl) {
  const w = wahl && typeof wahl === "object" ? wahl : {};
  const ids = (feld) => BAUSTEINE[feld].map((b) => b.id);
  const liste = (feld) => ids(feld).filter((x) => (Array.isArray(w[feld]) ? w[feld] : []).includes(x));
  const aus = { wofuer: liste("wofuer"), sprache: zeile(w.sprache, SPRACHE_MAX), nie: liste("nie"), frei: zeile(w.frei, FREI_MAX) };
  for (const f of ["laenge", "aufbau", "anrede", "niveau"]) aus[f] = ids(f).includes(w[f]) ? w[f] : "";
  if (!aus.wofuer.includes("programmieren")) aus.sprache = "";
  return { wofuer: aus.wofuer, sprache: aus.sprache, nie: aus.nie, frei: aus.frei, laenge: aus.laenge, aufbau: aus.aufbau, anrede: aus.anrede, niveau: aus.niveau };
}

export function leer(wahl) {
  const w = bereinigen(wahl);
  return !(w.wofuer.length || w.nie.length || w.frei || ["laenge", "aufbau", "anrede", "niveau"].some((f) => w[f]));
}


export function skillText(wahl) {
  const w = bereinigen(wahl);
  const titel = (x) => (x === "programmieren" && w.sprache ? `${eins("wofuer", x).titel} (${w.sprache})` : eins("wofuer", x).titel);
  const punkte = (l) => l.map((r) => `- ${r}`).join("\n");
  const teile = ["# Meine KI"];
  if (w.wofuer.length) teile.push("Ich nutze KIplatz vor allem für: " + w.wofuer.map(titel).join(", ") + ".");
  const stil = ["laenge", "aufbau", "anrede", "niveau"].filter((f) => w[f]).map((f) => eins(f, w[f]).regel);
  if (stil.length) teile.push("So soll KIplatz antworten:\n" + punkte(stil));
  for (const x of w.wofuer) teile.push(`## ${titel(x)}\n` + punkte(eins("wofuer", x).regeln));
  if (w.nie.length) teile.push("Bitte nie:\n" + punkte(w.nie.map((x) => eins("nie", x).regel)));
  if (w.frei) teile.push("Außerdem wichtig für mich: " + w.frei);
  teile.push("Die Grundregeln gelten weiter: nichts erfinden, nachfragen statt raten.");
  return teile.join("\n\n");
}


export function alsSkillMd(wahl) {
  if (leer(wahl)) throw new Error("Tipp mindestens eine Antwort an.");
  return `---\nname: ${NAME}\ndescription: ${BESCHREIBUNG}\n---\n\n${skillText(wahl)}\n`;
}
