/* the defaults that differ by platform, where neither a setting nor an environment variable says (C and C++).
 * Android (ANDROID-PERF-01): no anisotropic filtering (16x is costly on phone GPUs) and a FIFO swapchain on Vulkan
 * (mailbox is reported to show frames out of order and to flicker on a Mali when the touch overlay changes the
 * system compositor's path). The settings "anisotropy" / "present_mode" and RECOMP_ANISO / RECOMP_PRESENT_MODE
 * still win. */
#ifndef PLATFORM_DEFAULTS_H
#define PLATFORM_DEFAULTS_H

#ifdef __APPLE__
#include <TargetConditionals.h>
#endif
#if defined(__ANDROID__) || (defined(__APPLE__) && TARGET_OS_IPHONE)   /* (iOS: a phone's GPU too; Metal, so no swapchain mailbox to speak of) */
#define DEFAULT_ANISOTROPY 1
#define DEFAULT_VULKAN_MAILBOX 0
#else
#define DEFAULT_ANISOTROPY 16
#define DEFAULT_VULKAN_MAILBOX 1
#endif

#define DEFAULT_STR_(x) #x
#define DEFAULT_STR(x) DEFAULT_STR_(x)
#define DEFAULT_ANISOTROPY_STR DEFAULT_STR(DEFAULT_ANISOTROPY)

#endif
