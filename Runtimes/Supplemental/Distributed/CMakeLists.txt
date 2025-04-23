cmake_minimum_required(VERSION 3.29)

set(CMAKE_POSITION_INDEPENDENT_CODE YES)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/../cmake/modules")

if($ENV{BUILD_NUMBER})
  math(EXPR BUILD_NUMBER "$ENV{BUILD_NUMBER} % 65535")
  set(BUILD_NUMBER ".${BUILD_NUMBER}")
endif()
project(SwiftDistributed
  LANGUAGES C CXX Swift 
  VERSION 6.2.0${BUILD_NUMBER})

if(NOT PROJECT_IS_TOP_LEVEL)
  message(SEND_ERROR "Swift Distributed must build as a standalone project")
endif()

set(${PROJECT_NAME}_SWIFTC_SOURCE_DIR
  "${PROJECT_SOURCE_DIR}/../../../"
  CACHE FILEPATH "Path to the root source directory of the Swift compiler")

include(CompilerSettings)

find_package(SwiftCore)

# include(gyb)

configure_file("CMakeConfig.h.in"
  "${PROJECT_BINARY_DIR}/include/swift/Runtime/CMakeConfig.h"
  ESCAPE_QUOTES @ONLY)

add_compile_options(
  $<$<COMPILE_LANGUAGE:Swift>:-v>
  $<$<COMPILE_LANGUAGE:CXX>:-v>
  $<$<COMPILE_LANGUAGE:Swift>:-Rmodule-loading>
  $<$<COMPILE_LANGUAGE:Swift>:-explicit-module-build>
  $<$<COMPILE_LANGUAGE:Swift>:-nostdlibimport>
  $<$<COMPILE_LANGUAGE:Swift>:-parse-stdlib>
  "$<$<COMPILE_LANGUAGE:Swift>:SHELL:-library-level api>"
  $<$<COMPILE_LANGUAGE:Swift>:-enforce-exclusivity=unchecked>
  "$<$<COMPILE_LANGUAGE:Swift>:SHELL:-target-min-inlining-version min>"
  "$<$<COMPILE_LANGUAGE:Swift>:SHELL:-enable-experimental-feature NoncopyableGenerics2>"
  "$<$<COMPILE_LANGUAGE:Swift>:SHELL:-enable-experimental-feature SuppressedAssociatedTypes>"
  "$<$<COMPILE_LANGUAGE:Swift>:SHELL:-enable-experimental-feature SE427NoInferenceOnExtension>"
  "$<$<COMPILE_LANGUAGE:Swift>:SHELL:-enable-experimental-feature NonescapableTypes>"
  "$<$<COMPILE_LANGUAGE:Swift>:SHELL:-enable-experimental-feature LifetimeDependence>"
  "$<$<COMPILE_LANGUAGE:Swift>:SHELL:-enable-experimental-feature MemberImportVisibility>")

add_library(swiftDistributed
  DistributedActor.cpp
  DistributedActor.swift
  DistributedActorSystem.swift
  DistributedAssertions.swift
  DistributedDefaultExecutor.swift
  DistributedMacros.swift
  DistributedMetadata.swift
  LocalTestingDistributedActorSystem.swift)

set_target_properties(swiftDistributed PROPERTIES
  Swift_MODULE_NAME Distributed
  Swift_COMPILATION_MODE wholemodule
  LINKER_LANGUAGE CXX)

target_include_directories(swiftDistributed PRIVATE
  # FIXME: Use of `swift/Runtime/...`, `swift/ABI/...`, and `swift/Demangling/...`
  "${${PROJECT_NAME}_SWIFTC_SOURCE_DIR}/include"
  # FIXME: grant access to `runtime/CMakeConfig.h` which should be available
  # through the swiftRuntime target.
  "${PROJECT_BINARY_DIR}/include"
  # For llvm/support headers
  "${PROJECT_SOURCE_DIR}/include")

target_link_libraries(swiftDistributed PRIVATE
    swiftShims
    swiftCore
    swift_Concurrency)
    # Darwin/Libc/Platform
