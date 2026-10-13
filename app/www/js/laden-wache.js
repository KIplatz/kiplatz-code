// SPDX-License-Identifier: AGPL-3.0-or-later
(function () {
  "use strict";
  var VERSUCHE = "kiplatz.laden-versuche";

  function englisch() {
    var w = "";
    try { w = localStorage.getItem("kiplatz.sprache") || ""; } catch (e) { }
    if (w === "de" || w === "en") return w === "en";
    var l = (navigator.languages && navigator.languages[0]) || navigator.language || "de";
    return !/^de\b/i.test(l);
  }
  function versucheLesen() { try { return Number(sessionStorage.getItem(VERSUCHE) || 0) || 0; } catch (e) { return 0; } }
  function versucheMerken(n) { try { sessionStorage.setItem(VERSUCHE, String(n)); } catch (e) { } }
  function zeigen(text, knopf, beiKlick) {
    var band = document.getElementById("hinweis"), t = document.getElementById("hinweis-text"), k = document.getElementById("btn-hinweis-zu");
    if (!band || !t || !k) return;
    t.textContent = text; k.textContent = knopf; k.onclick = beiKlick; band.hidden = false;
  }
  function neuLaden() { location.reload(); }


  var gemeldet = false;
  window.addEventListener("error", function (e) {
    var el = e.target;
    if (gemeldet || !el || !el.tagName || el.tagName !== "SCRIPT" || el.type !== "module") return;
    gemeldet = true;
    var en = englisch(), n = versucheLesen();
    if (n < 1) {
      versucheMerken(n + 1);
      zeigen(en ? "KIplatz could not load completely. Trying again in a moment …"
                : "KIplatz konnte nicht ganz geladen werden. Gleich geht es noch einmal los …",
             en ? "Reload now" : "Jetzt neu laden", neuLaden);
      setTimeout(neuLaden, 3000);
    } else {
      zeigen(en ? "KIplatz could not load completely. Please check your connection and reload."
                : "KIplatz konnte nicht ganz geladen werden. Prüf bitte deine Verbindung und lade neu.",
             en ? "Reload" : "Neu laden", neuLaden);
    }
  }, true);
})();
