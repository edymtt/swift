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
  set(oneValueArgs "SOURCE_DIR" "BUILD_TARGET")
  set(multiValueArgs "DEPENDS" "TARGET_SDKS" "ADDITIONAL_BUILD_ARGUMENTS")

  cmake_parse_arguments(AOXP "${options}" "${oneValueArgs}"
                                "${multiValueArgs}" ${ARGN} )

  foreach(sdk ${AOXP_TARGET_SDKS})
    set(sdk_name ${SWIFT_SDK_${sdk}_LIB_SUBDIR})
    set(sdk_path ${SWIFT_SDK_${sdk}_PATH})

    set(dependencies swiftCore ${AOXP_DEPENDS})
    list(TRANSFORM dependencies APPEND "-${sdk_name}")

    set(temp_install_subpath "usr/lib/swift")
    ExternalProject_Add(${overlay}Overlay-${sdk_name}
      SOURCE_DIR ${AOXP_SOURCE_DIR}
      INSTALL_DIR  ${SWIFTLIB_DIR}/${sdk_name}
      CONFIGURE_COMMAND ""
      BUILD_ALWAYS 1 # because code is updated by update-checkout
      BUILD_IN_SOURCE TRUE
      BUILD_COMMAND xcodebuild install -target ${AOXP_BUILD_TARGET} -sdk ${sdk_path}
      SYMROOT=<TMP_DIR> OBJROOT=<TMP_DIR>
      DSTROOT=<TMP_DIR>
      SWIFT_EXEC=${SWIFT_NATIVE_SWIFT_TOOLS_PATH}/swiftc
      MACOSX_DEPLOYMENT_TARGET=${SWIFT_DARWIN_DEPLOYMENT_VERSION_OSX} IPHONEOS_DEPLOYMENT_TARGET=${SWIFT_DARWIN_DEPLOYMENT_VERSION_IOS}
      ${AOXP_ADDITIONAL_BUILD_ARGUMENTS}
      # This should have been the install command, but need to fold into the build one
      # to be sure the dependencies works
      COMMAND ditto <TMP_DIR>/${temp_install_subpath} <INSTALL_DIR>
      INSTALL_COMMAND ""
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

    foreach(sdk ${AOT_TARGET_SDKS})
      set(sdk_supported_archs
        ${SWIFT_SDK_${sdk}_ARCHITECTURES}
        ${SWIFT_SDK_${sdk}_MODULE_ARCHITECTURES})
      list(REMOVE_DUPLICATES sdk_supported_archs)
      foreach(arch ${sdk_supported_archs})
        set(sdk_name ${SWIFT_SDK_${sdk}_LIB_SUBDIR})
        set(VARIANT_SUFFIX "${sdk_name}-${arch}")
        add_library(swift${overlay}-${VARIANT_SUFFIX} SHARED IMPORTED GLOBAL)
        set_property(TARGET swift${overlay}-${VARIANT_SUFFIX} PROPERTY IMPORTED_LOCATION ${SWIFTLIB_DIR}/${sdk_name}/libswift${overlay}.dylib)
        add_custom_target(swift${overlay}-swiftmodule-${VARIANT_SUFFIX})
        add_dependencies(swift${overlay}-swiftmodule-${VARIANT_SUFFIX} ${overlay}Overlay-${sdk_name})
        if(SWIFT_ENABLE_MACCATALYST AND sdk STREQUAL "OSX")
          add_custom_target(swift${overlay}-swiftmodule-maccatalyst-${arch})
          add_dependencies(swift${overlay}-swiftmodule-maccatalyst-${arch} ${overlay}Overlay-${sdk_name})
        endif()
        add_dependencies(swift${overlay}-${VARIANT_SUFFIX} ${overlay}Overlay-${sdk_name})
        add_dependencies(swift-stdlib-${VARIANT_SUFFIX} ${overlay}Overlay-${sdk_name})
      endforeach()
    endforeach()
endfunction()
