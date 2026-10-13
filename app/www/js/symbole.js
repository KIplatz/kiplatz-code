// SPDX-License-Identifier: AGPL-3.0-or-later
const PFADE = {
  leiste: '<path d="M4 6h16M4 12h16M4 18h10"/>',
  zu: '<path d="M6 6l12 12M18 6L6 18"/>',
  neu: '<path d="M12 5v14M5 12h14"/>',
  suche: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/>',
  einstellungen: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
  mehr: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
  senden: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  stopp: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
  zurueck: '<path d="M15 5l-7 7 7 7"/>',
  kopieren: '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>',
  teilen: '<path d="M12 15V4M8 8l4-4 4 4"/><path d="M6 12v6.5A1.5 1.5 0 0 0 7.5 20h9a1.5 1.5 0 0 0 1.5-1.5V12"/>',
  gut: '<path d="M7 11v8H4.5v-8zM7 11l4-7a2 2 0 0 1 2.5 2.3L13 10h5.2a2 2 0 0 1 2 2.4l-1.3 5.8a2 2 0 0 1-2 1.8H7"/>',
  schlecht: '<path d="M7 13V5H4.5v8zM7 13l4 7a2 2 0 0 0 2.5-2.3L13 14h5.2a2 2 0 0 0 2-2.4l-1.3-5.8a2 2 0 0 0-2-1.8H7"/>',
  nochmal: '<path d="M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3"/><path d="M18 3v4h-4M6 21v-4h4"/>',
  nadel: '<path d="M9 4h6l-1 6 3 3H7l3-3zM12 13v7"/>',
  schreiben: '<path d="M12 4H6.5A2.5 2.5 0 0 0 4 6.5v11A2.5 2.5 0 0 0 6.5 20h11a2.5 2.5 0 0 0 2.5-2.5V12"/><path d="M17.5 3.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4z"/>',
  stift: '<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4z"/>',
  meineki: '<path d="M12 3.5l1.9 4.6 4.6 1.9-4.6 1.9L12 16.5l-1.9-4.6L5.5 10l4.6-1.9z"/><path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
  bestenliste: '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8.5 20h7M10 17h4"/>',
  platzl: '<path d="M4 5.5h11a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5H9l-4 3v-3H4A1.5 1.5 0 0 1 2.5 13V7A1.5 1.5 0 0 1 4 5.5z"/><path d="M16.5 9H20a1.5 1.5 0 0 1 1.5 1.5v6A1.5 1.5 0 0 1 20 18h-1v3l-4-3h-3.5"/>',
  melden: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  ordner: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  loeschen: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12.5A1.5 1.5 0 0 0 8.5 21h7a1.5 1.5 0 0 0 1.5-1.5L18 7M9 7V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V7"/>',

  mikro: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  runter: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  anhang: '<path d="M20 11.5l-7.8 7.8a5 5 0 0 1-7-7l7.8-7.8a3.3 3.3 0 0 1 4.7 4.7l-7.8 7.8a1.7 1.7 0 0 1-2.4-2.4L14.7 7.4"/>',
  datei: '<path d="M6 3.5h8l4.5 4.5v12A1.5 1.5 0 0 1 17 21.5H6A1.5 1.5 0 0 1 4.5 20V5A1.5 1.5 0 0 1 6 3.5z"/><path d="M14 3.5V8h4.5M8 13h8M8 17h6"/>',
  foto: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.8"/><path d="M21 16l-5.5-5.5L7 19"/>',

  pruefen: '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/>',

  geraet: '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M11 18h2"/>',
  pc: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  aussehen: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5V5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8"/>',
  schloss: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
  abgleich: '<path d="M4 8h13M14 5l3 3-3 3M20 16H7M10 13l-3 3 3 3"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
  antwortmelden: '<path d="M4 5h16v11H9l-5 4z"/><path d="M12 8v3.5M12 13.5h.01"/>',

  haken: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  mitglied: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c1-4 4-6 7-6s6 2 7 6"/>',
};

export function symbol(name) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("class", "ic");
  s.setAttribute("aria-hidden", "true");
  s.innerHTML = PFADE[name] || "";
  return s;
}


export function symboleEinsetzen(wurzel = document) {
  for (const el of wurzel.querySelectorAll("[data-icon]")) {
    if (!el.querySelector("svg.ic")) el.prepend(symbol(el.dataset.icon));
  }
}
