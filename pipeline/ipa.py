"""A built game as an unsigned .ipa for the player's own iPhone or iPad: vitarecomp export-ios.

The ipa holds the compiled game (runtime/build.py TARGET=ios: an arm64 executable, SDL3 linked in) and its images and files
from the player's copy: it is for their own device, never for anyone else. It is unsigned: Sideloadly or AltStore with a free
Apple ID (the app works for seven days at a time, then is signed again), Xcode with a paid team, or TrollStore install it.
There is no JIT: the game's ARM code was translated to C ahead of time, so a stock device runs it.

Bundle layout (what runtime/core/main.c's ios_bootstrap reads):

  Payload/<Name>.app/<exe>             the game's host program
  Payload/<Name>.app/Info.plist        landscape, file sharing on (the Files app reaches Documents/Nativ: session.log, env.txt, saves)
  Payload/<Name>.app/Icon-*.png        the game's own icon0.png at every size iOS asks for (runtime/platform/ios/icons.py)
  Payload/<Name>.app/data/launch.txt   the game's arguments and environment, as `vitarecomp run` gives them (apk.launch_text's
                                       format; $FILES = this data/ folder, $DATA = the app's Documents/Nativ)
  Payload/<Name>.app/data/*.img        the game's images (and its firmware modules')
  Payload/<Name>.app/data/shaders.txt  the pack's shader recipes
  Payload/<Name>.app/data/app0/        the game's files

The pieces, testable without a game (dev/test_export_ios.py):

  bundle_id()     local.nativ.<title id>: one app per game
  info_plist()    the Info.plist
  build_ipa()     the bundle written as a zip with the unix permissions iOS expects (the executable 0755, the rest 0644)
"""
import os
import re
import sys
import zipfile
from xml.sax.saxutils import escape

NOTICE = ("This ipa holds the compiled game and the game's files from YOUR copy: it is private, for your own device. "
          "Don't share or upload it.")
MIN_IOS = "15.0"
ICON_FILES = ["Icon-20", "Icon-29", "Icon-40", "Icon-60"]   # (icons.py's names; iOS picks the file for the screen)


def bundle_id(title):
    """local.nativ.<title id in lower case>; ValueError for anything but a title id"""
    if not re.fullmatch(r"[A-Z]{4}\d{5}", title or ""): raise ValueError(f"not a title id: {title!r}")
    return "local.nativ." + title.lower()


def app_name(name, title):
    """the bundle's folder name: the game's name with letters and digits only, else its title id"""
    return re.sub(r"[^A-Za-z0-9]", "", name or "") or title


def info_plist(bundle, exe, name, display, version="1.0"):
    icons = "".join(f"\t\t<string>{n}</string>\n" for n in ICON_FILES)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>CFBundleDevelopmentRegion</key><string>en</string>
\t<key>CFBundleExecutable</key><string>{escape(exe)}</string>
\t<key>CFBundleIdentifier</key><string>{escape(bundle)}</string>
\t<key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
\t<key>CFBundleName</key><string>{escape(name)}</string>
\t<key>CFBundleDisplayName</key><string>{escape(display)}</string>
\t<key>CFBundlePackageType</key><string>APPL</string>
\t<key>CFBundleShortVersionString</key><string>{escape(version)}</string>
\t<key>CFBundleVersion</key><string>1</string>
\t<key>CFBundleIconFiles</key>
\t<array>
{icons}\t</array>
\t<key>CFBundleIcons</key>
\t<dict>
\t\t<key>CFBundlePrimaryIcon</key>
\t\t<dict>
\t\t\t<key>CFBundleIconFiles</key>
\t\t<array>
{icons}\t\t\t</array>
\t\t</dict>
\t</dict>
\t<key>CFBundleSupportedPlatforms</key><array><string>iPhoneOS</string></array>
\t<key>LSRequiresIPhoneOS</key><true/>
\t<key>MinimumOSVersion</key><string>{MIN_IOS}</string>
\t<key>UIDeviceFamily</key><array><integer>1</integer><integer>2</integer></array>
\t<key>UIRequiredDeviceCapabilities</key><array><string>arm64</string></array>
\t<key>UILaunchScreen</key><dict/>
\t<key>UIStatusBarHidden</key><true/>
\t<key>UIViewControllerBasedStatusBarAppearance</key><false/>
\t<key>UISupportedInterfaceOrientations</key>
\t<array>
\t\t<string>UIInterfaceOrientationLandscapeLeft</string>
\t\t<string>UIInterfaceOrientationLandscapeRight</string>
\t</array>
\t<key>UIFileSharingEnabled</key><true/>
\t<key>LSSupportsOpeningDocumentsInPlace</key><true/>
\t<key>CADisableMinimumFrameDurationOnPhone</key><true/>
\t<key>UIRequiresFullScreen</key><true/>
</dict>
</plist>
"""


def build_ipa(out, name, plist, exe_path, exe_name, data_files, icon_png, app0=None):
    """write the ipa. data_files: (source path, name under data/); app0: the game's folder, copied to data/app0; icon_png: the
    game's icon0.png (or any square PNG). Everything is deflated except nothing: the game's files are mostly compressed
    already, and a stored zip of several GB is no faster to sideload"""
    import tempfile
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime", "platform", "ios"))
    import icons   # (the icon set from one image: no browser, no drawing tool)
    root = "Payload/" + name + ".app/"
    with tempfile.TemporaryDirectory(prefix="nativ-ipa-") as tmp:
        icons.from_image(icon_png, tmp)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        part = out + ".part"
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
            def put(src, rel, mode=0o100644):
                info = zipfile.ZipInfo.from_file(src, root + rel)
                info.external_attr = mode << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(src, "rb") as f, z.open(info, "w", force_zip64=True) as d:
                    while True:
                        b = f.read(1 << 20)
                        if not b: break
                        d.write(b)
            def put_text(text, rel):
                info = zipfile.ZipInfo(root + rel); info.external_attr = 0o100644 << 16; info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, text)
            put_text(plist, "Info.plist")
            put(exe_path, exe_name, 0o100755)
            for f in sorted(os.listdir(tmp)):
                if f.endswith(".png"): put(os.path.join(tmp, f), f)
            for src, rel in data_files: put(src, "data/" + rel)
            if app0:
                for d, dirs, files in os.walk(app0):
                    dirs.sort()
                    for fn in sorted(files):
                        p = os.path.join(d, fn)
                        put(p, "data/app0/" + os.path.relpath(p, app0).replace(os.sep, "/"))
        os.replace(part, out)
    return out
