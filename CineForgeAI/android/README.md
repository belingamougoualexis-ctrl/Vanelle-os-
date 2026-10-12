# CineForge AI Studio — Android

Native Android client for the existing LTX-2.5 video generation engine in engine/ltx_generate.py.

## Build

The GitHub Actions workflow at .github/workflows/cineforge-android-build.yml runs Kotlin unit tests and builds an installable debug APK. Open the workflow run and download the artifact named CineForgeAI-Android-APK.

## Generate a real video

1. On a capable Windows PC, install Python 3.11+ and launch start_mobile_engine.bat.
2. Allow Python through the Windows firewall on a private network. Let dependency and model downloads finish. LTX-2.5 is a large model and may need substantial GPU memory or system RAM; CPU rendering can be extremely slow.
3. Keep the console open. Copy the temporary access code it prints.
4. Put the phone and PC on the same trusted Wi-Fi network. Find the PC's local IPv4 address and enter http://PC-IP:8765 in the app, then enter the temporary code.
5. Tap Tester le moteur, describe the shot, then tap Générer le film MP4. A successful result is downloaded into the Android Movies/CineForge AI folder.

The bridge launches the existing inference script, checks that a non-empty MP4 was actually written, and reports engine errors rather than substituting a sample video. Generated work is performed on the connected PC, not on the phone.
