# All libraries in this directory tree are overlays that depend on Darwin SDK.

set(SWIFT_SDK_OVERLAY_LIBRARY_BUILD_TYPES)
if(SWIFT_BUILD_DYNAMIC_SDK_OVERLAY)
  list(APPEND SWIFT_SDK_OVERLAY_LIBRARY_BUILD_TYPES SHARED)
endif()
if(SWIFT_BUILD_STATIC_SDK_OVERLAY)
  list_intersect("${SWIFT_APPLE_PLATFORMS}" "${SWIFT_SDKS}" building_darwin_sdks)
  if(building_darwin_sdks)
    message(SEND_ERROR "cannot build static standard library for Darwin SDKs")
  else()
    list(APPEND SWIFT_SDK_OVERLAY_LIBRARY_BUILD_TYPES STATIC)
  endif()
endif()

set(all_overlays
  CoreGraphics
  Dispatch
  ObjectiveC
  XCTest
)

if(NOT SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD)
  list(APPEND all_overlays
    CoreFoundation
    Foundation
  )
endif()

if(DEFINED SWIFT_OVERLAY_TARGETS)
  set(overlays_to_build ${SWIFT_OVERLAY_TARGETS})
else()
  set(overlays_to_build ${all_overlays})
endif()

message(STATUS "Experimental build for foundation overlay: ${SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD}")
if(SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD)
  #add CoreFoundation in a different way
  include(ExternalProject)

  set(build_type "xcode")


  if(${build_type} STREQUAL "xcode")
    # Second idea: Xcode project
    # FIXME: set correct oputput folder
    ExternalProject_Add(CoreFoundationOverlay
      SOURCE_DIR "${CMAKE_SOURCE_DIR}/../foundation-swiftoverlay"
      INSTALL_DIR  ${SWIFTLIB_DIR}/macosx   # ${CMAKE_CURRENT_BINARY_DIR}/CoreFoundation
      CONFIGURE_COMMAND ""
      BUILD_COMMAND xcodebuild -target CoreFoundation-swiftoverlay -sdk macosx SYMROOT=<TMP_DIR> OBJROOT=<TMP_DIR> 
      SWIFT_EXEC=${SWIFT_NATIVE_SWIFT_TOOLS_PATH}/swiftc IS_ZIPPERED=$<IF:$<BOOL:${SWIFT_ENABLE_MACCATALYST}>,YES,NO>
      BUILD_IN_SOURCE TRUE
      INSTALL_COMMAND ditto <TMP_DIR>/Release <INSTALL_DIR>
      BUILD_BYPRODUCTS <INSTALL_DIR>/CoreFoundation.swiftmodule
      <INSTALL_DIR>/libswiftCoreFoundation.dylib
      EXCLUDE_FROM_ALL TRUE)

    # Experiment to see if we can avoid touching existing overlays
    add_custom_target(swiftCoreFoundation-swiftmodule-macosx-x86_64)
    add_custom_target(swiftCoreFoundation-swiftmodule-macosx-arm64)
    add_library(swiftCoreFoundation-macosx-arm64 SHARED IMPORTED )
    add_library(swiftCoreFoundation-macosx-x86_64 SHARED IMPORTED )
    set_property(TARGET swiftCoreFoundation-macosx-arm64 PROPERTY IMPORTED_LOCATION ${SWIFTLIB_DIR}/macosx/libswiftCoreFoundation.dylib)
    set_property(TARGET swiftCoreFoundation-macosx-x86_64 PROPERTY IMPORTED_LOCATION ${SWIFTLIB_DIR}/macosx/libswiftCoreFoundation.dylib)
    add_dependencies(swiftCoreFoundation-swiftmodule-macosx-x86_64 CoreFoundationOverlay)
    add_dependencies(swiftCoreFoundation-swiftmodule-macosx-arm64 CoreFoundationOverlay)
    add_dependencies(swiftCoreFoundation-macosx-arm64 CoreFoundationOverlay)
    add_dependencies(swiftCoreFoundation-macosx-x86_64 CoreFoundationOverlay)
    add_dependencies(swift-stdlib-macosx-x86_64 CoreFoundationOverlay)

    ExternalProject_Add(FoundationOverlay
      SOURCE_DIR "${CMAKE_SOURCE_DIR}/../foundation-swiftoverlay"
      INSTALL_DIR  ${SWIFTLIB_DIR}/macosx   # ${CMAKE_CURRENT_BINARY_DIR}/CoreFoundation
      CONFIGURE_COMMAND ""
      BUILD_COMMAND xcodebuild -target Foundation-swiftoverlay -sdk macosx SYMROOT=<TMP_DIR> OBJROOT=<TMP_DIR> 
      SWIFT_EXEC=${SWIFT_NATIVE_SWIFT_TOOLS_PATH}/swiftc
      IS_ZIPPERED=$<IF:$<BOOL:${SWIFT_ENABLE_MACCATALYST}>,YES,NO>
      BUILD_IN_SOURCE TRUE
      INSTALL_COMMAND ditto <TMP_DIR>/Release <INSTALL_DIR>
      BUILD_BYPRODUCTS <INSTALL_DIR>/Foundation.swiftmodule
      <INSTALL_DIR>/libswiftFoundation.dylib
      EXCLUDE_FROM_ALL TRUE
      DEPENDS CoreFoundationOverlay)

    # Experiment to see if we can avoid touching existing overlays
    add_custom_target(swiftFoundation-swiftmodule-macosx-x86_64)
    add_custom_target(swiftFoundation-swiftmodule-macosx-arm64)
    add_library(swiftFoundation-macosx-arm64 SHARED IMPORTED GLOBAL )
    add_library(swiftFoundation-macosx-x86_64 SHARED IMPORTED GLOBAL )
    set_property(TARGET swiftFoundation-macosx-arm64 PROPERTY IMPORTED_LOCATION ${SWIFTLIB_DIR}/macosx/libswiftFoundation.dylib)
    set_property(TARGET swiftFoundation-macosx-x86_64 PROPERTY IMPORTED_LOCATION ${SWIFTLIB_DIR}/macosx/libswiftFoundation.dylib)
    add_dependencies(swiftFoundation-swiftmodule-macosx-x86_64 FoundationOverlay)
    add_dependencies(swiftFoundation-swiftmodule-macosx-arm64 FoundationOverlay)
    add_dependencies(swiftFoundation-macosx-arm64 FoundationOverlay)
    add_dependencies(swiftFoundation-macosx-x86_64 FoundationOverlay)
    add_dependencies(swift-stdlib-macosx-x86_64 FoundationOverlay)
  else()

  # First idea: CMake project
  #FIXME likely try with newer CMake
  #FIXME match flags
  ExternalProject_Add(CoreFoundationOverlay
      SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/CoreFoundation"
      INSTALL_DIR ${CMAKE_CURRENT_BINARY_DIR}
    CMAKE_ARGS -DCMAKE_INSTALL_PREFIX:STRING=<INSTALL_DIR>
-DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
                          -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
                          -DCMAKE_CXX_COMPILER=${CMAKE_CXX_COMPILER}
                          -DCMAKE_CXX_FLAGS=${CMAKE_CXX_FLAGS}
                          -DCMAKE_MAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}
                          -DCMAKE_Swift_COMPILER="${SWIFT_NATIVE_SWIFT_TOOLS_PATH}/swiftc"
                          )
                  endif()


  add_dependencies(sdk-overlay CoreFoundationOverlay)
endif()
message(STATUS "Building overlays: ${overlays_to_build}")
foreach(overlay ${overlays_to_build})
  message(STATUS "INCLUDING OVERLAY: ${overlay}")
  add_subdirectory(${overlay})
endforeach()
