/*
 * iOS: the two small things the portable runtime asks of the platform.
 *
 *  - ios_documents_dir(): the app's Documents folder (with a trailing slash), the one place the Files app lets a player see
 *    and change anything: session.log, env.txt, fs/ (saves). SDL_GetPrefPath puts its folder in Library/Application Support,
 *    which nothing outside the app can open.
 *  - the compiler-rt availability builtins (__isPlatformVersionAtLeast, ...) for a toolchain that has none (a clang built
 *    without Darwin's runtime): without them any Objective-C file that uses @available fails to link. Xcode's clang has them
 *    (ATIV_IOS_LD=apple defines ATIV_APPLE_TOOLCHAIN: they are left out here, or the link would see them twice).
 */
#import <Foundation/Foundation.h>
#include <stdint.h>
#include <stdio.h>
#include <limits.h>

#ifndef ATIV_APPLE_TOOLCHAIN
static int32_t nativ_version_at_least(uint32_t major, uint32_t minor, uint32_t subminor)
{
    NSOperatingSystemVersion v;
    v.majorVersion = (NSInteger)major;
    v.minorVersion = (NSInteger)minor;
    v.patchVersion = (NSInteger)subminor;
    return [[NSProcessInfo processInfo] isOperatingSystemAtLeastVersion:v] ? 1 : 0;
}

int32_t __isPlatformVersionAtLeast(uint32_t platform, uint32_t major, uint32_t minor, uint32_t subminor)
{
    (void)platform; /* single-platform iOS builds only */
    return nativ_version_at_least(major, minor, subminor);
}

int32_t __isPlatformOrVariantPlatformVersionAtLeast(uint32_t platform, uint32_t major, uint32_t minor,
                                                    uint32_t subminor, uint32_t variant_platform)
{
    (void)platform;
    (void)variant_platform;
    return nativ_version_at_least(major, minor, subminor);
}
#endif

const char *ios_documents_dir(void)
{
    static char buf[PATH_MAX];
    if (buf[0]) return buf;
    @autoreleasepool {
        NSString *p = [NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES) firstObject];
        if (p.length) snprintf(buf, sizeof buf, "%s/", p.UTF8String);
    }
    return buf;
}
