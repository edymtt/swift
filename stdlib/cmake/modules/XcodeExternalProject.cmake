#===--- XcodeExternalProject.cmake - Building Xcode projects from CMake --===#
#
# This source file is part of the Swift.org open source project
#
# Copyright (c) 2014 - 2020 Apple Inc. and the Swift project authors
# Licensed under Apache License v2.0 with Runtime Library Exception
#
# See https://swift.org/LICENSE.txt for license information
# See https://swift.org/CONTRIBUTORS.txt for the list of Swift project authors
#
#===----------------------------------------------------------------------===#

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
