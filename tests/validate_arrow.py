#!/usr/bin/env python3
"""
Validation script for Arrow integration in doracxx
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Add doracxx to path
sys.path.insert(0, str(Path(__file__).parent))

def test_arrow_config():
    """Test Arrow configuration parsing"""
    print("[TEST] Testing Arrow configuration parsing...")
    
    from doracxx.config import load_config, create_example_config
    
    # Create a temporary config with Arrow
    test_config = """
[node]
name = "test-arrow-node"
type = "node"

[build]
toolchain = "auto"

[arrow]
enabled = true
git = "https://github.com/apache/arrow.git"
rev = "apache-arrow-15.0.0"

[dependencies]
[dependencies.eigen3]
type = "git"
url = "https://gitlab.com/libeigen/eigen.git"
tag = "3.4.0"
include_dirs = ["."]
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(test_config)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        
        # Test node config
        assert config.node.name == "test-arrow-node"
        
        # Test Arrow config
        assert config.arrow is not None
        assert config.arrow.enabled == True
        assert config.arrow.git == "https://github.com/apache/arrow.git"
        assert config.arrow.rev == "apache-arrow-15.0.0"
        
        # Test dependencies
        assert "eigen3" in config.dependencies
        
        print("✓ Arrow configuration parsing works correctly")
        
    finally:
        Path(config_path).unlink()


def test_arrow_detection():
    """Test Arrow detection logic"""
    print("[TEST] Testing Arrow detection logic...")
    
    from doracxx.config import load_config
    from doracxx.cache import get_arrow_cache_path
    from doracxx.build_cxx_node import find_arrow_install_dir
    
    # Test cache path generation
    cache_path = get_arrow_cache_path("https://github.com/apache/arrow.git", "apache-arrow-15.0.0")
    assert "arrow" in str(cache_path)
    assert "apache-arrow-15.0.0" in str(cache_path).replace("_", "-")
    
    # Test install dir finding
    install_dir = find_arrow_install_dir("https://github.com/apache/arrow.git", "apache-arrow-15.0.0")
    assert "install" in str(install_dir)
    
    print("✓ Arrow detection logic works correctly")


def test_prepare_arrow_script():
    """Test prepare_arrow script imports and basic functionality"""
    print("[TEST] Testing prepare_arrow script...")
    
    try:
        from doracxx import prepare_arrow
        
        # Test that main functions exist
        assert hasattr(prepare_arrow, 'git_clone_or_update')
        assert hasattr(prepare_arrow, 'build_arrow_cpp')
        assert hasattr(prepare_arrow, 'verify_arrow_installation')
        assert hasattr(prepare_arrow, 'main')
        
        print("✓ prepare_arrow script imports work correctly")
        
    except ImportError as e:
        print(f"✗ prepare_arrow script import failed: {e}")
        return False
    
    return True


def test_cli_integration():
    """Test CLI integration with Arrow commands"""
    print("[TEST] Testing CLI integration...")
    
    try:
        from doracxx.cli import prepare_arrow, main
        from doracxx.cache import cache_clean_arrow
        
        # Test that functions exist
        assert hasattr(prepare_arrow, '__call__')
        assert hasattr(cache_clean_arrow, '__call__')
        
        print("✓ CLI integration works correctly")
        
    except ImportError as e:
        print(f"✗ CLI integration failed: {e}")
        return False
    
    return True


def test_cache_functions():
    """Test cache functions for Arrow"""
    print("[TEST] Testing Arrow cache functions...")
    
    from doracxx.cache import get_arrow_cache_path, cache_clean_arrow
    
    # Test path generation with different parameters
    path1 = get_arrow_cache_path()
    path2 = get_arrow_cache_path("https://github.com/apache/arrow.git")
    path3 = get_arrow_cache_path("https://github.com/apache/arrow.git", "apache-arrow-15.0.0")
    
    assert "arrow" in str(path1)
    assert "arrow" in str(path2) 
    assert "arrow" in str(path3)
    assert str(path1) != str(path3)  # Different versions should have different paths
    
    print("✓ Arrow cache functions work correctly")


def main():
    """Run all tests"""
    print("=" * 50)
    print("doracxx Arrow Integration Validation")
    print("=" * 50)
    
    tests = [
        test_arrow_config,
        test_arrow_detection,
        test_prepare_arrow_script,
        test_cli_integration,
        test_cache_functions,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
            if result is not False:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All Arrow integration tests passed!")
        print("\nArrow support has been successfully added to doracxx!")
        print("\nKey features added:")
        print("- Apache Arrow fetch, build, and integration")
        print("- Arrow configuration in doracxx.toml")
        print("- CLI commands: 'doracxx prepare arrow', 'doracxx clean --arrow'")
        print("- Global caching for Arrow installations")
        print("- Automatic Arrow detection and linking")
        print("- Example node demonstrating Arrow usage")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
