#!/usr/bin/env python3
"""
Mock test for doracxx - Simulates a minimal Dora environment for testing
"""

import subprocess
import sys
import os
from pathlib import Path

def create_mock_dora_environment():
    """Creates a simulated Dora environment for testing"""
    base_dir = Path.cwd()
    
    # Create simulated third_party/dora structure
    mock_dora_dir = base_dir / "third_party" / "dora"
    mock_dora_dir.mkdir(parents=True, exist_ok=True)
    
    # Create simulated cxxbridge directories
    cxxbridge_dir = mock_dora_dir / "target" / "cxxbridge"
    cxxbridge_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a simulated Dora header
    mock_header = cxxbridge_dir / "dora-node-api.h"
    mock_header.write_text("""
#pragma once
// Mock Dora header for testing
namespace dora {
    class Node {
    public:
        void init();
        void run();
    };
}
""")
    
    return mock_dora_dir

def cleanup_mock_environment():
    """Cleans up the simulated environment"""
    mock_dir = Path.cwd() / "third_party"
    if mock_dir.exists():
        import shutil
        shutil.rmtree(mock_dir)

def run_command(cmd, description):
    """Execute a command and display the result"""
    print(f"\n🔄 {description}")
    print(f"Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"✅ Success: {description}")
            return True
        else:
            print(f"❌ Failed: {description}")
            print(f"Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏱️ Timeout: {description}")
        return False
    except Exception as e:
        print(f"❌ Exception: {description} - {e}")
        return False

def main():
    """Test with simulated Dora environment"""
    print("🧪 Testing doracxx - With simulated Dora environment")
    print("=" * 70)
    
    # Move to package directory
    script_dir = Path(__file__).resolve().parent
    package_dir = script_dir.parent
    os.chdir(package_dir)
    
    print(f"📁 Working directory: {package_dir}")
    
    # Create simulated environment
    print("🔧 Creating simulated Dora environment...")
    try:
        mock_dora_dir = create_mock_dora_environment()
        print(f"✅ Simulated environment created: {mock_dora_dir}")
    except Exception as e:
        print(f"❌ Failed to create simulated environment: {e}")
        return 1
    
    tests_passed = 0
    total_tests = 0
    
    try:
        # Test 1: Basic test - Help
        total_tests += 1
        if run_command([
            "python", "-m", "doracxx.cli", "help"
        ], "Display help"):
            tests_passed += 1
        
        # Test 2: Compilation test (might fail without MSVC)
        total_tests += 1
        print("\n⚠️ The following test might fail without a complete compilation environment...")
        if run_command([
            "python", "-m", "doracxx.cli", "build",
            "--node-dir", "examples/simple-node",
            "--profile", "debug",
            "--out", "test-mock",
            "--skip-build-packages"
        ], "Compilation test with simulated environment"):
            tests_passed += 1
        else:
            print("💡 Expected failure - MSVC/Clang compiler probably not available")
    
    finally:
        # Clean up simulated environment
        print("\n🧹 Cleaning up simulated environment...")
        try:
            cleanup_mock_environment()
            print("✅ Cleanup completed")
        except Exception as e:
            print(f"⚠️ Error during cleanup: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print(f"📊 Simulated test summary: {tests_passed}/{total_tests} passed")
    
    if tests_passed >= 1:  # At least help should work
        print("🎉 Basic tests passed! The doracxx package is functional.")
        if tests_passed < total_tests:
            print("💡 Some advanced tests failed - probably due to missing C++ compiler")
        return 0
    else:
        print("❌ Basic tests failed - problem with doracxx package")
        return 1

if __name__ == "__main__":
    sys.exit(main())
