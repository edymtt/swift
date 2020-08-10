cmake_minimum_required(VERSION 3.4.3)
include("../../../../cmake/modules/StandaloneOverlay.cmake")

# We cannot use a generator expression since, given it is not evaluated during command
# interpretation, it will cause the overlay to depend on an invalid dependency
if(NOT SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD)
  set(CORE_FOUNDATION_IF_BUILT CoreFoundation)
endif()

add_swift_target_library(swiftCoreGraphics ${SWIFT_SDK_OVERLAY_LIBRARY_BUILD_TYPES} IS_SDK_OVERLAY
  CoreGraphics.swift
  Private.swift

  "${SWIFT_SOURCE_DIR}/stdlib/linker-support/magic-symbols-for-install-name.c"

  GYB_SOURCES
    CGFloat.swift.gyb

  SWIFT_COMPILE_FLAGS ${SWIFT_RUNTIME_SWIFT_COMPILE_FLAGS} ${SWIFT_STANDARD_LIBRARY_SWIFT_FLAGS}
  LINK_FLAGS "${SWIFT_RUNTIME_SWIFT_LINK_FLAGS}"
  SWIFT_MODULE_DEPENDS_OSX Darwin Dispatch CoreFoundation ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_IOS Darwin Dispatch ${CORE_FOUNDATION_IF_BUILT} ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_TVOS Darwin Dispatch ${CORE_FOUNDATION_IF_BUILT} ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_WATCHOS Darwin Dispatch ${CORE_FOUNDATION_IF_BUILT} ObjectiveC # auto-updated
  FRAMEWORK_DEPENDS CoreGraphics

  DEPLOYMENT_VERSION_OSX ${SWIFTLIB_DEPLOYMENT_VERSION_COREGRAPHICS_OSX}
  DEPLOYMENT_VERSION_IOS ${SWIFTLIB_DEPLOYMENT_VERSION_COREGRAPHICS_IOS}
  DEPLOYMENT_VERSION_TVOS ${SWIFTLIB_DEPLOYMENT_VERSION_COREGRAPHICS_TVOS}
  DEPLOYMENT_VERSION_WATCHOS ${SWIFTLIB_DEPLOYMENT_VERSION_COREGRAPHICS_WATCHOS}
  INSTALL_IN_COMPONENT sdk-overlay
)
