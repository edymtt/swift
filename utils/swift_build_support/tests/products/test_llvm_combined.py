# tests/products/test_llvm_combined.py --------------------------*- python -*-
#
# This source file is part of the Swift.org open source project
#
# Copyright (c) 2014 - 2017 Apple Inc. and the Swift project authors
# Licensed under Apache License v2.0 with Runtime Library Exception
#
# See https://swift.org/LICENSE.txt for license information
# See https://swift.org/CONTRIBUTORS.txt for the list of Swift project authors
# ----------------------------------------------------------------------------

import argparse
import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO

from swift_build_support import shell
from swift_build_support.products import LLVMCombined
from swift_build_support.toolchain import host_toolchain
from swift_build_support.workspace import Workspace

class LLVMCombinedTestCase(unittest.TestCase):

    def setUp(self):
        # Setup workspace
        tmpdir1 = os.path.realpath(tempfile.mkdtemp())
        tmpdir2 = os.path.realpath(tempfile.mkdtemp())
        os.makedirs(os.path.join(tmpdir1, 'llvm'))
        os.makedirs(os.path.join(tmpdir1, 'swift'))
        os.makedirs(os.path.join(tmpdir1, 'cmark'))
        os.makedirs(os.path.join(tmpdir1, 'libcxx'))

        self.workspace = Workspace(source_root=tmpdir1,
                                   build_root=tmpdir2)

        # Setup toolchain
        self.toolchain = host_toolchain()
        self.toolchain.cc = '/path/to/cc'
        self.toolchain.cxx = '/path/to/cxx'

        # Setup args
        self.args = argparse.Namespace(
            llvm_targets_to_build='X86',
            llvm_assertions=True,
            compiler_vendor='none',
            clang_compiler_version=None,
            clang_user_visible_version=None,
            use_linker=None,
            build_swift=False,
            swift_user_visible_version='5.0',
            swift_compiler_version=None,
            enable_tsan_runtime=False,
            benchmark=False,
            benchmark_num_onone_iterations=3,
            benchmark_num_o_iterations=3,
            force_optimized_typechecker=False,
            enable_stdlibcore_exclusivity_checking=False,
            enable_experimental_differentiable_programming=False,
            enable_experimental_concurrency=False,
            enable_experimental_cxx_interop=False,
            enable_experimental_distributed=False,
            swift_enable_backtracing=False,
            enable_experimental_observation=False,
            enable_synchronization=False,
            enable_volatile=False,
            enable_runtime_module=False,
            build_swift_stdlib_static_print=False,
            build_swift_stdlib_unicode_data=True,
            build_embedded_stdlib=True,
            build_embedded_stdlib_cross_compiling=False,
            swift_freestanding_is_darwin=False,
            build_swift_private_stdlib=True,
            swift_tools_ld64_lto_codegen_only_for_supporting_targets=False,
            build_stdlib_docs=False,
            swift_pedantic_diagnostics=False,
            enable_experimental_parser_validation=False,
            swift_debuginfo_non_lto_args=None,
            enable_new_runtime_build=False,
            darwin_test_deployment_version_osx="10.9",
            darwin_test_deployment_version_ios="15.0",
            darwin_test_deployment_version_tvos="14.0",
            darwin_test_deployment_version_watchos="6.0",
            darwin_test_deployment_version_xros="1.0",
            enable_caching=False,
            extra_swift_cmake_options=[],
            extra_llvm_cmake_options=[],
            lto_type=None,
            bootstrapping_mode='hosttools',
            caching_cas_path=None
        )

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

    def test_llvm_combined_without_swift(self):
        self.args.build_swift = False
        llvm_combined = LLVMCombined(
            args=self.args,
            toolchain=self.toolchain,
            source_dir=os.path.join(self.workspace.source_root, 'llvm'),
            build_dir=os.path.join(self.workspace.build_root, 'llvm'))
        
        self.assertNotIn('-DSWIFT_VENDOR=Apple', llvm_combined.cmake_options)
        self.assertNotIn('-DSWIFT_VERSION=5.0', llvm_combined.cmake_options)

    def test_llvm_combined_with_swift(self):
        self.args.build_swift = True
        self.args.compiler_vendor = 'apple'
        self.args.swift_user_visible_version = '6.0'
        self.args.swift_compiler_version = '6.0.1'
        self.args.clang_compiler_version = '15.0.0'
        self.args.benchmark = True
        
        llvm_combined = LLVMCombined(
            args=self.args,
            toolchain=self.toolchain,
            source_dir=os.path.join(self.workspace.source_root, 'llvm'),
            build_dir=os.path.join(self.workspace.build_root, 'llvm'))

        # Check merged vendor flags
        self.assertIn('-DSWIFT_VENDOR=Apple', llvm_combined.cmake_options)
        self.assertIn('-DSWIFT_VERSION=6.0', llvm_combined.cmake_options)
        
        # Check merged version flags
        self.assertIn('-DCLANG_COMPILER_VERSION=15.0.0', llvm_combined.cmake_options)
        self.assertIn('-DSWIFT_COMPILER_VERSION=6.0.1', llvm_combined.cmake_options)
        self.assertIn('-DSWIFT_TOOLCHAIN_VERSION=swiftlang-6.0.1', llvm_combined.cmake_options)

        # Check filtered flags from Swift product (e.g. benchmarks)
        self.assertIn('-DSWIFT_BENCHMARK_NUM_ONONE_ITERATIONS=3', llvm_combined.cmake_options)
        
        # Ensure no redundant -DSWIFT_VENDOR from Swift product's raw options
        swift_vendor_count = 0
        for opt in llvm_combined.cmake_options:
            if '-DSWIFT_VENDOR=' in opt:
                swift_vendor_count += 1
        self.assertEqual(swift_vendor_count, 1)

if __name__ == '__main__':
    unittest.main()
