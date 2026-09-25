# swift_build_support/products/llvm.py --------------------------*- python -*-
#
# This source file is part of the Swift.org open source project
#
# Copyright (c) 2014 - 2017 Apple Inc. and the Swift project authors
# Licensed under Apache License v2.0 with Runtime Library Exception
#
# See https://swift.org/LICENSE.txt for license information
# See https://swift.org/CONTRIBUTORS.txt for the list of Swift project authors
#
# ----------------------------------------------------------------------------

import os
import shutil
from platform import system

from . import cmake_product
from . import cmark
from . import earlyswiftdriver
from . import libcxx
from . import staticswiftlinux
from .. import shell
from .. import targets
from ..cmake import CMakeOptions
from ..host_specific_configuration \
    import HostSpecificConfiguration


class LLVMCombined(cmake_product.CMakeProduct):

    def __init__(self, args, toolchain, source_dir, build_dir):
        cmake_product.CMakeProduct.__init__(self, args, toolchain, source_dir,
                                            build_dir)

        # Add the cmake option for enabling or disabling assertions.
        self.cmake_options.define(
            'LLVM_ENABLE_ASSERTIONS:BOOL', args.llvm_assertions)

        # Add the cmake option for LLVM_TARGETS_TO_BUILD.
        self.cmake_options.define(
            'LLVM_TARGETS_TO_BUILD', args.llvm_targets_to_build)

        # Add the cmake options for vendors
        self.cmake_options.extend(self._compiler_vendor_flags)

        # Add the cmake options for compiler version information.
        self.cmake_options.extend(self._version_flags)

        # Add linker flags if specified
        self.cmake_options.extend(self._use_linker)

        if args.build_swift:
            from .swift import Swift
            swift_product = Swift(args, toolchain, source_dir, build_dir)

            # Filter out vendor and version flags that we explicitly merged
            # in LLVMCombined to prevent redundancies.
            handled_vars = [
                'SWIFT_VENDOR', 'SWIFT_VENDOR_UTI', 'SWIFT_VERSION',
                'CLANG_COMPILER_VERSION', 'SWIFT_COMPILER_VERSION',
                'SWIFT_TOOLCHAIN_VERSION'
            ]

            for option in swift_product.cmake_options:
                is_handled = False
                for var in handled_vars:
                    if option.startswith(f'-D{var}=') or \
                       option.startswith(f'-D{var}:'):
                        is_handled = True
                        break
                if not is_handled:
                    self.cmake_options.extend_raw([option])

    @classmethod
    def is_build_script_impl_product(cls):
        """is_build_script_impl_product -> bool

        Whether this product is produced by build-script-impl.
        """
        return False

    @classmethod
    def is_before_build_script_impl_product(cls):
        """is_before_build_script_impl_product -> bool

        Whether this product is built before any build-script-impl products.
        """
        return True

    @property
    def _compiler_vendor_flags(self):
        if self.args.compiler_vendor == "none":
            return []

        if self.args.compiler_vendor != "apple":
            raise RuntimeError("Unknown compiler vendor?!")

        flags = [
            ('CLANG_VENDOR', 'Apple'),
            ('CLANG_VENDOR_UTI', 'com.apple.compilers.llvm.clang'),
            # This is safe since we always provide a default.
            ('PACKAGE_VERSION', str(self.args.clang_user_visible_version))
        ]

        if self.args.build_swift:
            flags.extend([
                ('SWIFT_VENDOR', 'Apple'),
                ('SWIFT_VENDOR_UTI', 'com.apple.compilers.llvm.swift'),
                ('SWIFT_VERSION', str(self.args.swift_user_visible_version)),
            ])
        return flags

    @property
    def _version_flags(self):
        result = CMakeOptions()
        if self.args.clang_compiler_version is not None:
            result.define(
                'CLANG_REPOSITORY_STRING',
                "clang-{}".format(self.args.clang_compiler_version))
            if self.args.build_swift:
                result.define('CLANG_COMPILER_VERSION',
                              str(self.args.clang_compiler_version))

        if self.args.build_swift:
            if self.args.swift_compiler_version is not None:
                swift_compiler_version = str(self.args.swift_compiler_version)
                result.define('SWIFT_COMPILER_VERSION', swift_compiler_version)
                result.define('SWIFT_TOOLCHAIN_VERSION',
                              "swiftlang-" + swift_compiler_version)
            else:
                toolchain_version = os.environ.get('TOOLCHAIN_VERSION')
                if toolchain_version:
                    result.define('SWIFT_TOOLCHAIN_VERSION', toolchain_version)
        return result

    @property
    def _use_linker(self):
        if self.args.use_linker is None:
            return []
        return [('CLANG_DEFAULT_LINKER', self.args.use_linker)]

    @classmethod
    def get_dependencies(cls):
        return [cmark.CMark,
                earlyswiftdriver.EarlySwiftDriver,
                staticswiftlinux.StaticSwiftLinuxConfig,
                libcxx.LibCXX]

    def llvm_c_flags(self, platform, arch):
        result = self.common_cross_c_flags(platform, arch, include_arch=False)
        if self.is_debug_info():
            if self.args.lto_type:
                result.append('-gline-tables-only')
            else:
                result.append('-g')
        return result

    def copy_lib_stripping_architecture(self, source, dest, arch):

        # An alternative approach would be to use || to first
        # attempt the removal of the slice and fall back to the
        # copy when failing.
        # However, this would leave unneeded error messages in the logs
        # that may hinder investigation; in addition, in this scenario
        # the `call` function seems to not propagate correctly failure
        # exit codes.
        if arch in shell.capture(['lipo', '-archs', source], dry_run=False):
            shell.call(['lipo', '-remove', arch, source, '-output', dest])
        else:
            shutil.copy(source, dest)

    def copy_embedded_compiler_rt_builtins_from_darwin_host_toolchain(
            self, clang_dest_dir):
        host_cxx_dir = os.path.dirname(self.toolchain.cxx)
        host_lib_clang_dir = os.path.join(host_cxx_dir, os.pardir, 'lib', 'clang')
        dest_lib_clang_dir = os.path.join(clang_dest_dir, 'lib', 'clang')

        if not os.path.exists(host_lib_clang_dir) or \
           not os.path.exists(dest_lib_clang_dir):
            return 0

        dest_cxx_builtins_version = os.listdir(dest_lib_clang_dir)
        dest_builtins_dir = os.path.join(clang_dest_dir, 'lib', 'clang',
                                         dest_cxx_builtins_version[0],
                                         'lib', 'darwin')

        if os.path.exists(dest_builtins_dir):
            for host_cxx_builtins_path in os.listdir(host_lib_clang_dir):
                host_cxx_builtins_dir = os.path.join(host_lib_clang_dir,
                                                     host_cxx_builtins_path,
                                                     'lib', 'darwin')
                print('copying compiler-rt embedded builtins from {}'
                      ' into the local clang build directory {}.'.format(
                          host_cxx_builtins_dir, dest_builtins_dir), flush=True)

                # Always strip i386 from copied host archives: Xcode 27's ld/strip
                # reject i386, and copy_lib_stripping_architecture falls back to a
                # plain copy when the source has no i386 slice.
                for _os in ['ios', 'watchos', 'tvos', 'xros']:
                    # Copy over the device .a when necessary
                    lib_name = 'libclang_rt.{}.a'.format(_os)
                    host_lib_path = os.path.join(host_cxx_builtins_dir, lib_name)
                    dest_lib_path = os.path.join(dest_builtins_dir, lib_name)
                    if not os.path.isfile(dest_lib_path):
                        if os.path.isfile(host_lib_path):
                            print('{} -> {} (stripping i386)'.format(
                                host_lib_path, dest_lib_path))
                            self.copy_lib_stripping_architecture(host_lib_path,
                                                                 dest_lib_path,
                                                                 'i386')
                        elif self.args.verbose_build:
                            print('no file exists at {}'.format(host_lib_path))

                    # Copy over the simulator .a when necessary
                    sim_lib_name = 'libclang_rt.{}sim.a'.format(_os)
                    host_sim_lib_path = os.path.join(host_cxx_builtins_dir,
                                                     sim_lib_name)
                    dest_sim_lib_path = os.path.join(dest_builtins_dir, sim_lib_name)

                    if not os.path.isfile(dest_sim_lib_path):
                        if os.path.isfile(host_sim_lib_path):
                            print('{} -> {} (stripping i386)'.format(
                                host_sim_lib_path, dest_sim_lib_path))
                            self.copy_lib_stripping_architecture(
                                host_sim_lib_path, dest_sim_lib_path, 'i386')

                        elif os.path.isfile(host_lib_path):
                            # The simulator .a might not exist if the host
                            # Xcode is old. In that case, copy over the
                            # device library to the simulator location to allow
                            # clang to find it. The device library has the simulator
                            # slices in Xcode that doesn't have the simulator .a, so
                            # the link is still valid.
                            print('copying over faux-sim library {} to {} '
                                  '(stripping i386)'.format(
                                      host_lib_path, sim_lib_name))
                            self.copy_lib_stripping_architecture(
                                host_lib_path, dest_sim_lib_path, 'i386')
                        elif self.args.verbose_build:
                            print('no file exists at {}', host_sim_lib_path)

                os.makedirs(os.path.join(dest_builtins_dir, 'macho_embedded'),
                            exist_ok=True)
                for _flavor in ['hard_pic', 'hard_static', 'soft_pic', 'soft_static']:
                    # Copy over the macho_embedded .a when necessary
                    lib_name = os.path.join('macho_embedded', 'libclang_rt.{}.a'.format(
                        _flavor))
                    host_lib_path = os.path.join(host_cxx_builtins_dir, lib_name)
                    dest_lib_path = os.path.join(dest_builtins_dir, lib_name)
                    if not os.path.isfile(dest_lib_path):
                        if os.path.isfile(host_lib_path):
                            print('{} -> {}'.format(host_lib_path, dest_lib_path))
                            shutil.copy(host_lib_path, dest_lib_path)
                        elif self.args.verbose_build:
                            print('no file exists at {}'.format(host_lib_path))

    def should_build(self, host_target):
        """should_build() -> Bool

        Whether or not this product should be built with the given arguments.
        """
        # LLVM will always be built in part
        return True

    def build(self, host_target):
        """build() -> void

        Perform the build, for a non-build-script-impl product.
        """

        (platform, arch) = host_target.split('-')

        llvm_cmake_options, _, relevant_options = self.host_cmake_options(host_target)
        llvm_cmake_options.extend_raw(self.args.llvm_cmake_options)

        # TODO: handle cross compilation
        llvm_cmake_options.define('CMAKE_INSTALL_PREFIX:PATH', self.args.install_prefix)
        llvm_cmake_options.define('INTERNAL_INSTALL_PREFIX', 'local')

        if host_target.startswith('linux'):
            toolchain_file = self.generate_linux_toolchain_file(
                platform, arch,
                crosscompiling=self.is_cross_compile_target(host_target))
            llvm_cmake_options.define('CMAKE_TOOLCHAIN_FILE:PATH', toolchain_file)

        target_supports_split_dwarf = host_target.startswith(('linux', 'freebsd'))
        if target_supports_split_dwarf and self.is_debug_info():
            # On platforms that support split-dwarf, build LLVM and subprojects with
            #  -gsplit-dwarf which is more space/time efficient than -g on that platform.
            llvm_cmake_options.define('LLVM_USE_SPLIT_DWARF:BOOL', 'YES')

        build = True
        if not self.args._build_llvm or (not self.args.cross_compile_build_swift_tools
                                         and self.is_cross_compile_target(host_target)):
            # Indicating we don't want to build LLVM at all should
            # override everything.
            build_targets = []
            build = False
        elif self.args.skip_build or not self.args.build_llvm:
            # We can't skip the build completely because the standalone
            # build of Swift depends on these.
            build_targets = ['llvm-tblgen', 'clang-resource-headers',
                             'intrinsics_gen', 'clang-tablegen-targets']

            # If we are not performing a toolchain-only build, then we
            # also want to include the following targets for testing purposes.
            if not self.args.build_toolchain_only:
                build_targets.extend([
                    'FileCheck',
                    'not',
                    'llvm-nm',
                    'llvm-size'
                ])
        else:
            build_targets = ['all']

            if self.args.llvm_ninja_targets_for_cross_compile_hosts and \
               self.is_cross_compile_target(host_target):
                build_targets = (self.args.llvm_ninja_targets_for_cross_compile_hosts)
            elif self.args.llvm_ninja_targets:
                build_targets = (self.args.llvm_ninja_targets)

        if self.args.host_libtool:
            llvm_cmake_options.define('CMAKE_LIBTOOL', self.args.host_libtool)

        # Note: we set the variable:
        #
        # LLVM_TOOL_SWIFT_BUILD
        #
        # below because this script builds swift separately, and people
        # often have reasons to symlink the swift directory into
        # llvm/tools, e.g. to build LLDB.

        llvm_c_flags = ' '.join(self.llvm_c_flags(platform, arch))
        llvm_cmake_options.define('CMAKE_C_FLAGS', llvm_c_flags)
        llvm_cmake_options.define('CMAKE_CXX_FLAGS', llvm_c_flags)
        llvm_cmake_options.define('CMAKE_C_COMPILER_TARGET', self.target_for_platform(platform, arch, include_version=True))
        llvm_cmake_options.define('CMAKE_CXX_COMPILER_TARGET', self.target_for_platform(platform, arch, include_version=True))
        llvm_cmake_options.define('CMAKE_C_FLAGS_RELWITHDEBINFO', '-O2 -DNDEBUG')
        llvm_cmake_options.define('CMAKE_CXX_FLAGS_RELWITHDEBINFO', '-O2 -DNDEBUG')
        llvm_cmake_options.define('CMAKE_BUILD_TYPE:STRING',
                                  self.args.llvm_build_variant)
        llvm_cmake_options.define('LLVM_TOOL_SWIFT_BUILD:BOOL', 'FALSE')
        llvm_cmake_options.define('LLVM_TOOL_LLD_BUILD:BOOL', 'TRUE')
        llvm_cmake_options.define('LLVM_INCLUDE_DOCS:BOOL', 'TRUE')
        llvm_cmake_options.define('LLVM_ENABLE_LTO:STRING', self.args.lto_type)
        llvm_cmake_options.define('COMPILER_RT_INTERCEPT_LIBDISPATCH', 'ON')
        # Swift expects the old layout for the runtime directory
        # updating this in tracked in #80180
        llvm_cmake_options.define('LLVM_ENABLE_PER_TARGET_RUNTIME_DIR', 'OFF')
        if host_target.startswith('linux'):
            # This preserves the behaviour we had when using
            # LLVM_BUILD_EXTERNAL COMPILER_RT --
            # that is, having the linker not complaining if symbols used
            # by TSan are undefined (namely the ones for Blocks Runtime)
            # In the long term, we want to remove this and
            # build Blocks Runtime before LLVM
            if ("-DCLANG_DEFAULT_LINKER=gold" in llvm_cmake_options
                or "-DCLANG_DEFAULT_LINKER:STRING=gold" in llvm_cmake_options):
                print("Assuming just built clang will use a gold linker -- "
                      "if that's not the case, please adjust the value of "
                      "`SANITIZER_COMMON_LINK_FLAGS` in `extra-llvm-cmake-options`",
                      flush=True)
                llvm_cmake_options.define(
                    'SANITIZER_COMMON_LINK_FLAGS:STRING',
                    '-Wl,--unresolved-symbols,ignore-in-object-files')
            else:
                print("Assuming just built clang will use a non gold linker -- "
                      "if that's not the case, please adjust the value of "
                      "`SANITIZER_COMMON_LINK_FLAGS` in `extra-llvm-cmake-options`",
                      flush=True)
                llvm_cmake_options.define(
                    'SANITIZER_COMMON_LINK_FLAGS:STRING', '-Wl,-z,undefs')

        builtins_runtimes_target_for_darwin = f'{arch}-apple-darwin'
        if system() == "Darwin":
            llvm_cmake_options.define(
                f'BUILTINS_{builtins_runtimes_target_for_darwin}_'
                'CMAKE_OSX_SYSROOT',
                relevant_options['CMAKE_OSX_SYSROOT'])
            llvm_cmake_options.define(
                f'RUNTIMES_{builtins_runtimes_target_for_darwin}_'
                'CMAKE_OSX_SYSROOT',
                relevant_options['CMAKE_OSX_SYSROOT'])
            llvm_cmake_options.define(
                'LLVM_BUILTIN_TARGETS', builtins_runtimes_target_for_darwin)
            llvm_cmake_options.define(
                'LLVM_RUNTIME_TARGETS', builtins_runtimes_target_for_darwin)
            llvm_cmake_options.define('RUNTIMES_BUILD_ALLOW_DARWIN', 'ON')
            # Build all except rtsan
            llvm_cmake_options.define(
                f'RUNTIMES_{builtins_runtimes_target_for_darwin}_'
                'COMPILER_RT_SANITIZERS_TO_BUILD',
                'asan;dfsan;msan;hwasan;tsan;safestack;cfi;scudo_standalone;'
                'ubsan_minimal;gwp_asan;nsan;asan_abi')

        if self.args.build_embedded_stdlib and system() == "Darwin":
            # Ask for Mach-O cross-compilation builtins (for Embedded Swift)
            llvm_cmake_options.define(
                f'BUILTINS_{builtins_runtimes_target_for_darwin}_'
                'COMPILER_RT_FORCE_BUILD_BAREMETAL_MACHO_BUILTINS_ARCHS:'
                'STRING', 'armv6 armv6m armv7 armv7m armv7em armv8m.main armv8.1m.main')

        llvm_enable_projects = ['clang']
        if self.args.build_lldb:
            llvm_enable_projects.append('lldb')
        llvm_enable_runtimes = []

        if self.args.build_compiler_rt and \
                not self.is_cross_compile_target(host_target):
            llvm_enable_runtimes.append('compiler-rt')

        # This accounts for previous incremental runs using the old
        # way of build compiler_rt that may have set
        # those in the LLVM CMakeCache.txt
        llvm_cmake_options.undefine('LLVM_TOOL_COMPILER_RT_BUILD')
        llvm_cmake_options.undefine('LLVM_BUILD_EXTERNAL_COMPILER_RT')

        if self.args.build_clang_tools_extra:
            llvm_enable_projects.append('clang-tools-extra')

        # Building lld is on by default -- on non-Darwin so we can always have a
        # linker that is compatible with the swift we are using to
        # compile the stdlib, but on Darwin too for Embedded Swift use cases.
        #
        # This makes it easier to build target stdlibs on systems that
        # have old toolchains without more modern linker features.
        if self.args.build_lld:
            llvm_enable_projects.append('lld')

        llvm_cmake_options.define('LLVM_ENABLE_PROJECTS',
                                  ';'.join(llvm_enable_projects))
        llvm_cmake_options.define('LLVM_ENABLE_RUNTIMES',
                                  ';'.join(llvm_enable_runtimes))
        if self.args.build_swift:
            llvm_cmake_options.define('LLVM_EXTERNAL_PROJECTS',
                                      'swift')
            llvm_cmake_options.define('LLVM_EXTERNAL_SWIFT_SOURCE_DIR',
                                      os.path.join(self.source_dir, '../../swift'))
            llvm_cmake_options.define('cmark-gfm_DIR',
                                      os.path.join(self.build_dir, '../cmark-install/usr/local/lib/cmake'))
            llvm_cmake_options.define('SWIFT_PATH_TO_STRING_PROCESSING_SOURCE',
                                      os.path.join(self.source_dir, '../../swift-experimental-string-processing '))

            # Incorporate Swift CMake options from build-script-impl
            # (lines 1693-2130)

            def add_swift_bool(cmake_var, arg_name=None):
                arg_name = arg_name or cmake_var.lower()
                val = getattr(self.args, arg_name, None)
                if val is not None:
                    llvm_cmake_options.define(cmake_var + ':BOOL', val)

            def add_swift_string(cmake_var, arg_name=None):
                arg_name = arg_name or cmake_var.lower()
                val = getattr(self.args, arg_name, None)
                if val is not None and str(val) != "":
                    llvm_cmake_options.define(cmake_var + ':STRING', str(val))

            llvm_cmake_options.define('SWIFT_ANALYZE_CODE_COVERAGE:STRING',
                                      str(self.args.swift_analyze_code_coverage).upper())
            llvm_cmake_options.define('SWIFT_STDLIB_BUILD_TYPE:STRING',
                                      self.args.swift_stdlib_build_variant)
            add_swift_bool('SWIFT_STDLIB_ASSERTIONS', 'swift_stdlib_assertions')
            add_swift_bool('SWIFT_STDLIB_ENABLE_DEBUG_PRECONDITIONS_IN_RELEASE')
            add_swift_bool('SWIFT_STDLIB_ENABLE_STRICT_AVAILABILITY',
                           'swift_stdlib_strict_availability')
            add_swift_bool('SWIFT_ENABLE_DISPATCH')
            add_swift_bool('SWIFT_IMPLICIT_CONCURRENCY_IMPORT')
            add_swift_bool('SWIFT_STDLIB_SUPPORT_BACK_DEPLOYMENT')
            add_swift_bool('SWIFT_STDLIB_SINGLE_THREADED_CONCURRENCY')
            add_swift_bool('SWIFT_STDLIB_TASK_TO_THREAD_MODEL_CONCURRENCY')

            # SWIFT_ENABLE_RUNTIME_FUNCTION_COUNTERS fallback to
            # swift_stdlib_assertions
            func_counters = getattr(self.args,
                                    'swift_enable_runtime_function_counters',
                                    None)
            if func_counters is None or str(func_counters) == "":
                func_counters = self.args.swift_stdlib_assertions
            llvm_cmake_options.define('SWIFT_ENABLE_RUNTIME_FUNCTION_COUNTERS:BOOL',
                                      func_counters)

            add_swift_bool('SWIFT_STDLIB_HAS_DLADDR')
            add_swift_bool('SWIFT_STDLIB_HAS_DLSYM')
            add_swift_bool('SWIFT_STDLIB_HAS_FILESYSTEM')
            add_swift_bool('SWIFT_RUNTIME_STATIC_IMAGE_INSPECTION')
            add_swift_bool('SWIFT_STDLIB_OS_VERSIONING')
            add_swift_bool('SWIFT_STDLIB_HAS_COMMANDLINE')
            add_swift_bool('SWIFT_STDLIB_HAS_DARWIN_LIBMALLOC')
            add_swift_bool('SWIFT_STDLIB_HAS_STDIN')
            add_swift_bool('SWIFT_STDLIB_HAS_ENVIRON')
            add_swift_string('SWIFT_STDLIB_ENABLE_LTO', 'swift_stdlib_lto')
            add_swift_bool('SWIFT_STDLIB_PASSTHROUGH_METADATA_ALLOCATOR')
            add_swift_bool('SWIFT_STDLIB_SHORT_MANGLING_LOOKUPS')
            add_swift_bool('SWIFT_STDLIB_ENABLE_VECTOR_TYPES')
            add_swift_bool('SWIFT_STDLIB_HAS_TYPE_PRINTING')
            add_swift_string('SWIFT_STDLIB_TRAP_FUNCTION')
            add_swift_bool('SWIFT_STDLIB_EXPERIMENTAL_HERMETIC_SEAL_AT_LINK')
            add_swift_bool('SWIFT_STDLIB_DISABLE_INSTANTIATION_CACHES')
            add_swift_string('SWIFT_STDLIB_REFLECTION_METADATA')

            add_swift_bool('SWIFT_BUILD_CLANG_OVERLAYS',
                           'build_swift_clang_overlays')
            add_swift_bool('SWIFT_BUILD_REMOTE_MIRROR',
                           'build_swift_remote_mirror')
            add_swift_bool('SWIFT_STDLIB_SIL_DEBUGGING',
                           'build_sil_debugging_stdlib')
            add_swift_bool('SWIFT_CHECK_INCREMENTAL_COMPILATION',
                           'check_incremental_compilation')
            add_swift_bool('SWIFT_ENABLE_ARRAY_COW_CHECKS',
                           'enable_array_cow_checks')
            add_swift_bool('SWIFT_REPORT_STATISTICS', 'report_statistics')
            add_swift_bool('SWIFT_BUILD_DYNAMIC_STDLIB',
                           'build_swift_dynamic_stdlib')
            add_swift_bool('SWIFT_BUILD_STATIC_STDLIB',
                           'build_swift_static_stdlib')
            add_swift_bool('SWIFT_BUILD_DYNAMIC_SDK_OVERLAY',
                           'build_swift_dynamic_sdk_overlay')
            add_swift_bool('SWIFT_BUILD_STATIC_SDK_OVERLAY',
                           'build_swift_static_sdk_overlay')

            # SWIFT_BUILD_PERF_TESTSUITE -> not skip_build_benchmarks
            llvm_cmake_options.define('SWIFT_BUILD_PERF_TESTSUITE:BOOL',
                                      not self.args.skip_build_benchmarks)

            add_swift_bool('SWIFT_BUILD_EXAMPLES', 'build_swift_examples')
            add_swift_bool('SWIFT_BUILD_LIBEXEC', 'build_swift_libexec')
            add_swift_bool('SWIFT_INCLUDE_TESTS', 'swift_include_tests')
            add_swift_bool('SWIFT_EMBED_BITCODE_SECTION', 'embed_bitcode_section')

            lto_type = getattr(self.args, 'swift_tools_enable_lto',
                               self.args.lto_type)
            if lto_type:
                llvm_cmake_options.define('SWIFT_TOOLS_ENABLE_LTO:STRING',
                                          lto_type)

            add_swift_bool('SWIFT_BUILD_RUNTIME_WITH_HOST_COMPILER')

            libdispatch_build_type = getattr(self.args,
                                             'libdispatch_build_variant',
                                             self.args.build_variant)
            llvm_cmake_options.define('LIBDISPATCH_CMAKE_BUILD_TYPE:STRING',
                                      libdispatch_build_type)

            swift_syntax_src = os.path.join(self.source_dir, '../../swift-syntax')
            llvm_cmake_options.define('SWIFT_PATH_TO_SWIFT_SYNTAX_SOURCE:PATH',
                                      swift_syntax_src)
            add_swift_bool('SWIFT_ENABLE_BACKTRACING')
            add_swift_bool('SWIFT_STDLIB_OVERRIDABLE_RETAIN_RELEASE')

            if self.args.build_toolchain_only:
                llvm_cmake_options.define('SWIFT_TOOL_SIL_OPT_BUILD', 'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SWIFT_IDE_TEST_BUILD', 'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SWIFT_REMOTEAST_TEST_BUILD',
                                          'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_LLDB_MODULEIMPORT_TEST_BUILD',
                                          'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SIL_EXTRACT_BUILD', 'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SWIFT_LLVM_OPT_BUILD', 'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SWIFT_SDK_ANALYZER_BUILD',
                                          'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SWIFT_SDK_DIGESTER_BUILD',
                                          'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SOURCEKITD_TEST_BUILD', 'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SOURCEKITD_REPL_BUILD', 'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_COMPLETE_TEST_BUILD', 'FALSE')
                llvm_cmake_options.define('SWIFT_TOOL_SWIFT_REFLECTION_DUMP_BUILD',
                                          'FALSE')

            llvm_cmake_options.define('SWIFT_PATH_TO_CMARK_SOURCE:PATH',
                                      os.path.join(self.source_dir, '../../cmark'))
            llvm_cmake_options.define(
                'SWIFT_PATH_TO_CMARK_BUILD:PATH',
                os.path.join(self.build_dir, '../cmark-' + host_target))
            llvm_cmake_options.define(
                'SWIFT_PATH_TO_LIBDISPATCH_SOURCE:PATH',
                os.path.join(self.source_dir,
                             '../../swift-corelibs-libdispatch'))
            llvm_cmake_options.define(
                'SWIFT_PATH_TO_LIBDISPATCH_BUILD:PATH',
                os.path.join(self.build_dir, '../libdispatch-' + host_target))

            if self.args.stdlib_deployment_targets:
                llvm_cmake_options.define('SWIFT_SDKS:STRING',
                                          ';'.join(self.args.
                                                   stdlib_deployment_targets))

            add_swift_bool('SWIFT_STDLIB_ENABLE_OBJC_INTEROP', 'swift_objc_interop')

            if getattr(self.args, 'swift_enable_reflection', None) == '0':
                llvm_cmake_options.define('SWIFT_ENABLE_REFLECTION:BOOL', 'FALSE')

            add_swift_string('SWIFT_PRIMARY_VARIANT_SDK')
            add_swift_string('SWIFT_PRIMARY_VARIANT_ARCH')
            add_swift_bool('SWIFT_STDLIB_STABLE_ABI')
            add_swift_bool('SWIFT_STDLIB_ENABLE_PRESPECIALIZATION')
            add_swift_bool('SWIFT_STDLIB_SUPPORTS_BACKTRACE_REPORTING')
            add_swift_bool('SWIFT_STDLIB_HAS_ASL')
            add_swift_bool('SWIFT_STDLIB_HAS_LOCALE')
            add_swift_string('SWIFT_INSTALL_COMPONENTS')
            add_swift_string('SWIFT_FREESTANDING_FLAVOR')
            add_swift_string('SWIFT_FREESTANDING_SDK')
            add_swift_string('SWIFT_FREESTANDING_TRIPLE_NAME')
            add_swift_string('SWIFT_FREESTANDING_MODULE_NAME')

            if getattr(self.args, 'swift_freestanding_archs', None):
                llvm_cmake_options.define('SWIFT_FREESTANDING_ARCHS:STRING',
                                          ';'.join(self.args.
                                                   swift_freestanding_archs))

            add_swift_bool('SWIFT_ENABLE_EXPERIMENTAL_STRING_PROCESSING')
            add_swift_bool('SWIFT_BUILD_REGEX_PARSER_IN_COMPILER')
            add_swift_bool('SWIFT_STDLIB_TRACING')
            add_swift_bool('SWIFT_STDLIB_USE_RELATIVE_PROTOCOL_WITNESS_TABLES')
            add_swift_bool('SWIFT_STDLIB_USE_FRAGILE_RESILIENT_PROTOCOL_WITNESS_TABLES')
            add_swift_string('SWIFT_RUNTIME_FIXED_BACKTRACER_PATH')
            add_swift_string('SWIFT_THREADING_PACKAGE')

        if self.args.build_lldb:
            # Incorporate LLDB CMake options from build-script-impl
            # (lines 2132-2285)

            def add_lldb_bool(cmake_var, arg_name=None):
                arg_name = arg_name or cmake_var.lower()
                val = getattr(self.args, arg_name, None)
                if val is not None:
                    llvm_cmake_options.define(cmake_var + ':BOOL', val)

            def add_lldb_string(cmake_var, arg_name=None):
                arg_name = arg_name or cmake_var.lower()
                val = getattr(self.args, arg_name, None)
                if val is not None and str(val) != "":
                    llvm_cmake_options.define(cmake_var + ':STRING', str(val))

            # Extra arguments
            llvm_cmake_options.extend_raw(self.args.lldb_cmake_options)

            # Pick the right cache.
            if system() == 'Darwin':
                cmake_cache = "Apple-lldb-macOS.cmake"
            else:
                cmake_cache = "Apple-lldb-Linux.cmake"

            lldb_source_dir = os.path.join(self.source_dir, 'lldb')
            llvm_cmake_options.extend_raw([
                '-C', os.path.join(lldb_source_dir, 'cmake/caches', cmake_cache)
            ])

            add_lldb_string('LLDB_BUILD_TYPE', 'lldb_build_variant')
            add_lldb_bool('LLDB_ASSERTIONS', 'lldb_assertions')

            # LLDB_SWIFTC:PATH=${SWIFTC_BIN}
            # We assume swiftc is in the same build directory if build_swift
            if self.args.build_swift:
                swift_build_dir = os.path.join(self.build_dir, '../swift-' + host_target)
                llvm_cmake_options.define('LLDB_SWIFTC:PATH',
                                          os.path.join(swift_build_dir, 'bin/swiftc'))
                llvm_cmake_options.define('LLDB_SWIFT_LIBS:PATH',
                                          os.path.join(swift_build_dir, 'lib/swift'))
                llvm_cmake_options.define('Swift_DIR:PATH',
                                          os.path.join(swift_build_dir, 'lib/cmake/swift'))

            llvm_cmake_options.define('LLDB_ENABLE_CURSES', 'ON')
            llvm_cmake_options.define('LLDB_ENABLE_LIBEDIT', 'ON')
            llvm_cmake_options.define('LLDB_ENABLE_PYTHON', 'ON')
            llvm_cmake_options.define('LLDB_ENABLE_LZMA', 'OFF')
            llvm_cmake_options.define('LLDB_ENABLE_LUA', 'OFF')

            if self.args.build_toolchain_only:
                should_configure_tests = False
            else:
                should_configure_tests = getattr(self.args, 'lldb_configure_tests', True)
            llvm_cmake_options.define('LLDB_INCLUDE_TESTS:BOOL', should_configure_tests)

            if not self.is_cross_compile_target(host_target):
                libcxx_build_dir = os.path.join(self.build_dir, '../libcxx-' + host_target)
                llvm_cmake_options.define('LLDB_TEST_LIBCXX_ROOT_DIR:STRING',
                                          libcxx_build_dir)

            # Construct dotest arguments
            lldb_build_dir = os.path.join(self.build_dir, '../lldb-' + host_target)
            dotest_args = ["--build-dir",
                           os.path.join(lldb_build_dir, 'lldb-test-build.noindex'),
                           "--skip-category=watchpoint"]
            if getattr(self.args, 'lldb_test_swift_only', False):
                dotest_args.append("--skip-category=dwo")

            llvm_cmake_options.define('LLDB_TEST_USER_ARGS', ';'.join(dotest_args))

            if self.is_cross_compile_target(host_target):
                llvm_cmake_options.define('LLDB_TABLEGEN', 'lldb-tblgen')
                llvm_cmake_options.define('LLDB_TABLEGEN_EXE', 'lldb-tblgen')

            add_lldb_bool('LLDB_USE_SYSTEM_DEBUGSERVER')
            llvm_cmake_options.extend_raw(self.args.lldb_extra_cmake_args)

        # NOTE: This is not a dead option! It is relied upon for certain
        # bots/build-configs!
        #
        # TODO: In the future when we are always cross compiling and
        # using Toolchain files, we should put this in either a
        # toolchain file or a cmake cache.
        if self.args.build_toolchain_only:
            clang_tool_driver_build = CMakeOptions.true_false(
                not self.args.build_runtime_with_host_compiler)
            llvm_cmake_options.define('LLVM_BUILD_TOOLS', 'NO')
            llvm_cmake_options.define('LLVM_INSTALL_TOOLCHAIN_ONLY', 'YES')
            llvm_cmake_options.define('LLVM_INCLUDE_TESTS', 'NO')
            llvm_cmake_options.define('CLANG_INCLUDE_TESTS', 'NO')
            llvm_cmake_options.define('LLVM_INCLUDE_UTILS', 'NO')
            llvm_cmake_options.define('LLVM_TOOL_LLI_BUILD', 'NO')
            llvm_cmake_options.define('LLVM_TOOL_LLVM_AR_BUILD', 'NO')
            llvm_cmake_options.define('CLANG_TOOL_CLANG_CHECK_BUILD', 'NO')
            llvm_cmake_options.define('CLANG_TOOL_ARCMT_TEST_BUILD', 'NO')
            llvm_cmake_options.define('CLANG_TOOL_C_ARCMT_TEST_BUILD', 'NO')
            llvm_cmake_options.define('CLANG_TOOL_C_INDEX_TEST_BUILD', 'NO')
            llvm_cmake_options.define('CLANG_TOOL_DRIVER_BUILD',
                                      clang_tool_driver_build)
            llvm_cmake_options.define('CLANG_TOOL_DIAGTOOL_BUILD', 'NO')
            llvm_cmake_options.define('CLANG_TOOL_SCAN_BUILD_BUILD', 'NO')
            llvm_cmake_options.define('CLANG_TOOL_SCAN_VIEW_BUILD', 'NO')
            llvm_cmake_options.define('CLANG_TOOL_CLANG_FORMAT_BUILD', 'NO')

        if not self.args.llvm_include_tests:
            llvm_cmake_options.define('LLVM_INCLUDE_TESTS', 'NO')
            llvm_cmake_options.define('CLANG_INCLUDE_TESTS', 'NO')

        if ("-DLLVM_INCLUDE_TESTS=NO" not in llvm_cmake_options
            and "-DLLVM_INCLUDE_TESTS:BOOL=FALSE" not in llvm_cmake_options):
            # This supports scenarios where tests are run
            # outside of `build-script` (e.g. with `run-test`)
            build_targets.append('LLVMTestingSupport')

        if self.is_cross_compile_target(host_target):
            build_root = os.path.dirname(self.build_dir)
            host_machine_target = targets.StdlibDeploymentTarget.host_target().name
            host_build_dir = os.path.join(build_root, 'llvm-{}'.format(
                host_machine_target))
            llvm_tblgen = os.path.join(host_build_dir, 'bin', 'llvm-tblgen')
            llvm_cmake_options.define('LLVM_TABLEGEN', llvm_tblgen)
            clang_tblgen = os.path.join(host_build_dir, 'bin', 'clang-tblgen')
            llvm_cmake_options.define('CLANG_TABLEGEN', clang_tblgen)
            confusable_chars_gen = os.path.join(host_build_dir, 'bin',
                                                'clang-tidy-confusable-chars-gen')
            llvm_cmake_options.define('CLANG_TIDY_CONFUSABLE_CHARS_GEN',
                                      confusable_chars_gen)
            llvm = os.path.join(host_build_dir, 'llvm')
            llvm_cmake_options.define('LLVM_NATIVE_BUILD', llvm)
            if self.args.build_swift:
                llvm_cmake_options.define('SWIFT_NATIVE_LLVM_TOOLS_PATH:STRING',
                                          os.path.join(host_build_dir, 'bin'))
                llvm_cmake_options.define('SWIFT_NATIVE_CLANG_TOOLS_PATH:STRING',
                                          os.path.join(host_build_dir, 'bin'))
                host_swift_build_dir = os.path.join(
                    build_root, 'swift-{}'.format(host_machine_target))
                llvm_cmake_options.define('SWIFT_NATIVE_SWIFT_TOOLS_PATH:STRING',
                                          os.path.join(host_swift_build_dir, 'bin'))

        host_config = HostSpecificConfiguration(host_target, self.args)

        self.cmake_options.extend(host_config.cmake_options)
        self.cmake_options.extend(llvm_cmake_options)
        self.cmake_options.extend_raw(self.args.extra_llvm_cmake_options)

        self._handle_cxx_headers(host_target, platform)

        # Use `cmake-file-api` in case it is available.
        self._write_runtime_cmake_file_api_queries(builtins_runtimes_target_for_darwin)

        self.build_with_cmake(build_targets, self.args.llvm_build_variant, [],
                              build_llvm=build)

        # copy over the compiler-rt builtins for iOS/tvOS/watchOS to ensure
        # that Swift's stdlib can use compiler-rt builtins when targeting
        # iOS/tvOS/watchOS.
        if self.args.build_llvm and system() == 'Darwin':
            self.copy_embedded_compiler_rt_builtins_from_darwin_host_toolchain(
                self.build_dir)

    def _handle_cxx_headers(self, host_target, platform):
        # When we are building LLVM create symlinks to the c++ headers. We need
        # to do this before building LLVM since compiler-rt depends on being
        # built with the just built clang compiler. These are normally put into
        # place during the cmake step of LLVM's build when libcxx is in
        # tree... but we are not building llvm with libcxx in tree when we build
        # swift. So we need to do configure's work here.
        if system() == 'Darwin':
            # We don't need this for Darwin since libcxx is present in SDKs present
            # in Xcode 12.5 and onward (build-script requires Xcode 13.0 at a minimum),
            # and clang knows how to find it there
            # However, we should take care of removing the symlink
            # laid down by a previous invocation, so to avoid failures
            # finding c++ headers should the target folder become invalid
            cxx_include_symlink = os.path.join(self.build_dir, 'include', 'c++')
            if os.path.islink(cxx_include_symlink):
                print('removing the symlink to system headers in the local '
                      f'clang build directory {cxx_include_symlink} .',
                      flush=True)
                shell.remove(cxx_include_symlink)

            return

        host_cxx_headers_dir = None
        if system() == 'Haiku':
            host_cxx_headers_dir = '/boot/system/develop/headers/c++'

        # This means we're building natively on Android in the Termux
        # app, which supplies the $PREFIX variable.
        elif os.environ.get('ANDROID_DATA'):
            host_cxx_headers_dir = os.path.join(os.environ['PREFIX'], 'include', 'c++')

        # Linux
        else:
            host_cxx_headers_dir = '/usr/include/c++'

        if self.is_cross_compile_target(host_target) and \
                platform == "openbsd":
            toolchain_file = self.get_openbsd_toolchain_file()
            if toolchain_file:
                self.llvm_cmake_options.define('CMAKE_TOOLCHAIN_FILE:PATH',
                                               toolchain_file)

        # Find the path in which the local clang build is expecting to find
        # the c++ header files.
        built_cxx_include_dir = os.path.join(self.build_dir, 'include')
        if not os.path.exists(built_cxx_include_dir):
            os.makedirs(built_cxx_include_dir)
        print('symlinking the system headers ({}) into the local '
              'clang build directory ({}).'.format(
                  host_cxx_headers_dir, built_cxx_include_dir), flush=True)
        shell.call(['ln', '-s', '-f', host_cxx_headers_dir, built_cxx_include_dir])

    def _write_runtime_cmake_file_api_queries(self, builtins_runtimes_target_for_darwin):
        if system() == "Darwin":
            sub_build_names = [
                f"builtins-{builtins_runtimes_target_for_darwin}",
                f"runtimes-{builtins_runtimes_target_for_darwin}",
            ]
        else:
            sub_build_names = ["builtins", "runtimes"]

        runtimes_base = os.path.join(self.build_dir, "runtimes")
        for sub_build in sub_build_names:
            self.write_cmake_file_api_query(
                os.path.join(runtimes_base, f"{sub_build}-bins"))

    def should_test(self, host_target):
        """should_test() -> Bool

        Whether or not this product should be tested with the given arguments.
        """

        # We don't test LLVM
        return False

    def test(self, host_target):
        """
        Perform the test phase for the product.

        This phase might build and execute the product tests.
        """
        pass

    def should_install(self, host_target):
        """should_install() -> Bool

        Whether or not this product should be installed with the given
        arguments.
        """
        return self.args.install_llvm and (
            self.args.cross_compile_build_swift_tools or
            not self.is_cross_compile_target(host_target))

    def install(self, host_target):
        """
        Perform the install phase for the product.

        This phase might copy the artifacts from the previous phases into a
        destination directory.
        """

        host_install_destdir = self.host_install_destdir(host_target)
        install_targets = ['install']
        if self.args.llvm_install_components and \
           self.args.llvm_install_components != 'all':
            install_targets = []
            components = self.args.llvm_install_components.split(';')
            if 'compiler-rt' in components:
                # This is a courtesy fallback to avoid breaking downstream presets
                # that are still using the old compiler-rt install component
                components.remove('compiler-rt')
                components.append('builtins')
                components.append('runtimes')
                print('warning: replaced legacy LLVM component compiler-rt '
                      'with builtins;runtimes -- consider updating your preset',
                      flush=True)

            for component in components:
                if self.is_cross_compile_target(host_target) \
                   or not self.args.build_compiler_rt:
                    if component in ['builtins', 'runtimes']:
                        continue
                install_targets.append('install-{}'.format(component))

        self.install_with_cmake(install_targets, host_install_destdir)

        clang_dest_dir = '{}{}'.format(host_install_destdir,
                                       self.args.install_prefix)

        if self.args.llvm_install_components and system() == 'Darwin':
            self.copy_embedded_compiler_rt_builtins_from_darwin_host_toolchain(
                clang_dest_dir)
