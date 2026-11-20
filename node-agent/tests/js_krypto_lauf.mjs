// Für test_ende_zu_ende_js_2026_11_19.py: die Verschlüsselung der App (app/www/js/frage-krypto.js) gegen das Programm. Liest einen Auftrag
// als JSON von stdin, schreibt das Ergebnis als JSON nach stdout. Nur zum Vergleich mit dem Programm, nie ausgeliefert.
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { readFileSync } from "node:fs";

const wurzel = resolve(process.argv[2]);
const lade = (p) => import(pathToFileURL(resolve(wurzel, p)).href);
const fk = await lade("app/www/js/frage-krypto.js");
const ak = await lade("app/www/js/abgleich-krypto.js");
const weg = await lade("app/www/js/frage-weg.js");
let roh = "";
for await (const teil of process.stdin) roh += teil;
const a = JSON.parse(roh);
const aus = {};
const fehlerArt = async (f) => { try { await f(); return "kein Fehler"; } catch (e) { return e instanceof fk.KryptoFehler ? "KryptoFehler" : String(e); } };

if (a.schritt === "pruefen") {
  // die Kette, die das Programm gemacht hat, gilt in der App; jede Veränderung fällt durch
  const j = a.jetzt;
  aus.empfaenger = await fk.empfaengerPruefen(a.eintrag, a.wurzeln, { jetzt: j });
  aus.ohne_wurzel = await fk.empfaengerPruefen(a.eintrag, [], { jetzt: j });
  aus.fremde_wurzel = await fk.empfaengerPruefen(a.eintrag, [a.fremd], { jetzt: j });
  aus.abgelaufen = await fk.empfaengerPruefen(a.eintrag, a.wurzeln, { jetzt: a.eintrag.beglaubigung.bis + 1 });
  aus.bis_veraendert = await fk.empfaengerPruefen({ ...a.eintrag, beglaubigung: { ...a.eintrag.beglaubigung, bis: a.eintrag.beglaubigung.bis + 1 } }, a.wurzeln, { jetzt: j });
  aus.antwort_getauscht = await fk.empfaengerPruefen({ ...a.eintrag, antwort: a.fremd }, a.wurzeln, { jetzt: j });
  aus.gesperrt = await fk.empfaengerPruefen(a.eintrag, a.wurzeln, { jetzt: j, gesperrt: new Set([a.kennung]) });
  aus.zu_lang = await fk.empfaengerPruefen(a.zu_lang, a.wurzeln, { jetzt: j });
  aus.kennung = await fk.schluesselKennung(a.eintrag.unterschrift);
  aus.sperrliste = await fk.sperrlistePruefen(a.wurzeln, a.sperrliste);
  aus.sperrliste_veraendert = await fk.sperrlistePruefen(a.wurzeln, { ...a.sperrliste, gesperrt: [] });
  const st = await new fk.Sperrstand(a.wurzeln, a.sperrliste).laden();
  aus.sperrstand = [...st.gesperrt];
  aus.sperrstand_alt = await st.nehmen(a.sperrliste_alt);
  aus.sperrstand_neu = await st.nehmen(a.sperrliste_neu);
  aus.sperrstand_danach = [...st.gesperrt];
  aus.abschnitt = await fk.abschnittPruefen(a.abschnitt.schluessel, a.abschnitt.quelle, a.abschnitt.text, a.abschnitt.sig);
  aus.abschnitt_veraendert = await fk.abschnittPruefen(a.abschnitt.schluessel, a.abschnitt.quelle, a.abschnitt.text + " ", a.abschnitt.sig);
  aus.pruefsummen = await Promise.all(a.texte.map((t) => fk.textPruefsumme(t)));
  // das bisherige Abgleich-Verfahren bleibt Byte für Byte gleich (abgleich-krypto.js wurde für Ende-zu-Ende erweitert)
  const V = JSON.parse(readFileSync(resolve(wurzel, "app/tests/abgleich-vektoren.json"), "utf-8"));
  const k = ak.unb64(V.kontoschluessel);
  aus.abgleich = [
    JSON.stringify(await ak.blockEntschluesseln(k, V.id, V.block)) === JSON.stringify(V.gespraech),
    (await ak.blockVerschluesseln(k, V.id, V.gespraech, ak.unb64(V.iv))) === V.block,
    JSON.stringify(await ak.fachPacken(k, V.geraet_oeffentlich, { wegwerf: V.wegwerf_jwk, iv: ak.unb64(V.iv) })) === JSON.stringify(V.fach),
    Array.from(await ak.fachOeffnen(V.fach, V.geraet_jwk)).join() === Array.from(k).join(),
  ];
} else if (a.schritt === "verschliessen") {
  const v = await fk.frageVerschliessen(a.inhalt, a.empfaenger);
  aus.paket = v.paket;
  aus.behalten = { rueck: v.rueck, frageId: v.frageId, roh: ak.b64(v.roh) };
  aus.zu_viele = await fehlerArt(() => fk.frageVerschliessen(a.inhalt, Object.fromEntries([...Array(65).keys()].map((i) => ["k" + i, Object.values(a.empfaenger)[0]]))));
  aus.kaputter_punkt = await fehlerArt(() => fk.frageVerschliessen(a.inhalt, { x: { art: "p256", punkt: ak.b64(new Uint8Array(65).fill(4)) } }));
} else if (a.schritt === "lesen") {
  const b = a.behalten;
  const e = new fk.Empfang({ rueck: b.rueck, frageId: b.frageId, roh: ak.unb64(b.roh) });
  aus.teile = [];
  for (const n of a.nachrichten) {
    if (!e.istNeu(n)) { aus.teile.push("schon gesehen"); continue; }
    const o = await e.oeffnen(n);
    if (o.art === "antwort") {
      const r = await e.antwortLesen(o, a.sig_schluessel);
      const fremd = await e.antwortLesen(o, a.fremd);
      aus.teile.push({ art: o.art, text: r.text, lieferschein: r.lieferschein, ok: r.ok, fremd_ok: fremd.ok });
    } else aus.teile.push({ art: o.art, daten: o.daten });
  }
  // wiederholt, verändert, für eine andere Frage: alles abgelehnt
  aus.wiederholt = await fehlerArt(() => e.oeffnen(a.nachrichten[0]));
  const e2 = new fk.Empfang({ rueck: b.rueck, frageId: b.frageId, roh: ak.unb64(b.roh) });
  const ct = ak.unb64(a.nachrichten[0].ct); ct[5] ^= 1;
  aus.veraendert = await fehlerArt(() => e2.oeffnen({ ...a.nachrichten[0], ct: ak.b64(ct) }));
  aus.art_getauscht = await fehlerArt(() => e2.oeffnen({ ...a.nachrichten[0], art: "schritt" }));
  const e3 = new fk.Empfang({ rueck: b.rueck, frageId: "0".repeat(32), roh: ak.unb64(b.roh) });
  aus.andere_frage = await fehlerArt(() => e3.oeffnen(a.nachrichten[0]));
}
if (a.schritt === "weg_verschliessen") {
  // der ganze Weg der App: Liste auswerten (Kette, Sperrliste), Kontaktdaten ersetzen, Speicher-Freigabe, verschließen
  const w = await weg.empfaengerAuswerten(a.antwort);
  aus.anzahl = w.anzahl; aus.kennungen = Object.keys(w.empf).sort(); aus.abschnitt = w.abschnitt;
  const { v, body } = await weg.verschliessen(a.nachrichten, w.empf, a.optionen || {});
  aus.body = body;
  aus.behalten = { rueck: v.rueck, frageId: v.frageId, roh: ak.b64(v.roh) };
  aus.vorher = a.nachrichten.map((n) => { const x = weg.vorher(n.content); return [x.krise !== null, x.haus.ok]; });
} else if (a.schritt === "weg_lesen") {
  const b = a.behalten, v = { rueck: b.rueck, frageId: b.frageId, roh: ak.unb64(b.roh) };
  const e = weg.empfang(v);
  aus.teile = await weg.teile(a.r, e);
  const unterschriften = new Set(a.unterschriften || []);
  const l = await weg.lesen(a.r, v, e, { abschnitt: a.abschnitt, unterschriften });
  aus.lesen = l.ok ? { ok: true, text: l.text, lieferschein: l.lieferschein, beweis_antwort: ak.b64(l.beweis.antwort), beweis_sig: l.beweis.sig,
    etikett: l.etikett } : l;
  aus.zweite = await weg.zweitePruefen(a.zweite, e, unterschriften);
  aus.offen = (a.offen || []).map(([r, frei]) => weg.offenAnnehmen(r, frei));
}
if (a.schritt === "besucher") aus.besucher = a.faelle.map(([t, ls, d]) => weg.fuerBesucher(t, ls, d));
process.stdout.write(JSON.stringify(aus));
