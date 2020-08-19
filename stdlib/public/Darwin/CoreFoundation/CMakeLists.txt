set(COREFOUNDATION_OVERLAY_BUILT_STANDALONE FALSE)
if("${CMAKE_SOURCE_DIR}" STREQUAL "${CMAKE_CURRENT_SOURCE_DIR}")
    set(COREFOUNDATION_OVERLAY_BUILT_STANDALONE TRUE)
endif()

if(COREFOUNDATION_OVERLAY_BUILT_STANDALONE OR SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD)
    cmake_minimum_required(VERSION 3.15.1)
    project(CoreFoundationOverlay LANGUAGES Swift C)

    option(BUILD_SHARED_LIBS "Build shared libraries by default" YES)
    add_library(swiftCoreFoundation
        CoreFoundation.swift)
    target_compile_options(swiftCoreFoundation
        PRIVATE -module-name CoreFoundation)
    
    target_link_options(swiftCoreFoundation
        PRIVATE -framework CoreFoundation)

    # FIXME: proper generatio of magic symbols
    add_library(magic-symbols-for-install-name STATIC
        "${CMAKE_SOURCE_DIR}/../../../linker-support/magic-symbols-for-install-name.c")
    target_compile_options(magic-symbols-for-install-name
        PRIVATE "-DSWIFT_TARGET_LIBRARY_NAME=swiftCoreFoundation")
    target_link_libraries(swiftCoreFoundation PRIVATE magic-symbols-for-install-name)

    install(TARGETS swiftCoreFoundation DESTINATION usr/lib/swift)
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
