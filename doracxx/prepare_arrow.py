#!/usr/bin/env python3
"""Prepare Apache Arrow checkout and build the C++ library.

This script will:
- clone or update Apache Arrow into global cache directory (~/.doracxx/arrow)
- build the Arrow C++ library with minimal dependencies for doracxx usage
- install the library in the cache for reuse across projects

The goal is to resolve Arrow (sources + built library) before node builds
while minimizing compilation time by building only what's needed for C++ nodes.
Uses a global cache to share dependencies between projects.
"""

import argparse
import subprocess
from pathlib import Path
import os
import shutil
import json
import urllib.request
import urllib.error

# Import cache functions with proper path handling for different execution contexts
try:
    from .cache import get_doracxx_cache_dir, get_arrow_cache_path
except ImportError:
    # When run directly, import from the same directory
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from cache import get_doracxx_cache_dir, get_arrow_cache_path


def get_latest_arrow_release():
    """Get the latest stable Arrow release tag from GitHub API"""
    try:
        url = "https://api.github.com/repos/apache/arrow/releases/latest"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            tag_name = data.get("tag_name", "apache-arrow-21.0.0")  # fallback
            print(f"Latest Arrow release: {tag_name}")
            return tag_name
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not fetch latest Arrow release ({e}), using fallback")
        return "apache-arrow-21.0.0"  # fallback to known stable version


def git_clone_or_update(url: str, dest: Path, rev: str | None):
    """Clone or update Apache Arrow repository"""
    dest = dest.resolve()
    if dest.exists():
        print(f"Arrow already present at {dest}, fetching updates")
        try:
            subprocess.check_call(["git", "-C", str(dest), "fetch", "--all"], stdout=subprocess.DEVNULL)
            if rev:
                subprocess.check_call(["git", "-C", str(dest), "checkout", rev])
            else:
                # Get latest stable release if no revision specified
                latest_rev = get_latest_arrow_release()
                subprocess.check_call(["git", "-C", str(dest), "checkout", latest_rev]) 
        except subprocess.CalledProcessError:
            print("warning: git update failed, continuing with existing checkout")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", url, str(dest)]
    if rev:
        cmd += ["--branch", rev]
    else:
        # If no revision specified, clone and then checkout latest stable release
        subprocess.check_call(cmd)
        latest_rev = get_latest_arrow_release()
        subprocess.check_call(["git", "-C", str(dest), "checkout", latest_rev])
        return dest
    subprocess.check_call(cmd)
    return dest


def run(cmd, cwd=None, env=None, check=True):
    """Execute a command with proper output management"""
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, env=env, check=check)


def detect_cmake_generator():
    """Detect the best CMake generator for the current platform"""
    # Check if Ninja is available (preferred for faster builds)
    if shutil.which("ninja"):
        return "Ninja"
    elif os.name == "nt":
        # On Windows, prefer Visual Studio if available
        try:
            result = subprocess.run(
                ["cmake", "--help"], 
                capture_output=True, text=True, check=True
            )
            if "Visual Studio" in result.stdout:
                return None  # Let CMake choose the default VS generator
        except subprocess.CalledProcessError:
            pass
        return "MinGW Makefiles"
    else:
        # On Unix-like systems, use Unix Makefiles
        return "Unix Makefiles"


def build_arrow_cpp(repo: Path, profile: str, install_dir: Path):
    """Build Arrow C++ library with minimal configuration optimized for doracxx"""
    cpp_dir = repo / "cpp"
    if not cpp_dir.exists():
        raise RuntimeError(f"Arrow C++ directory not found: {cpp_dir}")
    
    build_dir = cpp_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    # Determine build type
    build_type = "Release" if profile == "release" else "Debug"
    
    # Detect CMake generator
    generator = detect_cmake_generator()
    
    print(f"Building Arrow C++ library ({build_type})...")
    
    # Configure CMake with minimal Arrow features for faster builds
    cmake_args = [
        "cmake",
        f"-DCMAKE_BUILD_TYPE={build_type}",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        
        # Core Arrow features - enable minimal set
        "-DARROW_BUILD_SHARED=ON",
        "-DARROW_BUILD_STATIC=OFF",  # Only shared libs to reduce build time
        "-DARROW_COMPUTE=ON",        # Core compute functionality
        "-DARROW_CSV=ON",           # CSV support
        "-DARROW_FILESYSTEM=ON",    # Filesystem operations
        "-DARROW_JSON=ON",          # JSON support
        
        # Disable heavy features to speed up build
        "-DARROW_DATASET=OFF",
        "-DARROW_FLIGHT=OFF",
        "-DARROW_GANDIVA=OFF",
        "-DARROW_HDFS=OFF",
        "-DARROW_JEMALLOC=OFF",
        "-DARROW_MIMALLOC=OFF",
        "-DARROW_PARQUET=OFF",      # Disable Parquet for faster builds
        "-DARROW_PLASMA=OFF",
        "-DARROW_PYTHON=OFF",
        "-DARROW_S3=OFF",
        "-DARROW_WITH_BROTLI=OFF",
        "-DARROW_WITH_BZ2=OFF",
        "-DARROW_WITH_LZ4=OFF",
        "-DARROW_WITH_SNAPPY=OFF",
        "-DARROW_WITH_ZLIB=OFF",
        "-DARROW_WITH_ZSTD=OFF",
        
        # Testing and benchmarks - disable for faster builds
        "-DARROW_BUILD_TESTS=OFF",
        "-DARROW_BUILD_BENCHMARKS=OFF",
        "-DARROW_BUILD_EXAMPLES=OFF",
        "-DARROW_BUILD_INTEGRATION=OFF",
        
        # Reduce dependencies
        "-DARROW_DEPENDENCY_SOURCE=BUNDLED",  # Use bundled dependencies
        "-DARROW_VERBOSE_THIRDPARTY_BUILD=OFF",

        # Additional options to prevent hanging
        "-DCMAKE_POLICY_DEFAULT_CMP0077=NEW",
        "-DBUILD_TESTING=OFF",
        # Force non-interactive mode and reduce verbosity
        "-DCMAKE_INSTALL_MESSAGE=LAZY",
        "-DCMAKE_VERBOSE_MAKEFILE=OFF",
        "-DCMAKE_RULE_MESSAGES=OFF",
        "-DCMAKE_TARGET_MESSAGES=OFF",
    ]
    
    # Add Windows-specific CMake flags to avoid compilation conflicts
    if os.name == "nt":
        cmake_args.extend([
            "-DCMAKE_CXX_FLAGS=-DNOMINMAX -DWIN32_LEAN_AND_MEAN -D_CRT_SECURE_NO_WARNINGS",
            "-DCMAKE_C_FLAGS=-DNOMINMAX -DWIN32_LEAN_AND_MEAN -D_CRT_SECURE_NO_WARNINGS"
        ])
    
    # Add generator if detected
    if generator:
        cmake_args.extend(["-G", generator])
    
    cmake_args.append(str(cpp_dir))
    
    print(f"    [CMAKE] Configure: {' '.join(cmake_args)}")
    run(cmake_args, cwd=build_dir)
    
    # Build Arrow
    build_args = ["cmake", "--build", ".", "--config", build_type]
    
    # Add parallel jobs if available
    parallel_jobs = os.cpu_count()
    if parallel_jobs and parallel_jobs > 1:
        if generator == "Ninja":
            build_args.extend(["-j", str(parallel_jobs)])
        else:
            build_args.extend(["--parallel", str(parallel_jobs)])
    
    print(f"    [CMAKE] Build: {' '.join(build_args)}")
    run(build_args, cwd=build_dir, check=True)
    
    # Install Arrow
    install_args = ["cmake", "--install", ".", "--config", build_type]
    print(f"    [CMAKE] Install: {' '.join(install_args)}")
    run(install_args, cwd=build_dir, check=True)
    
    return True


def verify_arrow_installation(install_dir: Path):
    """Verify that Arrow was properly installed"""
    # Check for essential files
    include_dir = install_dir / "include" / "arrow"
    lib_dir = install_dir / "lib"
    
    if not include_dir.exists():
        raise RuntimeError(f"Arrow include directory not found: {include_dir}")
    
    if not lib_dir.exists():
        raise RuntimeError(f"Arrow lib directory not found: {lib_dir}")
    
    # Check for core headers
    essential_headers = ["api.h", "array.h", "buffer.h", "type.h"]
    for header in essential_headers:
        header_path = include_dir / header
        if not header_path.exists():
            print(f"Warning: Expected Arrow header not found: {header_path}")
    
    # Check for library files
    lib_patterns = ["*arrow*"]
    found_libs = []
    for pattern in lib_patterns:
        found_libs.extend(lib_dir.glob(pattern))
    
    if not found_libs:
        raise RuntimeError(f"No Arrow libraries found in: {lib_dir}")
    
    print(f"Arrow installation verified:")
    print(f"  Include dir: {include_dir}")
    print(f"  Lib dir: {lib_dir}")
    print(f"  Found libraries: {[lib.name for lib in found_libs[:3]]}...")  # Show first 3
    
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arrow-git", default="https://github.com/apache/arrow.git")
    p.add_argument("--arrow-rev", default=None, help="Git revision/tag/branch to checkout (default: latest stable release from GitHub)")
    p.add_argument("--profile", choices=("debug", "release"), default="debug")
    p.add_argument("--force-rebuild", action="store_true",
                   help="Force rebuild even if Arrow is already installed")
    p.add_argument("--use-local", action="store_true",
                   help="Use local third_party/arrow instead of global cache (legacy mode)")
    p.add_argument("--create-symlink", action="store_true",
                   help="Create symlink from third_party/arrow to global cache for backward compatibility")
    args = p.parse_args()

    # If no specific revision is provided, get the latest stable release
    if args.arrow_rev is None:
        args.arrow_rev = get_latest_arrow_release()
        print(f"Using latest stable Arrow release: {args.arrow_rev}")

    if args.use_local:
        # Legacy mode: use third_party/arrow in current project
        vendor = Path("third_party") / "arrow"
        install_dir = vendor / "install"
        print("Prepare Arrow in (local mode):", vendor)
    else:
        # New mode: use global cache with version-specific directories
        vendor = get_arrow_cache_path(args.arrow_git, args.arrow_rev)
        install_dir = vendor / "install"
        print("Prepare Arrow in (global cache):", vendor)
        
        # Optionally create symlink from third_party/arrow to cache for backward compatibility
        if args.create_symlink:
            local_vendor = Path("third_party") / "arrow"
            local_vendor.parent.mkdir(exist_ok=True)
            
            if not local_vendor.exists():
                try:
                    if os.name == "nt":
                        # Windows: use junction (works without admin privileges)
                        subprocess.run(["cmd", "/c", "mklink", "/J", str(local_vendor), str(vendor)], 
                                     check=True, capture_output=True)
                    else:
                        # Unix: use symlink
                        local_vendor.symlink_to(vendor, target_is_directory=True)
                    print(f"Created symlink: {local_vendor} -> {vendor}")
                except (subprocess.CalledProcessError, OSError) as e:
                    print(f"Warning: could not create symlink ({e})")

    # Check if Arrow is already built and installed
    if install_dir.exists() and not args.force_rebuild:
        try:
            verify_arrow_installation(install_dir)
            print("Arrow already built and verified. Use --force-rebuild to rebuild.")
            return
        except RuntimeError as e:
            print(f"Arrow installation verification failed: {e}")
            print("Rebuilding Arrow...")

    # Clone or update Arrow repository
    repo = git_clone_or_update(args.arrow_git, vendor, args.arrow_rev)
    
    # Build Arrow C++ library
    try:
        success = build_arrow_cpp(repo, args.profile, install_dir)
        if success:
            verify_arrow_installation(install_dir)
            print("\nArrow preparation completed successfully!")
            print(f"Installation directory: {install_dir}")
            print(f"Include directory: {install_dir / 'include'}")
            print(f"Library directory: {install_dir / 'lib'}")
        else:
            print("Arrow build failed!")
            return 1
            
    except Exception as e:
        print(f"Error building Arrow: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
