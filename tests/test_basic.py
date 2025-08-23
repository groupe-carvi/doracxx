#!/usr/bin/env python3
"""
Test script for doracxx - Independent version
Tests basic doracxx functionality with the simple-node example
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
            # Truncate output for readability
            output = result.stdout.strip()
            if len(output) > 500:
                output = output[:500] + "... (truncated)"
            print(f"Output: {output}")
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
    print("🧪 Testing doracxx - Independent version")
    print("=" * 60)
    
    # Move to package directory
    script_dir = Path(__file__).resolve().parent
    package_dir = script_dir.parent
    os.chdir(package_dir)
    
    print(f"📁 Working directory: {package_dir}")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Help
    total_tests += 1
    if run_command([
        "python", "-m", "doracxx.cli", "help"
    ], "Display help with doracxx"):
        tests_passed += 1
    
    # Test 2: Check example structure
    total_tests += 2
    if check_file_exists("examples/simple-node/src/node.cc", "Example C++ source"):
        tests_passed += 1
    if check_file_exists("examples/simple-node/include/simple_processor.h", "Example header"):
        tests_passed += 1
    
    # Test 3: Check package structure
    total_tests += 2
    if check_file_exists("doracxx/cli.py", "CLI script"):
        tests_passed += 1
    if check_file_exists("doracxx/build-cxx-node.py", "Build script"):
        tests_passed += 1
    
    # Note: Real compilation tests require a Dora environment
    # and are not included in this basic test
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 Basic test summary: {tests_passed}/{total_tests} passed")
    
    if tests_passed == total_tests:
        print("🎉 All basic tests passed!")
        print("💡 To test full compilation, use:")
        print("   doracxx build --node-dir examples/simple-node --profile release --out simple-node")
        return 0
    else:
        print("⚠️  Some tests failed. Check the configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
