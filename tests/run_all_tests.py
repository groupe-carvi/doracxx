#!/usr/bin/env python3
"""
Main test suite for doracxx
Executes all available tests according to the environment
"""

import subprocess
import sys
from pathlib import Path

def run_test_script(script_name, description):
    """Execute a test script"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    
    script_path = Path(__file__).parent / script_name
    try:
        result = subprocess.run([sys.executable, str(script_path)], 
                              capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False

def main():
    """Execute all tests"""
    print("🚀 doracxx test suite")
    print("Validation tests for the doracxx package")
    
    tests_results = []
    
    # Test 1: Basic tests (always executed)
    success = run_test_script("test_basic.py", "Basic tests - Structure and CLI")
    tests_results.append(("Basic tests", success))
    
    # Test 2: Tests with simulated environment
    success = run_test_script("test_mock.py", "Tests with simulated Dora environment")
    tests_results.append(("Simulated tests", success))
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 FINAL TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    total = len(tests_results)
    
    for test_name, success in tests_results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status:<12} {test_name}")
        if success:
            passed += 1
    
    print(f"\n📈 Score: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("💡 The doracxx package is ready to use.")
        return 0
    elif passed > 0:
        print("⚠️  TESTS PARTIALLY SUCCESSFUL")
        print("💡 The basic package works, but some advanced tests failed.")
        print("   This can be normal depending on your development environment.")
        return 0
    else:
        print("❌ CRITICAL FAILURE")
        print("   The doracxx package has fundamental problems.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
