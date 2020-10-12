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
  CoreFoundation
  Foundation
  CoreGraphics
  Dispatch
  ObjectiveC
  XCTest
)

if(DEFINED SWIFT_OVERLAY_TARGETS)
  set(overlays_to_build ${SWIFT_OVERLAY_TARGETS})
else()
  set(overlays_to_build ${all_overlays})
endif()

function(addOverlayXcodeProject overlay)
    set(options)
    set(oneValueArgs)
    set(multiValueArgs "DEPENDS" "TARGET_SDKS")

    cmake_parse_arguments(AOXP "${options}" "${oneValueArgs}"
                                  "${multiValueArgs}" ${ARGN} )

    foreach(sdk ${AOXP_TARGET_SDKS})
        set(sdk_name ${SWIFT_SDK_${sdk}_LIB_SUBDIR})


    set(dependencies swiftCore ${AOXP_DEPENDS})
    list(TRANSFORM dependencies APPEND "-${sdk_name}")
    message("Deps: ${dependencies}")
      ExternalProject_Add(${overlay}Overlay-${sdk_name}
        SOURCE_DIR "${CMAKE_SOURCE_DIR}/../foundation-swiftoverlay"
        INSTALL_DIR  ${SWIFTLIB_DIR}/${sdk_name}   # ${CMAKE_CURRENT_BINARY_DIR}/${overlay}
        CONFIGURE_COMMAND ""
        BUILD_COMMAND xcodebuild -target ${overlay}-swiftoverlay -sdk ${sdk_name} SYMROOT=<TMP_DIR> OBJROOT=<TMP_DIR> 
        SWIFT_EXEC=${SWIFT_NATIVE_SWIFT_TOOLS_PATH}/swiftc
        IS_ZIPPERED=NO #IS_ZIPPERED=$<IF:$<BOOL:${SWIFT_ENABLE_MACCATALYST}>,YES,NO>
        MACOSX_DEPLOYMENT_TARGET=${DARWIN_DEPLOYMENT_VERSION_OSX} IPHONEOS_DEPLOYMENT_TARGET=${DARWIN_DEPLOYMENT_VERSION_IOS}
        BUILD_IN_SOURCE TRUE
        INSTALL_COMMAND ditto <TMP_DIR>/Release <INSTALL_DIR>
        BUILD_BYPRODUCTS <INSTALL_DIR>/${overlay}.swiftmodule
        <INSTALL_DIR>/libswift${overlay}.dylib
        EXCLUDE_FROM_ALL TRUE
        DEPENDS ${dependencies})
  add_dependencies(sdk-overlay ${overlay}Overlay-${sdk_name})
    endforeach()
endfunction()

function(addOverlayTargets overlay)
    set(options)
    set(oneValueArgs)
    set(multiValueArgs "TARGET_SDKS")

    cmake_parse_arguments(AOT "${options}" "${oneValueArgs}"
                                  "${multiValueArgs}" ${ARGN} )
    message("Targeted sdks")
    foreach(sdk ${AOT_TARGET_SDKS})
        message(${sdk})
        message("Supported archs")
        foreach(arch ${SWIFT_SDK_${sdk}_ARCHITECTURES})
            message(${arch})
        endforeach()
        message("Supported module archs")
        foreach(arch ${SWIFT_SDK_${sdk}_MODULE_ARCHITECTURES})
            message(${arch})
        endforeach()
    set(sdk_supported_archs
      ${SWIFT_SDK_${sdk}_ARCHITECTURES}
      ${SWIFT_SDK_${sdk}_MODULE_ARCHITECTURES})
    list(REMOVE_DUPLICATES sdk_supported_archs)
    foreach(arch ${sdk_supported_archs})
      set(sdk_name ${SWIFT_SDK_${sdk}_LIB_SUBDIR})
      set(VARIANT_SUFFIX "${sdk_name}-${arch}")
      add_custom_target(swift${overlay}-swiftmodule-${VARIANT_SUFFIX})
      add_library(swift${overlay}-${VARIANT_SUFFIX} SHARED IMPORTED GLOBAL)
      set_property(TARGET swift${overlay}-${VARIANT_SUFFIX} PROPERTY IMPORTED_LOCATION ${SWIFTLIB_DIR}/${sdk_name}/libswift${overlay}.dylib)
      add_dependencies(swift${overlay}-swiftmodule-${VARIANT_SUFFIX} ${overlay}Overlay-${sdk_name})
      add_dependencies(swift${overlay}-${VARIANT_SUFFIX} ${overlay}Overlay-${sdk_name})
      add_dependencies(swift-stdlib-${VARIANT_SUFFIX} ${overlay}Overlay-${sdk_name})
    endforeach()
    endforeach()
endfunction()

message(STATUS "Experimental build for foundation overlay: ${SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD}")
if(SWIFT_ENABLE_EXPERIMENTAL_FOUNDATION_OVERLAY_POST_SPLIT_BUILD)
  include(ExternalProject)

  list(APPEND EXPERIMENTAL_FOUNDATION_SUPPORTED_SDKS "OSX")

  set(build_type "xcode")
  if(${build_type} STREQUAL "xcode")

    # Second idea: Xcode project
    # FIXME: set correct oputput folder
    if("CoreFoundation" IN_LIST overlays_to_build)
        addOverlayXcodeProject(CoreFoundation TARGET_SDKS ${EXPERIMENTAL_FOUNDATION_SUPPORTED_SDKS})

    # Experiment to see if we can avoid touching existing overlays
    addOverlayTargets(CoreFoundation TARGET_SDKS ${EXPERIMENTAL_FOUNDATION_SUPPORTED_SDKS})
endif()

    if("Foundation" IN_LIST overlays_to_build)
    # Experiment to see if we can avoid touching existing overlays
    addOverlayXcodeProject(Foundation DEPENDS CoreFoundationOverlay TARGET_SDKS ${EXPERIMENTAL_FOUNDATION_SUPPORTED_SDKS})
    addOverlayTargets(Foundation TARGET_SDKS ${EXPERIMENTAL_FOUNDATION_SUPPORTED_SDKS})
endif()
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


endif()
message(STATUS "Building overlays: ${overlays_to_build}")
foreach(overlay ${overlays_to_build})
  message(STATUS "INCLUDING OVERLAY: ${overlay}")
      add_subdirectory(${overlay})
    endforeach()
