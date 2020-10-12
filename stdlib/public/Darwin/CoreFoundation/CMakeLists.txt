cmake_minimum_required(VERSION 3.4.3)
include("../../../../cmake/modules/StandaloneOverlay.cmake")

set(CORE_FOUNDATION_TARGET_SDKS "")

if(SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD)
    set(CORE_FOUNDATION_TARGET_SDKS ${SWIFT_SDKS})
    variable_watch(CORE_FOUNDATION_TARGET_SDKS)
    list(REMOVE_ITEM CORE_FOUNDATION_TARGET_SDKS "OSX")

    if(NOT CORE_FOUNDATION_TARGET_SDKS)
        message("All the CoreFoundation targets are handled by the new logic, skipping legacy logic")
        return()
    endif()
endif()


add_swift_target_library(swiftCoreFoundation ${SWIFT_SDK_OVERLAY_LIBRARY_BUILD_TYPES} IS_SDK_OVERLAY
  CoreFoundation.swift

  "${SWIFT_SOURCE_DIR}/stdlib/linker-support/magic-symbols-for-install-name.c"

  SWIFT_COMPILE_FLAGS ${SWIFT_RUNTIME_SWIFT_COMPILE_FLAGS} ${SWIFT_STANDARD_LIBRARY_SWIFT_FLAGS}
  LINK_FLAGS "${SWIFT_RUNTIME_SWIFT_LINK_FLAGS}"
  SWIFT_MODULE_DEPENDS_OSX Darwin Dispatch ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_IOS Darwin Dispatch ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_TVOS Darwin Dispatch ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_WATCHOS Darwin Dispatch ObjectiveC # auto-updated
  TARGET_SDKS ${CORE_FOUNDATION_TARGET_SDKS}
  FRAMEWORK_DEPENDS CoreFoundation
  INSTALL_IN_COMPONENT sdk-overlay
)
