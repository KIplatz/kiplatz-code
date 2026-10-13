// SPDX-License-Identifier: AGPL-3.0-or-later
import { Capacitor } from "@capacitor/core";
import { App } from "@capacitor/app";
import { Haptics, ImpactStyle } from "@capacitor/haptics";
import { Share } from "@capacitor/share";
import { KeychainAccess, SecureStorage } from "@aparajita/capacitor-secure-storage";

let bereit = null;
async function tresorBereit() {

  bereit ??= (async () => {
    await SecureStorage.setKeyPrefix("kiplatz.");
    await SecureStorage.setSynchronize(false);
    await SecureStorage.setDefaultKeychainAccess(KeychainAccess.whenUnlockedThisDeviceOnly);
  })();
  return bereit;
}

export default {
  plattform: Capacitor.getPlatform(),
  tresor: {
    async lesen(name) { await tresorBereit(); return (await SecureStorage.get(name, false)) ?? null; },
    async schreiben(name, wert) { await tresorBereit(); await SecureStorage.set(name, wert, false); },
    async loeschen(name) { await tresorBereit(); await SecureStorage.remove(name); },
  },
  async teilen(text) { await Share.share({ text }); },
  async tippen() { try { await Haptics.impact({ style: ImpactStyle.Light }); } catch { } },
  async version() { return (await App.getInfo()).version; },
  beiLink(fn) { App.addListener("appUrlOpen", (e) => fn(e.url)); },
  beiRueckkehr(fn) { App.addListener("resume", fn); },

  beiZurueck(fn) { App.addListener("backButton", () => { if (!fn()) App.minimizeApp(); }); },
};
