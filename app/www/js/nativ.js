// SPDX-License-Identifier: AGPL-3.0-or-later
export let nativ = null;
if (globalThis.Capacitor?.isNativePlatform?.()) {
  try { nativ = (await import("./nativ-gebaut.js")).default; } catch { nativ = null; }
}
