// SPDX-License-Identifier: AGPL-3.0-or-later
import { Gespraeche, titelAus, MAX_GESPRAECHE, MAX_NACHRICHTEN, tagesgruss } from "/js/gespraeche.js";
import { mitOrt, sauber } from "/js/einrichten.js";
import { bloecke, stuecke, zeichnen, nurRueckfrage } from "/js/antwort.js";
import { fassungVergleich, standBewerten, holen, ServerFehler, basisSetzen } from "/js/schnittstelle.js";
import * as ak from "/js/abgleich-krypto.js";
import * as pl from "/js/platzl.js";
import * as sk from "/js/skills.js";
import * as an from "/js/anhang.js";
import * as sp from "/js/sprache.js";
import { ausGemeinsam } from "/js/abgleich.js";
import * as hf from "/js/helfer.js";
import { HELFER_SHA256 } from "/js/helfer-pruefsummen.js";
import * as kt from "/js/konten.js";
import * as mk from "/js/meine-ki.js";

basisSetzen("");

const faelle = [];
const test = (name, fn) => faelle.push({ name, fn });
const gleich = (a, b, was = "") => { const x = JSON.stringify(a), y = JSON.stringify(b); if (x !== y) throw new Error(`${was} erwartet ${y}, bekommen ${x}`); };
const wahr = (a, was) => { if (!a) throw new Error(was || "nicht wahr"); };


test("Konten: Fächer, Liste ohne Doppel, dasselbe Konto wird erkannt", () => {
  const alt = localStorage.getItem("kiplatz.konten"), altBesitzer = localStorage.getItem("kiplatz.fach-besitzer");
  try {
    localStorage.removeItem("kiplatz.konten"); localStorage.removeItem("kiplatz.fach-besitzer");
    const f = kt.aktivesFach();
    gleich(kt.name("gespraeche"), f ? `gespraeche.${f}` : "gespraeche");
    gleich(kt.name("geraet"), f ? `geraet.${f}` : "geraet");
    gleich(kt.name("ort"), "ort", "der Ort gehört dem Gerät");
    gleich(kt.name("anmeldung"), "anmeldung", "die laufende Anmeldung gehört dem Gerät");
    kt.merken({ konto: "Anna", benutzer: "anna", name: "Handy" });
    kt.merken({ konto: "Anna B.", benutzer: "anna", name: "Handy" });
    gleich(kt.liste().length, 1); gleich(kt.liste()[0].konto, "Anna B.");
    localStorage.setItem("kiplatz.konten", JSON.stringify([...kt.liste(), { fach: "k0000abcd", konto: "Bert", benutzer: "bert" }, { fach: "../boese", konto: "x" }]));
    gleich(kt.doppelt({ benutzer: "bert" })?.fach, f === "k0000abcd" ? undefined : "k0000abcd");
    gleich(kt.doppelt({ benutzer: "" }), null, "ohne Benutzername kein Vergleich");
    wahr(/^k[0-9a-f]{8}$/.test(kt.neuesFach()), "neues Fach");
    wahr(kt.liste().every((k) => /^(|k[0-9a-f]{8})$/.test(k.fach)), "nur saubere Fächer");
    gleich(kt.doppelt({ benutzer: "", konto: "Bert" }), null, "am Anzeigenamen nie: der ist nicht eindeutig");
    kt.vergessen();
    wahr(!kt.liste().some((k) => k.fach === f && k.konto === "Anna B."), "abgemeldet heißt aus der Liste");
    wahr(kt.fremdesFach({ benutzer: "cora", konto: "Cora" }), "das Fach gehört noch Anna: Cora bekommt ein eigenes");
    wahr(!kt.fremdesFach({ benutzer: "anna", konto: "Anna" }), "Anna selbst darf zurück in ihr Fach");
  } finally {
    if (alt === null) localStorage.removeItem("kiplatz.konten"); else localStorage.setItem("kiplatz.konten", alt);
    if (altBesitzer === null) localStorage.removeItem("kiplatz.fach-besitzer"); else localStorage.setItem("kiplatz.fach-besitzer", altBesitzer);
  }
});

test("ein leeres Gespräch wird wiederverwendet", () => {
  const g = new Gespraeche();
  const erstes = g.aktuellId;
  g.neu();
  gleich(g.liste.length, 1); gleich(g.aktuellId, erstes);
  g.hinzufuegen({ rolle: "user", text: "Hallo" });
  g.neu();
  gleich(g.liste.length, 2);
});

test("Titel aus der ersten Frage, gekürzt; eigener Name gewinnt", () => {
  gleich(titelAus([]), "Neues Gespräch");
  const lang = "Wie   funktioniert eigentlich der verteilte Speicher bei KIplatz genau und warum?";
  wahr(titelAus([{ rolle: "user", text: lang }]).endsWith("…"), "gekürzt");
  const g = new Gespraeche();
  g.hinzufuegen({ rolle: "user", text: "Frage" });
  g.umbenennen(g.aktuellId, "  Mein   Name ");
  gleich(g.titel(g.aktuell), "Mein Name");
  g.umbenennen(g.aktuellId, "");
  gleich(g.titel(g.aktuell), "Frage");
});

test("angeheftete zuerst, Suche in Titel und Text", () => {
  const g = new Gespraeche();
  g.hinzufuegen({ rolle: "user", text: "Wetter in Gmunden" }); const a = g.aktuellId;
  g.neu(); g.hinzufuegen({ rolle: "user", text: "Rezept Kaiserschmarrn" }); g.hinzufuegen({ rolle: "assistant", text: "Mehl, Eier, Milch" });
  g.anheften(a);
  gleich(g.sortiert()[0].kennung, a);
  gleich(g.suchen("EIER").length, 1);
  gleich(g.suchen("gmunden")[0].kennung, a);
  gleich(g.suchen("").length, 2);
});

test("löschen wählt ein anderes Gespräch und lässt nie null übrig", () => {
  const g = new Gespraeche();
  g.hinzufuegen({ rolle: "user", text: "eins" });
  g.loeschen(g.aktuellId);
  gleich(g.liste.length, 1); wahr(g.aktuell, "aktuell da");
});

test("Grenzen: 200 Nachrichten, 100 Gespräche, angeheftete bleiben", () => {
  const g = new Gespraeche();
  for (let i = 0; i < MAX_NACHRICHTEN + 20; i++) g.hinzufuegen({ rolle: "user", text: "n" + i });
  const alt = g.aktuellId; g.anheften(alt); g.aktuell.zeit = 0;
  for (let i = 0; i < MAX_GESPRAECHE + 10; i++) { g.neu(); g.hinzufuegen({ rolle: "user", text: "g" + i }); }
  g.daten();
  gleich(g.liste.find((x) => x.kennung === alt).nachrichten.length, MAX_NACHRICHTEN);
  wahr(g.liste.length <= MAX_GESPRAECHE + 1, "höchstens 100 plus angeheftete");
  wahr(g.liste.some((x) => x.kennung === alt), "angeheftetes bleibt");
});

test("kaputte Ablage wird verworfen statt abzustürzen", () => {
  const g = Gespraeche.aus({ liste: [null, { kennung: 5 }, { kennung: "x", nachrichten: "nein" }], aktuell: "weg" });
  gleich(g.liste.length, 1); wahr(g.aktuell);
});

test("Antwort in Blöcke: Absatz, Liste, Nummern, Code, Überschrift", () => {
  const b = bloecke("# Titel\nZeile eins\nZeile zwei\n\n- a\n- b\n1. x\n2) y\n```\ncode <b>\n```\nSchluss");
  gleich(b.map((x) => x.art), ["ueberschrift", "absatz", "punkte", "nummern", "codeblock", "absatz"]);
  gleich(b[2].punkte, ["a", "b"]); gleich(b[4].text, "code <b>");
  gleich(stuecke("a **fett** und `code`").map((s) => s.art), ["text", "fett", "text", "code"]);
});


const BENZIN = "Hier die aktuelle Vergleichstabelle:\n\n"
  + "| Land        | Preis (€/L) | Quelle |\n|-------------|------------:|--------|\n"
  + "| Österreich | 1,93 € | WKO (Wirtschaftskammer Österreich) |\n| Deutschland | 1,89 € | tankplus.de |\n| Schweiz | 2,15 CHF | <b>x</b> a \\| b |\n"
  + "Hinweis: Die Schweiz ist teurer.";
test("Tabelle wird eine echte Tabelle, Text davor und danach bleibt", () => {
  const b = bloecke(BENZIN);
  gleich(b.map((x) => x.art), ["absatz", "tabelle", "absatz"]);
  gleich(b[1].kopf, ["Land", "Preis (€/L)", "Quelle"]);
  gleich(b[1].ausrichtung, ["", "right", ""]);
  gleich(b[1].reihen[2], ["Schweiz", "2,15 CHF", "<b>x</b> a | b"]);
  const el = document.createElement("div");
  zeichnen(el, BENZIN, null);
  gleich(el.querySelectorAll("table thead th").length, 3);
  gleich(el.querySelectorAll("table tbody tr").length, 3);
  wahr(!el.textContent.includes("---"), "keine Trennstriche mehr");
  gleich(el.querySelectorAll("b").length, 0, "kein eingeschleustes HTML in Zellen");
});
test("Tabelle: fehlende Zellen leer, zu viele gehen nicht verloren, ohne Trennzeile kein Umbau", () => {
  const t = bloecke("a | b\n--|--\n1 |\n1 | 2 | 3")[0];
  gleich([t.kopf, t.reihen], [["a", "b", ""], [["1", "", ""], ["1", "2", "3"]]]);
  gleich(bloecke("Preis | Ort\n1 | Wien").map((x) => x.art), ["absatz"]);
  gleich(bloecke("Oben\n\n---\n\nUnten").map((x) => x.art), ["absatz", "absatz", "absatz"]);
});

test("Antwort kann kein HTML einschleusen", () => {
  const el = document.createElement("div");
  zeichnen(el, 'Hallo <img src=x onerror="window.BOESE=1"> **<script>x</script>**', null);
  gleich(el.querySelectorAll("img, script").length, 0, "keine fremden Elemente");
  wahr(el.textContent.includes("<img src=x"), "als Text sichtbar");
  wahr(!window.BOESE, "nichts ausgeführt");
});


test("Antwort: kein Punkt hinter Sätzen, auch wenn alle ohne Quelle sind", () => {
  const el = document.createElement("div");
  zeichnen(el, "Dividieren heißt teilen. Du hast 6 Äpfel. Drei Kinder bekommen gleich viel.\n\n| Kind | Äpfel |\n|--|--|\n| Anna | 2 |");
  gleich(el.querySelectorAll("span").length, 0, "kein Zeichen im Text");
  wahr(el.textContent.startsWith("Dividieren heißt teilen. Du hast 6 Äpfel. Drei Kinder bekommen gleich viel."), "Text unverändert");
  gleich(el.querySelectorAll("tbody tr").length, 1);
});


test("Start: leeres Gespräch vorne, alte bleiben; Gruß nach Uhrzeit", () => {
  const g = new Gespraeche([{ kennung: "a", nachrichten: [{ rolle: "user", text: "Hallo" }], zeit: 5 }], "a");
  g.neu();
  gleich(g.aktuell.nachrichten.length, 0);
  gleich(g.liste.length, 2);
  const leer = g.aktuellId; g.neu();
  gleich([g.aktuellId, g.liste.length], [leer, 2]);
  gleich([7, 12, 15, 20, 2].map(tagesgruss), ["Guten Morgen", "Mahlzeit", "Schönen Nachmittag", "Guten Abend", "Noch munter"]);
});


test("Wohnort: nur bei Wetter oder „in der Nähe“, nie doppelt, nie bei anderen Fragen", () => {
  gleich(mitOrt("Wie wird das Wetter morgen?", "Gmunden"), "Wie wird das Wetter morgen in Gmunden?");
  gleich(mitOrt("Wie wird das Wetter in Linz?", "Gmunden"), null);
  gleich(mitOrt("Wo ist eine Apotheke in der Nähe", "Gmunden"), "Wo ist eine Apotheke in der Nähe? Ich wohne in Gmunden.");
  gleich(mitOrt("Gibt es in meiner Nähe einen Bäcker? Ich bin in Gmunden.", "Gmunden"), null);
  gleich(mitOrt("Was ist nächste Woche los?", "Gmunden"), null);
  gleich(mitOrt("Wer ist Bundeskanzler?", "Gmunden"), null);
  gleich(mitOrt("Wie wird das Wetter?", ""), null);
  gleich(sauber("  Phil\n\tipp  ", 40), "Phil ipp");
  gleich(sauber("x".repeat(50), 40).length, 40);
});


test("Rückfrage: keine Ampel, auch wenn ein älterer PC sie geprüft hat", () => {
  gleich(nurRueckfrage({ gemacht: "nachgefragt" }), true);
  gleich(nurRueckfrage({ gemacht: "geantwortet" }), false);
  gleich(nurRueckfrage(undefined), false);
});

test("Fassungen vergleichen", () => {
  gleich(fassungVergleich("0.1.0", "0.1.0"), 0);
  gleich(fassungVergleich("0.9.0", "0.10.0"), -1);
  gleich(fassungVergleich("1.0", "0.99.9"), 1);
  gleich(fassungVergleich("1.0.0", "1"), 0);
});

test("Update-Prüfung: Sperre unter mindestens, Hinweis unter neueste", () => {
  gleich(standBewerten(null).art, "ok");
  gleich(standBewerten({ mindestens: "0.1.0", neueste: "0.1.0" }, "0.1.0").art, "ok");
  gleich(standBewerten({ mindestens: "0.1.0", neueste: "0.2.0" }, "0.1.0").art, "hinweis");
  gleich(standBewerten({ mindestens: "0.2.0", neueste: "0.2.0" }, "0.1.5").art, "sperre");
});

test("Schnittstelle: nur eigene Wege, Fehler als Satz", async () => {
  let fehler = null;
  try { await holen("https://boese.example/x"); } catch (e) { fehler = e; }
  wahr(fehler instanceof ServerFehler, "fremde Adresse abgelehnt");
  const stand = await holen("/app-stand");
  wahr(stand.mindestens && stand.neueste, "Dienst liefert /app-stand");
  fehler = null;
  try { await holen("/antwort/123", { geraet: { kennung: "x", schluessel: "y" } }); } catch (e) { fehler = e; }
  gleich(fehler?.status, 401);
  wahr(/^[A-ZÄÖÜ]/.test(fehler.message), "Satz beginnt groß: " + fehler.message);
});


const V = await (await fetch("abgleich-vektoren.json", { cache: "no-store" })).json();
test("Abgleich: liest den Block des Programms und macht Byte für Byte denselben", async () => {
  const k = ak.unb64(V.kontoschluessel);
  gleich(await ak.blockEntschluesseln(k, V.id, V.block), V.gespraech);
  gleich(await ak.blockVerschluesseln(k, V.id, V.gespraech, ak.unb64(V.iv)), V.block);
  let fehler = null;
  try { await ak.blockEntschluesseln(k, "f".repeat(32), V.block); } catch (e) { fehler = e; }
  wahr(fehler instanceof ak.KryptoFehler, "unter fremder Kennung abgelehnt");
});
test("Abgleich: Fach und Prüfzahl wie im Programm", async () => {
  const k = ak.unb64(V.kontoschluessel);
  gleich(Array.from(await ak.fachOeffnen(V.fach, V.geraet_jwk)), Array.from(k));
  gleich(await ak.fachPacken(k, V.geraet_oeffentlich, { wegwerf: V.wegwerf_jwk, iv: ak.unb64(V.iv) }), V.fach);
  gleich(await ak.pruefzahl(V.geraet_oeffentlich), V.pruefzahl);
  gleich(await ak.siegel(k, V.siegel_kennung, V.geraet_oeffentlich), V.siegel);
  wahr(!(await ak.siegelPruefen(k, "anderes0000", V.geraet_oeffentlich, V.siegel)), "Siegel gilt nur für diese Kennung");
  const fremd = await ak.neuesGeraet();
  let fehler = null;
  try { await ak.fachOeffnen(V.fach, fremd.privat); } catch (e) { fehler = e; }
  wahr(fehler instanceof ak.KryptoFehler, "fremdes Gerät kann das Fach nicht öffnen");
});
test("Abgleich: Wiederherstellungsschlüssel wie im Programm, auch klein und mit O statt 0", async () => {
  const k = ak.unb64(V.kontoschluessel);
  gleich(Array.from(await ak.wiederherstellungOeffnen(V.wiederherstellung, V.wiederherstellung_text.toLowerCase().replace(/0/g, "o"))), Array.from(k));
  gleich(await ak.wiederherstellungPacken(k, V.wiederherstellung_text, ak.unb64(V.iv)), V.wiederherstellung);
  const r = ak.neuerWiederherstellungsschluessel();
  gleich(ak.wiederherstellungZeigen(ak.wiederherstellungLesen(r)), r);
});
test("Abgleich: frische Schlüssel, hin und zurück", async () => {
  const k = ak.neuerKontoschluessel(), g = await ak.neuesGeraet();
  gleich(Array.from(await ak.fachOeffnen(await ak.fachPacken(k, g.oeffentlich), g.privat)), Array.from(k));
  const b = await ak.blockVerschluesseln(k, "a".repeat(32), { titel: "Äpfel €" });
  gleich((await ak.blockEntschluesseln(k, "a".repeat(32), b)).titel, "Äpfel €");
  wahr((ak.unb64(b).length - 29) % ak.AUFFUELLEN === 0, "aufgefüllt");
});


test("Platzl: Beiträge nur als sichere Bausteine, keine Skripte, Bilder, fremden Links", () => {
  window.platzlFalle = 0;
  const f = pl.inhaltBauen('<p>Hi <strong>du</strong> <a href="https://kiplatz.at/wiki/">Wiki</a> <a href="javascript:alert(1)">x</a> <a href="/t/5">rel</a></p>'
    + '<script>window.platzlFalle=1</script><img src="x" onerror="window.platzlFalle=2" alt="Foto"><iframe src="https://example.org"></iframe>'
    + '<div onclick="x()" style="color:red"><span class="emoji">🙂</span>Text</div><svg><script>1</script></svg>');
  const box = document.createElement("div"); box.append(f); document.body.append(box);
  try {
    gleich(box.querySelectorAll("script,img,iframe,svg,[onclick],[style],[onerror]").length, 0, "gefährliche Teile");
    gleich([...box.querySelectorAll("a")].map((a) => a.href), ["https://kiplatz.at/wiki/", "https://forum.kiplatz.at/t/5"], "Links");
    wahr(box.textContent.includes("[Bild: Foto]") && box.textContent.includes("Text"), "Text bleibt");
    gleich(window.platzlFalle, 0, "Falle");
  } finally { box.remove(); }
});
test("Platzl: Kategoriefarbe nur als Hex, sonst grau", () => {
  gleich(pl.kategorieFarbe("3F9A7E"), "#3F9A7E"); gleich(pl.kategorieFarbe("fff"), "#fff");
  gleich(pl.kategorieFarbe("red;background:url(x)"), "#8a949c"); gleich(pl.kategorieFarbe(null), "#8a949c");
});
test("Platzl: die Antwort öffnet nur das eigene Schlüsselpaar und nur mit der richtigen Nummer", async () => {
  const p = await pl.schluesselpaar();
  wahr((await pl.pem(p.publicKey)).startsWith("-----BEGIN PUBLIC KEY-----\n"), "PEM");
  const roh = new TextEncoder().encode(JSON.stringify({ key: "a1b2c3d4e5f6a7b8c9d0", nonce: "n1", push: false, api: 4 }));
  const geheim = btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.encrypt({ name: "RSA-OAEP" }, p.publicKey, roh))));
  gleich(await pl.antwortOeffnen(p.privateKey, geheim.replace(/(.{60})/g, "$1\n"), "n1"), "a1b2c3d4e5f6a7b8c9d0");
  let fehler = 0;
  try { await pl.antwortOeffnen(p.privateKey, geheim, "n2"); } catch { fehler++; }
  const fremd = await pl.schluesselpaar();
  try { await pl.antwortOeffnen(fremd.privateKey, geheim, "n1"); } catch { fehler++; }
  gleich(fehler, 2, "abgelehnt");
});


test("Skill: SKILL.md lesen wie das Programm, Name aus dem Kopf oder der Überschrift", () => {
  const s = sk.lesen("---\nname: brief-ans-amt\ndescription: \"Briefe an Ämter\"\n---\n\nSchreibe sachlich, mit Betreff und Grußformel.");
  gleich([s.name, s.beschreibung], ["brief-ans-amt", "Briefe an Ämter"]);
  gleich(sk.lesen("# Kochen mit Oma\n\nErkläre jedes Rezept Schritt für Schritt.").name, "Kochen mit Oma");
  let fehler = 0;
  for (const schlecht of ["kurz", "ohne Namen und ohne Überschrift, aber lang genug", "x".repeat(sk.MAX_TEXT + 1)]) { try { sk.lesen(schlecht); } catch { fehler++; } }
  gleich(fehler, 3);
});
test("Skill: aus dem Platzl-Beitrag nur der erste Codeblock, nur als Text", () => {
  gleich(pl.skillImBeitrag('<p>Hallo</p><pre><code>---\nname: a\n---\n&lt;script&gt;x&lt;/script&gt; Anweisungen</code></pre><pre><code>zweiter</code></pre>'),
    "---\nname: a\n---\n<script>x</script> Anweisungen");
  gleich(pl.skillImBeitrag("<p>kein Skill</p>"), null);
});
test("Skill: merken ersetzt gleichen Namen und sagt, ob sich etwas geändert hat", () => {
  const alt = localStorage.getItem("kiplatz.skills");
  try {
    localStorage.removeItem("kiplatz.skills");
    gleich(sk.merken({ name: "t", text: "Fassung 1 mit genug Text" }), "neu");
    gleich(sk.merken({ name: "t", text: "Fassung 1 mit genug Text" }), "gleich");
    gleich(sk.merken({ name: "t", text: "Fassung 2 mit genug Text" }), "aktualisiert");
    gleich([sk.liste().length, sk.holen("t").text], [1, "Fassung 2 mit genug Text"]);
    sk.entfernen("t"); gleich(sk.holen("t"), null);
  } finally { if (alt === null) localStorage.removeItem("kiplatz.skills"); else localStorage.setItem("kiplatz.skills", alt); }
});
test("Skill: „Immer an“ gilt in jedem Gespräch, mit dem gewählten zuerst, jeder einmal, nur so viel wie der Server annimmt", () => {
  const alt = localStorage.getItem("kiplatz.skills");
  try {
    localStorage.removeItem("kiplatz.skills");
    const A = "---\nname: a\ndescription: Erster\n---\n\nAnweisungen von a, lang genug.";
    sk.merken({ name: "a", beschreibung: "Erster", text: A });
    sk.merken({ name: "b", text: "Anweisungen von b, lang genug." });
    gleich(sk.fuerGespraech("").mit.length, 0, "ohne Immer an");
    sk.immerSetzen("b", true); sk.immerSetzen("a", true);
    gleich(sk.fuerGespraech("").mit.map((s) => s.name), ["b", "a"], "Reihenfolge des Einschaltens");
    gleich(sk.fuerGespraech("a").mit.map((s) => s.name), ["a", "b"], "gewählter zuerst, nicht doppelt");
    sk.merken({ name: "a", beschreibung: "Erster", text: A + " neu" });
    wahr(sk.holen("a").immer, "neu laden lässt „Immer an“ stehen");
    const e = sk.alsEine(sk.fuerGespraech("").mit);
    gleich(e.name, "b und a");
    const gelesen = sk.lesen(e.text);
    wahr(gelesen.name === "b und a" && e.text.includes("# Skill „a“ (Erster)") && e.text.includes("Anweisungen von b") && !e.text.includes("name: a\n"), "eine SKILL.md, Köpfe raus");
    sk.merken({ name: "gross", text: "x".repeat(sk.MAX_TEXT - 100) });
    sk.immerSetzen("gross", true);
    const f = sk.fuerGespraech("");
    gleich([f.mit.map((s) => s.name), f.weg.map((s) => s.name)], [["b", "a"], ["gross"]], "zu viel Text bleibt weg statt die Frage zu sprengen");
    sk.immerSetzen("a", false);
    gleich(sk.immer().map((s) => s.name), ["b", "gross"]);
  } finally { if (alt === null) localStorage.removeItem("kiplatz.skills"); else localStorage.setItem("kiplatz.skills", alt); }
});

test("Platzl schreiben: zu kurz, ohne Titel oder Kategorie geht gar nicht erst hinaus", async () => {
  const faelle = [{ text: "kurz", thema: 5 }, { text: "Ein Text, der lang genug ist.", titel: "kurz", kategorie: 3 }, { text: "Ein Text, der lang genug ist.", titel: "Ein Titel mit genug Zeichen" }];
  let abgelehnt = 0;
  for (const f of faelle) { try { await pl.schreiben(f); } catch (e) { if (!/Platzl ist mit diesem Gerät nicht verbunden/.test(e.message)) abgelehnt++; } }
  gleich(abgelehnt, 3);
});


async function zipBauen(name, inhalt, klein = null) {
  const roh = typeof inhalt === "string" ? new TextEncoder().encode(inhalt) : inhalt;
  const gepackt = new Uint8Array(await new Response(new Blob([roh]).stream().pipeThrough(new CompressionStream("deflate-raw"))).arrayBuffer());
  const n = new TextEncoder().encode(name);
  const lokal = new Uint8Array(30 + n.length), zentral = new Uint8Array(46 + n.length), ende = new Uint8Array(22);
  const l = new DataView(lokal.buffer), z = new DataView(zentral.buffer), e = new DataView(ende.buffer);
  l.setUint32(0, 0x04034b50, true); l.setUint16(8, 8, true); l.setUint32(18, gepackt.length, true); l.setUint32(22, klein ?? roh.length, true); l.setUint16(26, n.length, true); lokal.set(n, 30);
  z.setUint32(0, 0x02014b50, true); z.setUint16(10, 8, true); z.setUint32(20, gepackt.length, true); z.setUint32(24, klein ?? roh.length, true); z.setUint16(28, n.length, true); z.setUint32(42, 0, true); zentral.set(n, 46);
  e.setUint32(0, 0x06054b50, true); e.setUint16(8, 1, true); e.setUint16(10, 1, true); e.setUint32(12, zentral.length, true); e.setUint32(16, lokal.length + gepackt.length, true);
  const aus = new Uint8Array(lokal.length + gepackt.length + zentral.length + ende.length);
  aus.set(lokal, 0); aus.set(gepackt, lokal.length); aus.set(zentral, lokal.length + gepackt.length); aus.set(ende, lokal.length + gepackt.length + zentral.length);
  return aus;
}

test("Anhang: erlaubte Arten wie im Programm, alles andere nicht", () => {
  gleich(["a.PDF", "b.docx", "c.txt", "d.md", "e.csv", "f.html", "g.jpg", "h.heic", "i.exe", "j.doc", "k"].map((n) => an.art(n)),
    ["pdf", "docx", "text", "text", "text", "html", "bild", "bild", null, null, null]);
  gleich(an.art("foto", "image/png"), "bild");
});

test("Anhang: Word-Text mit Absätzen, Tabulator und Umlauten", async () => {
  const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  const xml = `<?xml version="1.0"?><w:document xmlns:w="${W}"><w:body><w:p><w:r><w:t>Straßenfest</w:t></w:r><w:r><w:tab/><w:t>Öffnung</w:t></w:r></w:p><w:p><w:r><w:t xml:space="preserve">Zeile </w:t></w:r><w:r><w:t>zwei</w:t></w:r></w:p></w:body></w:document>`;
  gleich(await an.docxText(await zipBauen("word/document.xml", xml)), "Straßenfest Öffnung\nZeile zwei");
});

test("Anhang: ZIP-Bombe mit gelogener Größe wird nach 60 MB abgebrochen", async () => {
  const bombe = await zipBauen("word/document.xml", new Uint8Array(61 * 1024 * 1024), 100);
  let fehler = "";
  try { await an.docxText(bombe); } catch (e) { fehler = e instanceof an.AnhangFehler ? e.message : "falscher Fehler: " + e; }
  gleich(fehler, "Die Word-Datei ist zu groß.");
  let keinWord = "";
  try { await an.docxText(await zipBauen("anderes.xml", "x")); } catch (e) { keinWord = e.message; }
  gleich(keinWord, "Das ist keine Word-Datei (.docx).");
});

test("Anhang: HTML nur sichtbarer Text, Skripte und Stile fallen weg", () => {
  gleich(an.htmlText("<html><head><style>p{}</style><script>alert(1)</script></head><body><h1>Titel</h1><p>Hallo <b>Welt</b></p><img src=x onerror=alert(2)></body></html>"), "Titel\nHallo Welt");
  gleich(an.htmlText("<table><tr><td>Preis</td><td>1,80</td></tr></table>"), "Preis 1,80");
});

test("Anhang: Nachricht bleibt unter 8000 Zeichen, gekürzt wird sichtbar und gerecht", () => {
  const kurz = an.nachricht(" Was steht drin? ", [{ name: "a.txt", info: "Text", text: "Hallo" }]);
  gleich([kurz.text, kurz.mit, kurz.gekuerzt], ["Was steht drin?", "Datei „a.txt“ (Text):\nHallo", []]);
  gleich(an.nachricht("Frage", []), { text: "Frage", mit: "", gekuerzt: [] });
  const lang = an.nachricht("Fasse zusammen", [{ name: "gross.pdf", info: "PDF", text: "wort ".repeat(5000) }, { name: "klein.txt", info: "Text", text: "kurz und gut" }]);
  wahr(an.inhalt(lang).length <= an.MAX_NACHRICHT, "zu lang: " + an.inhalt(lang).length);
  wahr(lang.mit.includes("kurz und gut"), "der kurze Anhang geht ganz mit");
  wahr(lang.mit.includes(" […]"), "Kürzung ist sichtbar");
  gleich(lang.gekuerzt.map((g) => g.name), ["gross.pdf"]);
  const drei = an.nachricht("F", [1, 2, 3].map((i) => ({ name: i + ".txt", info: "Text", text: "ä".repeat(9000) })));
  wahr(an.inhalt(drei).length <= an.MAX_NACHRICHT, "drei lange zu lang");
  gleich(drei.gekuerzt.length, 3);
});

test("Anhang: Verlauf trägt nur die letzten zwei Anhänge und passt unter die Grenze des Dienstes", () => {
  const n = [];
  for (let i = 0; i < 6; i++) {
    n.push({ rolle: "user", text: "Frage " + i, mit: "Datei „d" + i + ".pdf“:\n" + "ä".repeat(7000), anhaenge: [{ name: "d" + i + ".pdf", zeichen: 7000 }] });
    n.push({ rolle: "assistant", text: "Antwort " + i });
  }
  n.push({ rolle: "assistant", text: "kaputt", fehler: true });
  const v = an.verlaufBauen(n);
  wahr(new TextEncoder().encode(JSON.stringify(v)).length <= an.MAX_BODY_BYTES, "zu groß");
  gleich(v.at(-1).content, "Antwort 5", "Fehlversuche gehen nie mit");
  const mitText = v.filter((x) => x.content.includes("ääää")).length;
  wahr(mitText <= 2, "mehr als zwei Anhänge mit Text: " + mitText);
  const alt = an.verlaufBauen(n, 10 ** 9).find((x) => x.content.startsWith("Frage 0"));
  gleich(alt.content, "Frage 0\n\n[angehängt war: „d0.pdf“]");
});

test("Sprechen: Mono auf 16 000 je Sekunde, Text anhängen wie im Programm, Helfer nur von zwei Orten", () => {
  const links = new Float32Array(48000).fill(0.5), rechts = new Float32Array(48000).fill(-0.5);
  const m = sp.aufMono16k([links, rechts], 48000);
  gleich([m.length, m[0], m[15999]], [16000, 0, 0]);
  gleich(sp.aufMono16k([new Float32Array([0.25, 0.5])], 16000), new Float32Array([0.25, 0.5]));
  gleich([sp.anhaengen("", " Hallo "), sp.anhaengen("Hallo", "Welt"), sp.anhaengen("Hallo ", "Welt"), sp.anhaengen("Hallo", "  ")], ["Hallo", "Hallo Welt", "Hallo Welt", "Hallo"]);
  gleich(sp.helferBasis(new URL("https://kiplatz.at/app-neu/"), false), "https://kiplatz.at/ki-helfer/");
  gleich(sp.helferBasis(new URL("http://127.0.0.1:8780/"), false), "http://127.0.0.1:8780/ki-helfer/");
  gleich(sp.helferBasis(new URL("https://localhost/"), true), "https://kiplatz.at/ki-helfer/", "Android-App");
  gleich(sp.helferBasis({ protocol: "capacitor:", origin: "capacitor://localhost" }, false), "https://kiplatz.at/ki-helfer/", "iOS-App");
});

test("Helfer: nur Dateien, die Byte für Byte zur Prüfsumme in der App passen", async () => {
  gleich(await hf.stimmt("pdfjs/pdf.min.mjs", new Uint8Array([1, 2, 3])), false);
  gleich(await hf.stimmt("fremd/boese.js", new Uint8Array(0)), false, "unbekannte Datei");
  wahr(Object.keys(HELFER_SHA256).length >= 20 && Object.values(HELFER_SHA256).every((h) => /^[0-9a-f]{64}$/.test(h)), "Prüfsummen in der App");
  let fehler = "";
  try { await hf.bytes("../geheim.js"); } catch (e) { fehler = e instanceof hf.HelferFehler ? "abgewiesen" : String(e); }
  gleich(fehler, "abgewiesen");
});

test("Helfer: ein übernommener Server bringt keinen fremden Code in die App, ein verfälschter Speicher auch nicht", async () => {
  const pfad = "lizenzen/pdfjs.txt";
  const schluessel = `https://ki-helfer.invalid/${HELFER_SHA256[pfad]}/${pfad}`;
  const ablage = await caches.open("kiplatz-helfer");
  await ablage.delete(schluessel);
  const echt = globalThis.fetch;
  globalThis.fetch = async () => new Response("alert('übernommen')", { status: 200 });
  let fehler = "";
  try { await hf.bytes(pfad); } catch (e) { fehler = e instanceof hf.HelferFehler ? "abgewiesen" : String(e); }
  finally { globalThis.fetch = echt; }
  gleich(fehler, "abgewiesen", "Server");
  gleich(await ablage.match(schluessel), undefined, "nichts Ungeprüftes abgelegt");
  await ablage.put(schluessel, new Response("verfälscht"));
  const b = await hf.bytes(pfad);
  wahr(await hf.stimmt(pfad, b), "echte Datei");
  wahr(new TextDecoder().decode(b).includes("Apache"), "Lizenztext");
});

test("Abgleich: Anhangstext aus einem anderen Gerät wird begrenzt", () => {
  const g = ausGemeinsam({ nachrichten: [{ rolle: "user", text: "F", mit: "x".repeat(20000), anhaenge: [1, 2, 3, 4].map((i) => ({ name: "n".repeat(300), zeichen: "5", boese: i })) }] }, {});
  const m = g.nachrichten[0];
  gleich([m.mit.length, m.anhaenge.length, m.anhaenge[0].name.length, m.anhaenge[0].zeichen, "boese" in m.anhaenge[0]], [8000, 3, 120, 5, false]);
  gleich("mit" in ausGemeinsam({ nachrichten: [{ rolle: "user", text: "F" }] }, {}).nachrichten[0], false);
});


const MK = await (await fetch("meine-ki-beispiel.json", { cache: "no-store" })).json();
test("Meine KI: gleicher Skill-Text wie im Programm, nichts Unbekanntes, Name und Immer an", () => {
  gleich(mk.bereinigen(MK.wahl), MK.bereinigt);
  gleich(mk.skillText(MK.wahl), MK.text);
  wahr(mk.leer({}) && mk.leer({ laenge: "unsinn" }), "leer");
  const s = sk.lesen(mk.alsSkillMd(MK.wahl));
  gleich([s.name, s.beschreibung], [mk.NAME, mk.BESCHREIBUNG]);
  gleich(mk.BAUSTEINE.wofuer.slice(0, 4).map((b) => b.id), ["programmieren", "web", "ki", "linux"]);
});

const ergebnis = { gut: 0, schlecht: 0, fehler: [] };
const liste = document.querySelector("#ergebnis");
for (const f of faelle) {
  const li = document.createElement("li");
  try { await f.fn(); ergebnis.gut++; li.textContent = "gut: " + f.name; }
  catch (e) { ergebnis.schlecht++; ergebnis.fehler.push(`${f.name}: ${e.message}`); li.textContent = "FEHLER: " + f.name + " – " + e.message; li.className = "fehler"; }
  liste.append(li);
}
document.querySelector("#summe").textContent = `${ergebnis.gut} von ${faelle.length} gut`;
window.ERGEBNIS = ergebnis;
