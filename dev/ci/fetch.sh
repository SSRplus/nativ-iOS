#!/usr/bin/env bash
# Download one direct link into a folder and unpack it there: dev/ci/fetch.sh <url> <folder>
#
# What the link serves is told by its first bytes, not its name (a download script's file name is often just
# "download.php"): a zip is unpacked; a 7z or rar is unpacked when 7z is installed; a PKG or a PUP is kept as it is;
# anything else (an HTML page: the link expired, or wants a browser's cookies) stops here with the start of what came
# back. The link itself is never printed -- these links carry a key. Archives inside the unpacked folder are
# opened later, by find_inputs.py.
set -euo pipefail
url=${1:?usage: fetch.sh <url> <folder>}; dest=${2:?usage: fetch.sh <url> <folder>}
mkdir -p "$dest"; part="$dest/.download.part"
echo "downloading ..."
curl -fsSL --retry 5 --retry-all-errors --connect-timeout 30 --speed-limit 1024 --speed-time 120 \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15" \
  -o "$part" -D "$part.hdr" "$url" || true
[[ -s $part ]] || { echo "error: nothing came back from the link (expired or refused?)"; sed -n '1,12p' "$part.hdr" 2>/dev/null | tr -d '\r'; exit 1; }
size=$(wc -c < "$part" | tr -d ' ')
magic=$(head -c 4 "$part" | od -An -tx1 | tr -d ' \n')
# a name for the kept file, from the server's Content-Disposition when it sends one
name=$(grep -i '^content-disposition:' "$part.hdr" 2>/dev/null | tail -1 | sed -n 's/.*filename\*\?=\(UTF-8'"''"'\)\?"\?\([^";]*\).*/\2/p' | tr -d '\r' | head -1 || true)
echo "got $size bytes (starts $magic)${name:+, named: $name}"
case $magic in
  504b0304|504b0506)
    mv "$part" "$dest/download.zip"
    unzip -q -o "$dest/download.zip" -d "$dest" || { echo "error: the zip did not unpack"; exit 1; }
    rm -f "$dest/download.zip" ;;
  377abcaf|52617221)
    command -v 7zz >/dev/null || command -v 7z >/dev/null || brew install sevenzip >/dev/null 2>&1 || brew install p7zip >/dev/null 2>&1 || true
    x=$(command -v 7zz || command -v 7z) || { echo "error: no 7z to unpack it"; exit 1; }
    ext=7z; [[ $magic == 52617221 ]] && ext=rar
    mv "$part" "$dest/download.$ext"; "$x" x -y -o"$dest" "$dest/download.$ext" >/dev/null; rm -f "$dest/download.$ext" ;;
  7f504b47) mv "$part" "$dest/${name:-download.pkg}" ;;     # a PKG
  53434555) mv "$part" "$dest/${name:-PSP2UPDAT.PUP}" ;;    # SCEUF: a firmware update file
  *)
    echo "error: not an archive, a PKG or a firmware file. The start of it:"; head -c 300 "$part" | tr -c '[:print:]\n' '.'; echo
    exit 1 ;;
esac
rm -f "$part" "$part.hdr"
echo "unpacked into $dest: $(find "$dest" -type f | wc -l | tr -d ' ') files, $(du -sh "$dest" | cut -f1)"
