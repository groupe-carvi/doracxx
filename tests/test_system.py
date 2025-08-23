#!/usr/bin/env python3
"""
Test script for doracxx
Verifies that the compilation system works correctly
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Execute a command and display the result"""
    print(f"\n🔄 {description}")
    print(f"Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ Success: {description}")
        if result.stdout.strip():
            print(f"Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {description}")
        print(f"Error: {e.stderr}")
        return False

def check_file_exists(path, description):
    """Check if a file exists"""
    if Path(path).exists():
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ Missing {description}: {path}")
        return False

def main():
    """Main test function"""
    print("🧪 doracxx Test")
    print("=" * 50)
    
    # Check structure - use package directory
    base_dir = Path(__file__).resolve().parent.parent
    os.chdir(base_dir)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Help
    total_tests += 1
    if run_command([
        "uv", "run", "doracxx", "help"
    ], "Display help with doracxx"):
        tests_passed += 1
    
    # Test 2: Release compilation
    total_tests += 1
    if run_command([
        "uv", "run", "doracxx", "build",
        "--node-dir", "examples/simple-node",
        "--profile", "release",
        "--out", "test-release",
        "--skip-build-packages"
    ], "Release mode compilation"):
        tests_passed += 1
    
    # Test 3: Debug compilation
    total_tests += 1
    if run_command([
        "uv", "run", "doracxx", "build",
        "--node-dir", "examples/simple-node", 
        "--profile", "debug",
        "--out", "test-debug",
        "--skip-build-packages"
    ], "Debug mode compilation"):
        tests_passed += 1
    
    # Test 4: Executable verification
    total_tests += 2
    if check_file_exists("target/release/test-release.exe", "Release executable"):
        tests_passed += 1
    if check_file_exists("target/debug/test-debug.exe", "Debug executable"):
        tests_passed += 1
    
    # Test 5: Project structure verification
    total_tests += 3
    if check_file_exists("examples/simple-node/deps/dora-node-api.h", "Copied Dora header"):
        tests_passed += 1
    if check_file_exists("examples/simple-node/src/node.cc", "C++ source"):
        tests_passed += 1
    if check_file_exists("doracxx/cli.py", "CLI script"):
        tests_passed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test summary: {tests_passed}/{total_tests} passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! The system works perfectly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
