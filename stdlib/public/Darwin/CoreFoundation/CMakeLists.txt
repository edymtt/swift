variable_watch(COREFOUNDATION_OVERLAY_BUILT_STANDALONE)
set(COREFOUNDATION_OVERLAY_BUILT_STANDALONE FALSE)
if("${CMAKE_SOURCE_DIR}" STREQUAL "${CMAKE_CURRENT_SOURCE_DIR}")
    set(COREFOUNDATION_OVERLAY_BUILT_STANDALONE TRUE)
endif()

if(COREFOUNDATION_OVERLAY_BUILT_STANDALONE OR SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD)
    cmake_minimum_required(VERSION 3.12.4)
else()

cmake_minimum_required(VERSION 3.4.3)
include("../../../../cmake/modules/StandaloneOverlay.cmake")

add_swift_target_library(swiftCoreFoundation ${SWIFT_SDK_OVERLAY_LIBRARY_BUILD_TYPES} IS_SDK_OVERLAY
  CoreFoundation.swift

  "${SWIFT_SOURCE_DIR}/stdlib/linker-support/magic-symbols-for-install-name.c"

  SWIFT_COMPILE_FLAGS ${SWIFT_RUNTIME_SWIFT_COMPILE_FLAGS} ${SWIFT_STANDARD_LIBRARY_SWIFT_FLAGS}
  LINK_FLAGS "${SWIFT_RUNTIME_SWIFT_LINK_FLAGS}"
  SWIFT_MODULE_DEPENDS_OSX Darwin Dispatch ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_IOS Darwin Dispatch ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_TVOS Darwin Dispatch ObjectiveC # auto-updated
  SWIFT_MODULE_DEPENDS_WATCHOS Darwin Dispatch ObjectiveC # auto-updated
  FRAMEWORK_DEPENDS CoreFoundation
  INSTALL_IN_COMPONENT sdk-overlay
)
endif()
