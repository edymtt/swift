# tests/products/test_llvm.py -----------------------------------*- python -*-
#
# This source file is part of the LLVM.org open source project
#
# Copyright (c) 2014 - 2017 Apple Inc. and the LLVM project authors
# Licensed under Apache License v2.0 with Runtime Library Exception
#
# See https://swift.org/LICENSE.txt for license information
# See https://swift.org/CONTRIBUTORS.txt for the list of LLVM project authors
# ----------------------------------------------------------------------------

import argparse
import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO

from swift_build_support import shell
from swift_build_support.products import LLVM
from swift_build_support.toolchain import host_toolchain
from swift_build_support.workspace import Workspace


class LLVMTestCase(unittest.TestCase):

    def setUp(self):
        # Setup workspace
        tmpdir1 = os.path.realpath(tempfile.mkdtemp())
        tmpdir2 = os.path.realpath(tempfile.mkdtemp())
        os.makedirs(os.path.join(tmpdir1, 'llvm'))

        self.workspace = Workspace(source_root=tmpdir1,
                                   build_root=tmpdir2)

        # Setup toolchain
        self.toolchain = host_toolchain()
        self.toolchain.cc = '/path/to/cc'
        self.toolchain.cxx = '/path/to/cxx'

        # Setup args
        self.args = argparse.Namespace(
            llvm_targets_to_build='X86;ARM;AArch64;PowerPC;SystemZ',
            llvm_assertions='true',
            compiler_vendor='none',
            clang_compiler_version=None,
            clang_user_visible_version=None,
            darwin_deployment_version_osx='10.9',
            use_linker=None)

        # Setup shell
        shell.dry_run = True
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        self.stdout = StringIO()
        self.stderr = StringIO()
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def tearDown(self):
        shutil.rmtree(self.workspace.build_root)
        shutil.rmtree(self.workspace.source_root)
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        shell.dry_run = False
        self.workspace = None
        self.toolchain = None
        self.args = None

    def test_llvm_targets_to_build(self):
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        expected_targets = 'X86;ARM;AArch64;PowerPC;SystemZ'
        expected_arg = '-DLLVM_TARGETS_TO_BUILD=%s' % expected_targets
        self.assertIn(expected_arg, llvm.cmake_options)

    def test_llvm_enable_assertions(self):
        self.args.llvm_assertions = True
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        self.assertIn('-DLLVM_ENABLE_ASSERTIONS:BOOL=TRUE', llvm.cmake_options)

        self.args.llvm_assertions = False
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        self.assertIn('-DLLVM_ENABLE_ASSERTIONS:BOOL=FALSE',
                      llvm.cmake_options)

    def test_compiler_vendor_flags(self):
        self.args.compiler_vendor = "none"
        self.args.clang_user_visible_version = "1.2.3"
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        self.assertNotIn('-DCLANG_VENDOR=Apple', llvm.cmake_options)
        self.assertNotIn(
            '-DCLANG_VENDOR_UTI=com.apple.compilers.llvm.clang',
            llvm.cmake_options
        )
        self.assertNotIn('-DPACKAGE_VERSION=1.2.3', llvm.cmake_options)

        self.args.compiler_vendor = "apple"
        self.args.clang_user_visible_version = "2.2.3"
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        self.assertIn('-DCLANG_VENDOR=Apple', llvm.cmake_options)
        self.assertIn(
            '-DCLANG_VENDOR_UTI=com.apple.compilers.llvm.clang',
            llvm.cmake_options
        )
        self.assertIn('-DPACKAGE_VERSION=2.2.3', llvm.cmake_options)

        self.args.compiler_vendor = "unknown"
        with self.assertRaises(RuntimeError):
            llvm = LLVM(
                args=self.args,
                toolchain=self.toolchain,
                source_dir='/path/to/src',
                build_dir='/path/to/build')

    def test_version_flags(self):
        self.args.clang_compiler_version = None
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        self.assertListEqual(
            [],
            [x for x in llvm.cmake_options if 'CLANG_REPOSITORY_STRING' in x]
        )

        self.args.clang_compiler_version = "2.2.3"
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        self.assertIn(
            '-DCLANG_REPOSITORY_STRING=clang-2.2.3',
            llvm.cmake_options
        )

    def test_use_linker(self):
        self.args.use_linker = None
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        for s in llvm.cmake_options:
            self.assertFalse('CLANG_DEFAULT_LINKER' in s)

        self.args.use_linker = 'gold'
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        self.assertIn(
            '-DCLANG_DEFAULT_LINKER=gold',
            llvm.cmake_options
        )

        self.args.use_linker = 'lld'
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        self.assertIn(
            '-DCLANG_DEFAULT_LINKER=lld',
            llvm.cmake_options
        )

    def _host_cmake_options_args(self, **overrides):
        # host_cmake_options() reads these args fields. Use linux-x86_64 as
        # the host_target so we hit only the unconditional code path
        # (no Darwin/Android branch fields required).
        defaults = dict(
            lit_args='-sv',
            lit_jobs=1,
            clang_profile_instr_use=None,
            swift_profile_instr_use=None,
            coverage_db=None,
            lto_type=None,
            llvm_enable_index_store=True,
        )
        defaults.update(overrides)
        for key, value in defaults.items():
            setattr(self.args, key, value)

    def test_llvm_enable_index_store_default_on(self):
        self._host_cmake_options_args()
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        llvm_opts, swift_opts, _ = llvm.host_cmake_options('linux-x86_64')
        self.assertIn('-DLLVM_ENABLE_INDEX_STORE:BOOL=TRUE', llvm_opts)
        self.assertIn('-DLLVM_ENABLE_INDEX_STORE:BOOL=TRUE', swift_opts)

    def test_llvm_enable_index_store_disabled(self):
        self._host_cmake_options_args(llvm_enable_index_store=False)
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir='/path/to/src',
            build_dir='/path/to/build')
        llvm_opts, swift_opts, _ = llvm.host_cmake_options('linux-x86_64')
        self.assertIn('-DLLVM_ENABLE_INDEX_STORE:BOOL=FALSE', llvm_opts)
        self.assertIn('-DLLVM_ENABLE_INDEX_STORE:BOOL=FALSE', swift_opts)

    def test_llvm_unified_without_swift(self):
        self.args.unified_llvm_build = True
        self.args.build_swift = False
        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir=os.path.join(self.workspace.source_root, 'llvm'),
            build_dir=os.path.join(self.workspace.build_root, 'llvm'))

        self.assertNotIn('-DSWIFT_VENDOR=Apple', llvm.cmake_options)
        self.assertNotIn('-DSWIFT_VERSION=5.0', llvm.cmake_options)

    def test_llvm_unified_with_swift(self):
        self.args.unified_llvm_build = True
        self.args.build_swift = True
        self.args.compiler_vendor = 'apple'
        self.args.swift_user_visible_version = '6.0'
        self.args.swift_compiler_version = '6.0.1'
        self.args.clang_compiler_version = '15.0.0'
        # Add necessary args for Swift product initialization
        self.args.benchmark = True
        self.args.benchmark_num_onone_iterations = 3
        self.args.benchmark_num_o_iterations = 3
        self.args.enable_tsan_runtime = False
        self.args.force_optimized_typechecker = False
        self.args.enable_stdlibcore_exclusivity_checking = False
        self.args.enable_experimental_differentiable_programming = False
        self.args.enable_experimental_concurrency = False
        self.args.enable_experimental_cxx_interop = False
        self.args.enable_experimental_distributed = False
        self.args.swift_enable_backtracing = False
        self.args.enable_experimental_observation = False
        self.args.enable_experimental_parser_validation = False
        self.args.swift_pedantic_diagnostics = False
        self.args.enable_synchronization = False
        self.args.enable_volatile = False
        self.args.enable_runtime_module = False
        self.args.build_swift_stdlib_static_print = False
        self.args.build_swift_stdlib_unicode_data = True
        self.args.build_embedded_stdlib = True
        self.args.build_embedded_stdlib_cross_compiling = False
        self.args.swift_freestanding_is_darwin = False
        self.args.build_swift_private_stdlib = True
        self.args.swift_tools_ld64_lto_codegen_only_for_supporting_targets = False
        self.args.build_stdlib_docs = False
        self.args.swift_debuginfo_non_lto_args = None
        self.args.enable_new_runtime_build = False
        self.args.darwin_test_deployment_version_osx = "10.9"
        self.args.darwin_test_deployment_version_ios = "15.0"
        self.args.darwin_test_deployment_version_tvos = "14.0"
        self.args.darwin_test_deployment_version_watchos = "6.0"
        self.args.darwin_test_deployment_version_xros = "1.0"
        self.args.enable_caching = False
        self.args.extra_swift_cmake_options = []

        # Create swift source dir
        os.makedirs(os.path.join(self.workspace.source_root, 'swift'),
                    exist_ok=True)

        llvm = LLVM(
            args=self.args,
            toolchain=self.toolchain,
            source_dir=os.path.join(self.workspace.source_root, 'llvm'),
            build_dir=os.path.join(self.workspace.build_root, 'llvm'))

        # Check merged vendor flags
        self.assertIn('-DSWIFT_VENDOR=Apple', llvm.cmake_options)
        self.assertIn('-DSWIFT_VERSION=6.0', llvm.cmake_options)

        # Check merged version flags
        self.assertIn('-DCLANG_COMPILER_VERSION=15.0.0', llvm.cmake_options)
        self.assertIn('-DSWIFT_COMPILER_VERSION=6.0.1', llvm.cmake_options)
        self.assertIn('-DSWIFT_TOOLCHAIN_VERSION=swiftlang-6.0.1',
                      llvm.cmake_options)

        # Check filtered flags from Swift product (e.g. benchmarks)
        self.assertIn('-DSWIFT_BENCHMARK_NUM_ONONE_ITERATIONS=3',
                      llvm.cmake_options)

        # Ensure no redundant -DSWIFT_VENDOR from Swift product's raw options
        swift_vendor_count = 0
        for opt in llvm.cmake_options:
            if '-DSWIFT_VENDOR=' in opt:
                swift_vendor_count += 1
        self.assertEqual(swift_vendor_count, 1)
