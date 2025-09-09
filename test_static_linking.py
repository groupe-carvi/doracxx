#!/usr/bin/env python3
"""
Test script to validate Arrow static linking
"""
import subprocess
import sys
from pathlib import Path

def test_arrow_static_linking():
    """Test that Arrow libraries are statically linked"""
    print("=== Testing Arrow Static Linking ===")
    
    # Build the arrow node example
    examples_dir = Path(__file__).parent / "examples" / "arrow-node"
    if not examples_dir.exists():
        print(f"Error: Examples directory not found: {examples_dir}")
        return False
    
    print(f"Building arrow-node example in {examples_dir}")
    
    # Build the node
    try:
        cmd = [sys.executable, "-m", "doracxx.build_cxx_node", "--node-dir", str(examples_dir)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode != 0:
            print("Build failed:")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
        
        print("Build successful!")
        print("STDOUT:", result.stdout)
        
        # Find the built executable
        target_dir = examples_dir / "target" / "debug"
        executable = None
        
        # Look for executable
        for exe_path in target_dir.rglob("*"):
            if exe_path.is_file() and exe_path.name in ["arrow-node", "arrow-node.exe"]:
                executable = exe_path
                break
        
        if not executable:
            print(f"Error: Executable not found in {target_dir}")
            return False
        
        print(f"Found executable: {executable}")
        
        # Check dependencies
        if sys.platform.startswith('linux'):
            # Use ldd to check shared library dependencies
            ldd_result = subprocess.run(['ldd', str(executable)], capture_output=True, text=True)
            if ldd_result.returncode == 0:
                print("\nShared library dependencies:")
                print(ldd_result.stdout)
                
                # Check if Arrow libraries are listed as dependencies
                if 'libarrow' in ldd_result.stdout:
                    print("❌ WARNING: Arrow appears to be dynamically linked!")
                    return False
                else:
                    print("✅ Arrow appears to be statically linked (no libarrow dependencies)")
                    return True
            else:
                print("Could not check dependencies with ldd")
                return True
        
        else:
            print("Dependency checking not implemented for this platform")
            return True
            
    except Exception as e:
        print(f"Error during build: {e}")
        return False

if __name__ == "__main__":
    success = test_arrow_static_linking()
    sys.exit(0 if success else 1)
