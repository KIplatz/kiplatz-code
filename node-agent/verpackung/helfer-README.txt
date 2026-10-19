KIplatz Helper – Read me
========================

With the helper, your Linux computer or your Mac works for the KIplatz
community. It has no window. It runs quietly in the background, at low
priority, and only as much as you allow.

It is available for ordinary PCs (x64) and for Macs with Apple silicon
(M1 and newer). With its own graphics card and 16 GB of memory your
device answers other members' questions; on a Mac the Apple chip counts
as graphics. Otherwise it does background work for the shared knowledge.


Setting it up
-------------
Everything happens in the terminal. You need your KIplatz account, just
like in the app (Google, GitHub or an email code).

Linux:

  mkdir -p ~/.local/share/kiplatz
  tar -xzf KIplatz-Helfer-linux-x64.tar.gz -C ~/.local/share/kiplatz
  ~/.local/share/kiplatz/kiplatz-helfer/kiplatz-helfer einrichten

Mac:

  mkdir -p ~/Library/kiplatz
  tar -xzf KIplatz-Helfer-macos-arm64.tar.gz -C ~/Library/kiplatz
  ~/Library/kiplatz/kiplatz-helfer/kiplatz-helfer einrichten

On a Mac, download the package in the terminal with curl, so the Mac
does not treat it as a file from the browser.

Check that the file is unchanged (before unpacking):

  sha256sum -c KIplatz-Helfer-linux-x64.tar.gz.sha256        (Linux)
  shasum -a 256 -c KIplatz-Helfer-macos-arm64.tar.gz.sha256   (Mac)

During setup the helper shows an address. Open it in a browser, on your
phone is fine too, sign in with your account and confirm "Connect a new
PC?". Then the helper joins the community, sets its limits and from
then on starts by itself every time you log in. It registers as a
service for your user only (Linux: systemd, Mac: launchd). It does not
need administrator rights.

On its first start it fetches the AI runtime and a suitable AI model
from our server, 2 to 10 GB depending on the device. Every file is
checked against a checksum built into the program.


What you can set
----------------
The commands are in the helper's folder (see below).

  kiplatz-helfer status                     signed in, running, log
  kiplatz-helfer grenzen --cpu 25 --ram 4   at most 25 % of the processor
                                            and 4 GB of memory
  kiplatz-helfer aus                        stop, autostart off
  kiplatz-helfer an                         switch it on again

Without settings it takes what suits your device: a quarter of the
memory and 25 to 50 % of the processor.

Linux machines without a screen: so that the helper also runs when
nobody is logged in, run "loginctl enable-linger" once.


What the helper does and does not do
------------------------------------
- Questions from the community arrive without names.
- It opens none of your files, no camera, no microphone.
- While someone is working at your device (on Linux: logged in there),
  its background work pauses. It keeps answering questions.
- Its keys are kept in your system's keychain. Where there is none
  (Linux without a screen), in a file that only you can read.
- Updates arrive by themselves and are digitally signed. An update
  without a valid signature is rejected.


Where the files are
-------------------
Linux: program in ~/.local/share/kiplatz/kiplatz-helfer,
       data and models in ~/.local/share/kiplatz/daten
Mac:   program in ~/Library/kiplatz/kiplatz-helfer,
       data and models in ~/Library/Application Support/KIplatz/Daten


Removing it
-----------
  kiplatz-helfer aus

Then delete the two folders above. To take your device out of the
community, remove it from the list of your devices, in the app or in the
program.


Help
----
Website:                 https://kiplatz.at/en/
Questions:               support@kiplatz.at
Privacy (in German):     https://kiplatz.at/datenschutz/
