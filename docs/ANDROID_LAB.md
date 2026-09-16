# ANDROID LAB — reusable, NOT a hunt artefact

Built during hunt #41. **Survives hunt close** — it carries no session material, no credentials and
no target account. Same reasoning as the bundle carve-out: the instrument outlives the hunt that
motivated it.

## What exists

```
SDK            D:\android-sdk                       13 GB
AVD            tcTest2   Android 14 (API 34), google_apis x86_64, 3 GB RAM     4.8 GB
               C:\Users\krnkk\.android\avd\tcTest2.avd
tools          platform-tools/adb · emulator · build-tools/34.0.0 (aapt2, d8, zipalign, apksigner)
               cmdline-tools/latest/bin/avdmanager
```

## Boot it

```bash
export ANDROID_SDK_ROOT=/d/android-sdk
/d/android-sdk/emulator/emulator -avd tcTest2 -no-snapshot-load -no-boot-anim -no-audio \
  -gpu host -memory 3072 &
```

⚠️ **`-gpu host`, not `swiftshader_indirect`.** SwiftShader segfaults (exit 139) on graphics-heavy
apps. Cost me one full boot cycle in #41.

## What this lab CAN do

- Install and run **arm64-only APKs**: `abilist x86_64,arm64-v8a`, 22 `ndk_translation` libs. Most
  commercial apps ship arm64 only and they run fine.
- `adb root` → full `/data/data` access (this is a **google_apis** image; Play Store images block it).
- Decode any manifest: `aapt2 dump xmltree --file AndroidManifest.xml app.apk`
- Build a PoC APK with **no Gradle**: `javac -bootclasspath android.jar → d8 → aapt2 link → zip →
  zipalign → apksigner` (this produced hunt #41's report #1).
- Enumerate exported components, mine dex strings for Retrofit paths and hostnames.

## What it CANNOT do — learned the hard way

- **Any flow gated by real Play Services.** `com.android.vending` here is the **1.8 stub**. Hunt #41
  died at *"Age verification failed — check your Google Play settings"*, which is unfixable on this
  image.
- **The two requirements are mutually exclusive:** `google_apis` gives `adb root` but no real Play;
  `google_apis_playstore` gives real Play but blocks `adb root`. No single AVD provides both.
  If a future target needs both, check `allowBackup` in its manifest first — `adb backup` on a Play
  image is the only route, and it is unreliable on Android 12+.
- **MITM of a pinned app.** Check `network_security_config` first: if user CAs appear only under
  `<debug-overrides>`, a release build ignores your CA. Then grep the dex for `CertificatePinner`.
  Both true ⇒ MITM needs Frida + root; do not root the researcher's personal phone.

## Gotchas that cost real time

- ⚠️ **MSYS path translation** rewrites device paths. `adb shell uiautomator dump /sdcard/ui.xml`
  silently produces **0 bytes**. Use `export MSYS_NO_PATHCONV=1` and `//sdcard/...`.
  (EVAL_SET I-21 — recurred three times across one hunt.)
- `adb shell` runs as **uid 2000**, which is NOT the attacker model. `am broadcast` prints
  `Broadcast completed: result=0` whether or not a receiver ran ⇒ useless as an oracle. Build a
  zero-permission APK instead (`pb0771`).
- `am force-stop` before a broadcast test destroys the signal — stopped apps receive nothing.
- A stale AVD can point at an uninstalled system image; `emulator -list-avds` still lists it.
