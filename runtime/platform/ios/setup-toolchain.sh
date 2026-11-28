#!/bin/bash
# The iOS toolchain, pinned: the static libraries an iOS build links (runtime/build.py TARGET=ios), built from source
# for arm64-apple-ios$MIN with Xcode's own clang and the iPhoneOS SDK. Runs on a Mac (a GitHub macos runner has
# everything it needs: Xcode, cmake; ninja from Homebrew is used when there). Same pins as the macOS toolchain
# (runtime/platform/macos/setup-toolchain.sh), plus zlib's as the Linux one has it.
#
#   setup-toolchain.sh            into $ATIV_IOS_TOOLCHAIN (default ~/toolchains/ativ-ios)
#
# The layout runtime/build.py expects:
#   SDL3/{include,lib/libSDL3.a}   zlib/{include,lib/libz.a}   spirv-cross/{include,lib/libspirv-cross-*.a}
#   ffmpeg/{include,lib/libavcodec.a,lib/libavutil.a}   (H.264, AAC and MP3 decoders: the game's movies and audio)
set -euo pipefail
SDL=3.4.16
SDL_SHA=7322236cd12090c3eb40b9728be4d49c76f66ad17d04369584d4ecad5cf77c68
SPIRV_CROSS=vulkan-sdk-1.4.363.0
SPIRV_CROSS_SHA=f708982e88b763ef5b0394ed468fc2c3628f68cdab89f2e7a946cd628c04e721
FFMPEG=7.1.1
FFMPEG_SHA=733984395e0dbbe5c046abda2dc49a5544e7e0e1e2366bba849222ae9e3a03b1
ZLIB=1.3.1
ZLIB_SHA=9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23
MIN=15.0
ARCH=arm64
D=${ATIV_IOS_TOOLCHAIN:-$HOME/toolchains/ativ-ios}
SDK=${ATIV_IOS_SDK:-$(xcrun --sdk iphoneos --show-sdk-path)}
[[ -d $SDK ]] || { echo "no iPhoneOS SDK at $SDK"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)   # (runtime/platform/ios: rawdec.c is in ../ffmpeg)
mkdir -p "$D/dl"; cd "$D/dl"
JOBS=$(sysctl -n hw.ncpu)
verify() { local h; h=$(shasum -a 256 "$1" | awk '{print $1}'); [[ $h == "$2" ]] && return; echo "checksum mismatch: $1 (expected $2, got $h)"; rm -f "$1"; exit 1; }
fetch() { [[ -f $2 ]] || { curl -fL --retry 5 --retry-all-errors -o "$2.part" "$1" && verify "$2.part" "$3" && mv -f "$2.part" "$2"; }; }
fetch "https://github.com/libsdl-org/SDL/releases/download/release-$SDL/SDL3-$SDL.tar.gz" "SDL3-$SDL.tar.gz" "$SDL_SHA"
fetch "https://github.com/KhronosGroup/SPIRV-Cross/archive/refs/tags/$SPIRV_CROSS.tar.gz" "SPIRV-Cross-$SPIRV_CROSS.tar.gz" "$SPIRV_CROSS_SHA"
fetch "https://ffmpeg.org/releases/ffmpeg-$FFMPEG.tar.xz" "ffmpeg-$FFMPEG.tar.xz" "$FFMPEG_SHA"
fetch "https://github.com/madler/zlib/releases/download/v$ZLIB/zlib-$ZLIB.tar.gz" "zlib-$ZLIB.tar.gz" "$ZLIB_SHA"
cd "$D"
GEN=; command -v ninja >/dev/null && GEN="-G Ninja"
CM=(-DCMAKE_BUILD_TYPE=Release -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_OSX_ARCHITECTURES=$ARCH
    -DCMAKE_OSX_DEPLOYMENT_TARGET=$MIN -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_POSITION_INDEPENDENT_CODE=ON)
[[ $(cat min 2>/dev/null) == "$MIN" ]] || rm -rf SDL3 zlib spirv-cross ffmpeg   # (built for another minimum iOS: again)

if [[ ! -f SDL3/lib/libSDL3.a ]]; then
  echo "== SDL3 $SDL"
  rm -rf sdl-src sdl-build; mkdir sdl-src; tar xzf "dl/SDL3-$SDL.tar.gz" -C sdl-src --strip-components 1
  cmake -S sdl-src -B sdl-build $GEN "${CM[@]}" -DCMAKE_INSTALL_PREFIX="$D/SDL3" \
    -DSDL_SHARED=OFF -DSDL_STATIC=ON -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF -DSDL_INSTALL_DOCS=OFF > sdl-configure.log 2>&1 || { tail -40 sdl-configure.log; exit 1; }
  cmake --build sdl-build -j"$JOBS" > sdl-build.log 2>&1 && cmake --install sdl-build >> sdl-build.log 2>&1 || { tail -60 sdl-build.log; exit 1; }
fi

if [[ ! -f spirv-cross/lib/libspirv-cross-c.a ]]; then
  echo "== SPIRV-Cross $SPIRV_CROSS"
  rm -rf spirv-src spirv-build; mkdir spirv-src; tar xzf "dl/SPIRV-Cross-$SPIRV_CROSS.tar.gz" -C spirv-src --strip-components 1
  cmake -S spirv-src -B spirv-build $GEN "${CM[@]}" -DCMAKE_INSTALL_PREFIX="$D/spirv-cross" \
    -DSPIRV_CROSS_SHARED=OFF -DSPIRV_CROSS_STATIC=ON -DSPIRV_CROSS_CLI=OFF -DSPIRV_CROSS_ENABLE_TESTS=OFF > spirv-configure.log 2>&1 || { tail -40 spirv-configure.log; exit 1; }
  cmake --build spirv-build -j"$JOBS" > spirv-build.log 2>&1 && cmake --install spirv-build >> spirv-build.log 2>&1 || { tail -60 spirv-build.log; exit 1; }
fi

if [[ ! -f zlib/lib/libz.a ]]; then
  echo "== zlib $ZLIB"
  rm -rf zlib-src; mkdir -p zlib-src zlib/lib zlib/include; tar xzf "dl/zlib-$ZLIB.tar.gz" -C zlib-src --strip-components 1
  ( cd zlib-src
    ZF=(-arch $ARCH -isysroot "$SDK" -miphoneos-version-min=$MIN -O2 -fPIC -DHAVE_UNISTD_H -D_LARGEFILE64_SOURCE=1)
    for f in adler32 crc32 deflate infback inffast inflate inftrees trees zutil compress uncompr gzclose gzlib gzread gzwrite; do
      xcrun --sdk iphoneos clang "${ZF[@]}" -c $f.c -o $f.o; done
    xcrun --sdk iphoneos ar rcs ../zlib/lib/libz.a ./*.o; cp zlib.h zconf.h ../zlib/include/ )
fi

# FFmpeg's decoders, stamped (ffmpeg/.nativ-codecs): the build is made again when they change
FF_CODECS="--enable-decoder=h264 --enable-decoder=aac --enable-decoder=mp3float --enable-parser=h264 --enable-parser=hevc"
[[ "$(cat ffmpeg/.nativ-codecs 2>/dev/null)" == "$FFMPEG $FF_CODECS" ]] || rm -rf ffmpeg
if [[ ! -f ffmpeg/lib/libavcodec.a || ! -f ffmpeg/lib/libnativ_rawdec.a ]]; then
  rm -rf ffmpeg
  echo "== FFmpeg $FFMPEG"
  rm -rf ffmpeg-src; mkdir ffmpeg-src; tar xJf "dl/ffmpeg-$FFMPEG.tar.xz" -C ffmpeg-src --strip-components 1
  F="-arch $ARCH -isysroot $SDK -miphoneos-version-min=$MIN"
  ( cd ffmpeg-src && ./configure --prefix="$D/ffmpeg" --enable-cross-compile --target-os=darwin --arch=$ARCH \
      --cc="$(xcrun --sdk iphoneos -f clang)" --sysroot="$SDK" --extra-cflags="$F" --extra-ldflags="$F" \
      --enable-static --disable-shared --enable-pic --disable-everything --disable-programs --disable-doc --disable-network --disable-autodetect \
      --disable-avdevice --disable-avformat --disable-swscale --disable-swresample --disable-avfilter --disable-debug \
      $FF_CODECS > ../ffmpeg-configure.log 2>&1 \
    && make -j"$JOBS" > ../ffmpeg-build.log 2>&1 && make install >> ../ffmpeg-build.log 2>&1 \
    && xcrun --sdk iphoneos clang $F -O2 -I. -c "$HERE/../ffmpeg/rawdec.c" -o rawdec.o && xcrun --sdk iphoneos ar rcs "$D/ffmpeg/lib/libnativ_rawdec.a" rawdec.o \
    && echo "$FFMPEG $FF_CODECS" > "$D/ffmpeg/.nativ-codecs" ) || { tail -60 ffmpeg-configure.log ffmpeg-build.log 2>/dev/null; exit 1; }
fi

# their licences beside them (SDL, zlib, SPIRV-Cross: permissive; FFmpeg: LGPL 2.1 or later, unmodified source named)
mkdir -p spirv-cross/share/licenses ffmpeg/share/licenses
cp spirv-src/LICENSE spirv-cross/share/licenses/LICENSE 2>/dev/null || true
cp ffmpeg-src/LICENSE.md ffmpeg-src/COPYING.LGPLv2.1 ffmpeg/share/licenses/ 2>/dev/null || true
printf 'FFmpeg %s (LGPL 2.1 or later), unmodified: https://ffmpeg.org/releases/ffmpeg-%s.tar.xz\nbuilt by runtime/platform/ios/setup-toolchain.sh with only the H.264, AAC and MP3 decoders and the H.264 and HEVC parsers enabled, plus libnativ_rawdec.a (runtime/platform/ffmpeg/rawdec.c).\n' "$FFMPEG" "$FFMPEG" > ffmpeg/share/licenses/SOURCE.txt
ok() { [[ -f $1 ]] && echo built || echo MISSING; }
echo "toolchain: $D (iOS $MIN, $ARCH; SDL3 $SDL $(ok SDL3/lib/libSDL3.a); zlib $ZLIB $(ok zlib/lib/libz.a); SPIRV-Cross $SPIRV_CROSS $(ok spirv-cross/lib/libspirv-cross-c.a); FFmpeg $FFMPEG $(ok ffmpeg/lib/libavcodec.a))"
for f in SDL3/lib/libSDL3.a zlib/lib/libz.a spirv-cross/lib/libspirv-cross-c.a ffmpeg/lib/libavcodec.a ffmpeg/lib/libnativ_rawdec.a; do [[ -f $f ]] || exit 1; done
echo "$MIN" > "$D/min"
