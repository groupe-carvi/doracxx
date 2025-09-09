#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
import tarfile
from pathlib import Path
import tempfile
import argparse
from typing import Optional, Union, List

# Import cache functions with proper path handling for different execution contexts
try:
    from .cache import get_doracxx_cache_dir, get_dora_cache_path, get_arrow_cache_path
    from .config import load_config, DoracxxConfig, Toolchain, find_project_root
    from .dependencies import setup_dependencies
except ImportError:
    # When run directly, import from the same directory
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from cache import get_doracxx_cache_dir, get_dora_cache_path, get_arrow_cache_path
    from config import load_config, DoracxxConfig, Toolchain, find_project_root
    from dependencies import setup_dependencies


def find_dora_target_dir(dora_git: str | None = None, dora_rev: str | None = None):
    """Find Dora target directory, checking cache first, then local."""
    # Check global cache first (version-specific)
    cache_target = get_dora_cache_path(dora_git, dora_rev) / "target"
    if cache_target.exists():
        return str(cache_target)
    
    # Fallback: try the default latest cache if specific version not found
    if dora_git or dora_rev:
        default_cache_target = get_dora_cache_path() / "target"
        if default_cache_target.exists():
            return str(default_cache_target)
    
    # Fallback to local third_party (backward compatibility)
    project_root = find_project_root()
    local_target = project_root / "third_party" / "dora" / "target"
    if local_target.exists():
        return str(local_target)
    
    # Last resort: current workspace target
    return str(project_root / "target")


def find_arrow_install_dir(arrow_git: str | None = None, arrow_rev: str | None = None):
    """Find Arrow installation directory, checking cache first, then local."""
    # Check global cache first (version-specific)
    cache_install = get_arrow_cache_path(arrow_git, arrow_rev) / "install"
    if cache_install.exists():
        return str(cache_install)
    
    # Fallback: try the default latest cache if specific version not found
    if arrow_git or arrow_rev:
        default_cache_install = get_arrow_cache_path() / "install"
        if default_cache_install.exists():
            return str(default_cache_install)
    
    # Fallback to local third_party (backward compatibility)
    project_root = find_project_root()
    local_install = project_root / "third_party" / "arrow" / "install"
    if local_install.exists():
        return str(local_install)
    
    # Last resort: return expected path (will be created during preparation)
    return str(project_root / "third_party" / "arrow" / "install")


def ensure_dora_prepared(dora_git: str | None = None, dora_rev: str | None = None, profile: str = "debug"):
    """Ensure Dora is prepared and built. If not found, automatically prepare it."""
    import sys
    
    # Check if Dora target directory exists with cxxbridge artifacts
    dora_target_path = Path(find_dora_target_dir(dora_git, dora_rev))
    
    # Check for cxxbridge artifacts that indicate a successful Dora build
    cxxbridge_indicators = [
        dora_target_path / profile / "cxxbridge",
        dora_target_path / "cxxbridge"
    ]
    
    has_cxxbridge = any(p.exists() and any(p.iterdir()) for p in cxxbridge_indicators if p.exists())
    
    if not has_cxxbridge:
        print("[INFO] Dora not found or incomplete. Preparing Dora automatically...")
        
        # Import prepare_dora functionality
        try:
            from .prepare_dora import git_clone_or_update, build_workspace, build_manifests
            from .cache import get_dora_cache_path
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent))
            from prepare_dora import git_clone_or_update, build_workspace, build_manifests
            from cache import get_dora_cache_path
        
        # Determine the repository path
        vendor = get_dora_cache_path(dora_git, dora_rev)
        print(f"[CACHE] Preparing Dora in global cache: {vendor}")
        
        # Clone or update Dora repository
        dora_git_url = dora_git or "https://github.com/dora-rs/dora"
        repo = git_clone_or_update(dora_git_url, vendor, dora_rev)
        
        # Build essential C++ API packages
        print("[BUILD] Building essential C++ API packages...")
        ok = build_workspace(repo, profile)
        
        if not ok:
            print("[BUILD] Attempting targeted builds for C/C++ API crates...")
            build_manifests(repo, profile)
        
        print("[OK] Dora preparation completed")
        
        # Re-check the target directory
        new_target = find_dora_target_dir(dora_git, dora_rev)
        return new_target
    
    return str(dora_target_path)


def ensure_arrow_prepared(arrow_git: str | None = None, arrow_rev: str | None = None, profile: str = "debug"):
    """Ensure Arrow is prepared and built. If not found, automatically prepare it."""
    import sys
    
    # Check if Arrow installation directory exists with required files
    arrow_install_path = Path(find_arrow_install_dir(arrow_git, arrow_rev))
    
    # Check for Arrow artifacts that indicate a successful build
    arrow_indicators = [
        arrow_install_path / "include" / "arrow",
        arrow_install_path / "lib"
    ]
    
    has_arrow = all(p.exists() for p in arrow_indicators)
    
    # Additional check for actual library files
    if has_arrow:
        lib_dir = arrow_install_path / "lib"
        has_libs = any(lib_dir.glob("*arrow*"))
        has_arrow = has_arrow and has_libs
    
    if not has_arrow:
        print("[INFO] Arrow not found or incomplete. Preparing Arrow automatically...")
        
        # Import prepare_arrow functionality
        try:
            from .prepare_arrow import git_clone_or_update, build_arrow_cpp, verify_arrow_installation
            from .cache import get_arrow_cache_path
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent))
            from prepare_arrow import git_clone_or_update, build_arrow_cpp, verify_arrow_installation
            from cache import get_arrow_cache_path
        
        # Determine the repository path
        vendor = get_arrow_cache_path(arrow_git, arrow_rev)
        install_dir = vendor / "install"
        print(f"[CACHE] Preparing Arrow in global cache: {vendor}")
        
        # Clone or update Arrow repository
        arrow_git_url = arrow_git or "https://github.com/apache/arrow.git"
        repo = git_clone_or_update(arrow_git_url, vendor, arrow_rev)
        
        # Build Arrow C++ library
        print("[BUILD] Building Arrow C++ library...")
        try:
            success = build_arrow_cpp(repo, profile, install_dir)
            if success:
                verify_arrow_installation(install_dir)
                print("[OK] Arrow preparation completed")
            else:
                print("[ERROR] Arrow build failed")
                raise RuntimeError("Arrow build failed")
        except Exception as e:
            print(f"[ERROR] Arrow preparation failed: {e}")
            raise
        
        # Re-check the installation directory
        new_install = find_arrow_install_dir(arrow_git, arrow_rev)
        return new_install
    
    return str(arrow_install_path)


def git_clone(url, dest, rev=None):
    dest = Path(dest)
    if dest.exists():
        # try to fetch latest
        try:
            subprocess.check_call(["git", "-C", str(dest), "fetch", "--all"], stdout=subprocess.DEVNULL)
            if rev:
                subprocess.check_call(["git", "-C", str(dest), "checkout", rev])
            else:
                subprocess.check_call(["git", "-C", str(dest), "checkout", "main"]) 
        except Exception:
            pass
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", url, str(dest)]
    if rev:
        cmd += ["--branch", rev]
    subprocess.check_call(cmd)
    return dest


def run(cmd, cwd=None, env=None, capture_output=False, timeout=300, config=None):
    """Execute a command with proper output management.
    
    Args:
        cmd: Command to execute
        cwd: Working directory
        env: Environment variables
        capture_output: If True, capture and return output instead of streaming
        timeout: Timeout in seconds (default 5 minutes)
        config: DoracxxConfig for custom warning patterns
    
    Returns:
        subprocess.CompletedProcess if capture_output=True, None otherwise
    """
    print("$ ", " ".join(cmd))
    
    if capture_output:
        # For commands where we need to capture output
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            env=env, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result
    else:
        # For compilation commands that may produce large output
        # Use PIPE to avoid hanging on large outputs, but don't accumulate in memory
        process = subprocess.Popen(
            cmd, 
            cwd=cwd, 
            env=env, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
        
        try:
            # Stream output line by line to avoid memory accumulation
            if process.stdout:
                custom_patterns = config.build.warning_filter_patterns if config else None
                for line in iter(process.stdout.readline, ''):
                    # Only print important lines to reduce noise
                    line = line.rstrip()
                    if line and should_print_line(line, custom_patterns):
                        print(line)
            
            # Wait for process to complete with timeout
            process.wait(timeout=timeout)
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)
                
        except subprocess.TimeoutExpired:
            process.kill()
            raise subprocess.TimeoutExpired(cmd, timeout)
        finally:
            if process.stdout:
                process.stdout.close()


def should_print_line(line, custom_patterns=None):
    """Determine if a compiler output line should be printed.
    
    This filters out excessive warning spam while keeping important information.
    
    Args:
        line: The output line to check
        custom_patterns: Additional patterns to filter (list of strings)
    """
    line_lower = line.lower()
    
    # Always print errors
    if any(keyword in line_lower for keyword in ['error', 'fatal', 'failed', 'cannot']):
        return True
    
    # Print progress indicators
    if any(keyword in line_lower for keyword in ['building', 'compiling', 'linking', 'finished']):
        return True
    
    # Skip warning spam patterns commonly seen with MSVC templates
    warning_spam_patterns = [
        'warning c4996',  # MSVC deprecation warnings
        'warning c4244',  # Conversion warnings
        'warning c4267',  # Size conversion warnings
        'warning c4101',  # Unreferenced local variable
        'warning c4189',  # Local variable initialized but not referenced
        'note: see declaration of',  # MSVC note spam
        'note: see reference to',    # Template instantiation notes
    ]
    
    # Add custom patterns if provided
    if custom_patterns:
        warning_spam_patterns.extend(pattern.lower() for pattern in custom_patterns)
    
    for pattern in warning_spam_patterns:
        if pattern in line_lower:
            return False
    
    # For other warnings, only print occasionally to show progress
    if 'warning' in line_lower:
        # Use hash to consistently show some warnings but not all
        return hash(line) % 20 == 0  # Show ~5% of warnings
    
    return True


def build_package(pkg):
    try:
        run([os.environ.get("CARGO", "cargo"), "build", "--package", pkg])
        return True
    except subprocess.CalledProcessError:
        print(f"warning: failed to build package {pkg} (ignored)")
        return False


def build_manifest(manifest_path, profile="debug"):
    cmd = [os.environ.get("CARGO", "cargo"), "build", "--manifest-path", str(manifest_path)]
    if profile == "release":
        cmd.append("--release")
    try:
        run(cmd)
        return True
    except subprocess.CalledProcessError:
        print(f"warning: failed to build manifest {manifest_path} (ignored)")
        return False


def find_cxxbridge_artifacts(dora_target: Path, profile: str):
    """Return (include_dirs, generated_cc_files).

    include_dirs: list of directories to pass as -I (/I for MSVC)
    generated_cc_files: list of full paths to lib.rs.cc files to compile alongside node sources
    """
    include_dirs = []
    generated_cc = []

    # Candidate roots: target/<profile>/cxxbridge and target/cxxbridge
    cxxbridge_root_candidates = [dora_target / profile / "cxxbridge", dora_target / "cxxbridge"]
    for cxxbridge_root in cxxbridge_root_candidates:
        if cxxbridge_root.exists():
            # add the cxxbridge root itself so any top-level headers (like dora-node-api.h) are visible
            include_dirs.append(str(cxxbridge_root))
            for crate_dir in cxxbridge_root.iterdir():
                if crate_dir.is_dir():
                    # include crate root and its src if present
                    include_dirs.append(str(crate_dir))
                    src = crate_dir / "src"
                    if src.exists():
                        include_dirs.append(str(src))
                        ccpath = src / "lib.rs.cc"
                        if ccpath.exists():
                            generated_cc.append(str(ccpath))
                    # also include any crate-root .cc files (e.g., dora-node-api.cc)
                    for f in crate_dir.glob("*.cc"):
                        generated_cc.append(str(f))

    # Fallback: some cxxbridge outputs are placed under build/*/out/cxxbridge/crate/<crate>/src
    build_root = dora_target / profile / "build"
    if build_root.exists():
        for build_dir_entry in build_root.iterdir():
            out_dir = build_dir_entry / "out" / "cxxbridge" / "crate"
            if out_dir.exists():
                for crate_dir in out_dir.iterdir():
                    src = crate_dir / "src"
                    if src.exists():
                        include_dirs.append(str(src))
                        ccpath = src / "lib.rs.cc"
                        if ccpath.exists():
                            generated_cc.append(str(ccpath))

    # deduplicate while preserving order
    seen = set()
    include_dirs = [p for p in include_dirs if not (p in seen or seen.add(p))]
    seen = set()
    generated_cc = [p for p in generated_cc if not (p in seen or seen.add(p))]

    return include_dirs, generated_cc


def find_arrow_artifacts(arrow_install: Path):
    """Return (include_dirs, lib_dirs, libraries) for Arrow.

    include_dirs: list of directories to pass as -I (/I for MSVC)
    lib_dirs: list of directories to pass as -L (/LIBPATH for MSVC)
    libraries: list of library names to link against
    """
    include_dirs = []
    lib_dirs = []
    libraries = []

    # Arrow include directory
    arrow_include = arrow_install / "include"
    if arrow_include.exists():
        include_dirs.append(str(arrow_include))

    # Arrow library directory
    arrow_lib = arrow_install / "lib"
    if arrow_lib.exists():
        lib_dirs.append(str(arrow_lib))
        
        # Find Arrow libraries - prioritize static libraries for easier deployment
        static_libs = []
        shared_libs = []
        
        # Collect static libraries first (.a files on Unix, .lib files on Windows)
        for lib_file in arrow_lib.glob("libarrow*.a"):
            if lib_file.is_file():
                lib_name = lib_file.name[3:].split('.', 1)[0]  # Remove 'lib' prefix and extension
                static_libs.append(lib_name)
        
        # For Windows, look for .lib files (which can be static or import libraries)
        for lib_file in arrow_lib.glob("arrow*.lib"):
            if lib_file.is_file():
                lib_name = lib_file.name.split('.', 1)[0]
                static_libs.append(lib_name)
        
        # Collect shared libraries as fallback (.so files)
        for lib_file in arrow_lib.glob("libarrow*.so"):
            if lib_file.is_file():
                lib_name = lib_file.name[3:].split('.', 1)[0]  # Remove 'lib' prefix and extension
                shared_libs.append(lib_name)
        
        # Use static libraries if available, otherwise fall back to shared
        if static_libs:
            libraries.extend(static_libs)
            print(f"[ARROW] Using static libraries: {static_libs}")
        elif shared_libs:
            libraries.extend(shared_libs)
            print(f"[ARROW] Using shared libraries: {shared_libs}")
        else:
            print(f"[ARROW] Warning: No Arrow libraries found in {arrow_lib}")
        
        # Remove duplicates while preserving order
        seen = set()
        libraries = [x for x in libraries if not (x in seen or seen.add(x))]

    return include_dirs, lib_dirs, libraries


def compile_node(node_dir: Path, build_dir: Path, out_name: str, profile: str, dora_target: str, extras: list, config: DoracxxConfig | None = None, dora_git: str | None = None, dora_rev: str | None = None):
    # Extract Dora configuration from config if available
    final_dora_git = dora_git
    final_dora_rev = dora_rev
    if config and config.node:
        if config.node.dora_git:
            final_dora_git = config.node.dora_git
        if config.node.dora_rev:
            final_dora_rev = config.node.dora_rev
    
    # Ensure Dora is prepared with the requested version
    print("[INFO] Checking Dora preparation...")
    try:
        dora_target = ensure_dora_prepared(final_dora_git, final_dora_rev, profile)
        print(f"[OK] Dora target ready: {dora_target}")
    except Exception as e:
        print(f"[ERROR] Failed to prepare Dora automatically: {e}")
        print(f"Using fallback Dora target directory: {dora_target}")
    
    # On Windows, try to load MSVC environment (vcvarsall) so cl/link are visible
    if os.name == "nt":
        try:
            load_msvc_env()
        except Exception:
            # if it fails, we continue and rely on PATH / CXX
            pass

    # Determine compiler preference from config
    preferred_toolchain = None
    if config:
        preferred_toolchain = config.build.toolchain

    # Find a C++ compiler (prefer environment, then config preference, then common names)
    cc_env = os.environ.get("CXX") or os.environ.get("CXX_COMPILER")
    cc = None
    kind = None
    if cc_env and shutil.which(cc_env):
        cc = cc_env
        # heuristics for kind
        if cc_env.lower().endswith("cl.exe") or cc_env.lower().endswith("cl"):
            kind = "msvc"
    else:
        # Apply toolchain preference from config
        candidates = []
        if preferred_toolchain == Toolchain.MSVC or (preferred_toolchain == Toolchain.AUTO and os.name == "nt"):
            candidates = [("cl", "msvc"), ("clang-cl", "msvc"), ("clang++", "gcc"), ("g++", "gcc")]
        elif preferred_toolchain == Toolchain.CLANG:
            candidates = [("clang++", "gcc"), ("clang-cl", "msvc"), ("g++", "gcc"), ("cl", "msvc")]
        elif preferred_toolchain == Toolchain.GCC:
            candidates = [("g++", "gcc"), ("clang++", "gcc"), ("clang-cl", "msvc"), ("cl", "msvc")]
        else:  # AUTO or fallback
            if os.name == "nt":
                candidates = [("cl", "msvc"), ("clang-cl", "msvc"), ("clang++", "gcc"), ("g++", "gcc")]
            else:
                candidates = [("clang++", "gcc"), ("g++", "gcc")]
        
        for cand, k in candidates:
            p = shutil.which(cand)
            if p:
                cc = p
                kind = k
                break

    if not cc:
        # If no compiler found on Windows, try to install clang automatically
        auto_install = config.build.install_clang if config else False
        if os.name == "nt" and auto_install:
            print("No C++ compiler found; attempting to install clang automatically...")
            if ensure_clang_installed(install=True):
                # retry compiler detection after installation
                for cand, k in [("clang-cl", "msvc"), ("clang++", "gcc"), ("cl", "msvc"), ("g++", "gcc")]:
                    p = shutil.which(cand)
                    if p:
                        cc = p
                        kind = k
                        break
        
        if not cc:
            raise RuntimeError("no C++ compiler found (tried CXX env, cl, clang-cl, clang++, g++); install one or set CXX")

    # Discover all C/C++ source files in the node directory
    srcs = []
    
    # Check if sources are specified in config
    if config and hasattr(config.build, 'sources') and config.build.sources:
        # Use explicitly configured sources
        for src_pattern in config.build.sources:
            if "*" in src_pattern or "?" in src_pattern:
                # Pattern matching
                matched_files = list(node_dir.glob(src_pattern))
                srcs.extend(matched_files)
            else:
                # Direct file path
                src_path = node_dir / src_pattern
                if src_path.exists():
                    srcs.append(src_path)
    else:
        # Default behavior: discover all C/C++ files
        for pattern in ["**/*.cc", "**/*.cpp", "**/*.c"]:
            srcs.extend(node_dir.glob(pattern))
    
    # Apply exclude patterns if specified
    if config and hasattr(config.build, 'exclude_sources') and config.build.exclude_sources:
        import fnmatch
        excluded_srcs = []
        for src in srcs:
            relative_path = str(src.relative_to(node_dir))
            should_exclude = False
            for exclude_pattern in config.build.exclude_sources:
                if fnmatch.fnmatch(relative_path, exclude_pattern):
                    should_exclude = True
                    break
            if should_exclude:
                excluded_srcs.append(src)
                print(f"[EXCLUDE] Excluding source file: {relative_path}")
        
        # Remove excluded files
        for excluded in excluded_srcs:
            srcs.remove(excluded)
    
    if not srcs:
        raise RuntimeError("no C/C++ sources found in node dir (looked for .cc, .cpp, .c files)")
    
    # Use target/<profile>/ for ALL build artifacts (like Rust projects)
    # Use the project root directory, not the current working directory
    project_root = find_project_root(node_dir)
    workspace_target_dir = project_root / "target" / profile
    workspace_target_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories in target for organization
    target_build_dir = workspace_target_dir / "build"
    target_deps_dir = workspace_target_dir / "deps" 
    target_include_dir = workspace_target_dir / "include"
    target_build_dir.mkdir(exist_ok=True)
    target_deps_dir.mkdir(exist_ok=True)
    target_include_dir.mkdir(exist_ok=True)
    
    # Setup dependencies if config is provided
    dep_manager = None
    if config and config.dependencies:
        print("[DEPS] Setting up dependencies...")
        dep_manager = setup_dependencies(config, node_dir, workspace_target_dir)
    
    # Check if Arrow is needed (either explicitly configured or from dependencies)
    arrow_git = None
    arrow_rev = None
    arrow_needed = False
    
    # Check if Arrow is configured in arrow config
    if config and config.arrow and config.arrow.enabled:
        arrow_git = config.arrow.git
        arrow_rev = config.arrow.rev
        arrow_needed = True
    
    # Check if Arrow is in dependencies
    if config and config.dependencies:
        for dep_name, dep_config in config.dependencies.items():
            if 'arrow' in dep_name.lower():
                arrow_needed = True
                break
    
    # Prepare Arrow if needed
    arrow_include_dirs = []
    arrow_lib_dirs = []
    arrow_libraries = []
    if arrow_needed:
        try:
            print("[INFO] Checking Arrow preparation...")
            arrow_install = ensure_arrow_prepared(arrow_git, arrow_rev, profile)
            arrow_include_dirs, arrow_lib_dirs, arrow_libraries = find_arrow_artifacts(Path(arrow_install))
            print(f"[OK] Arrow ready: {arrow_install}")
            print(f"Arrow include dirs: {arrow_include_dirs}")
            print(f"Arrow lib dirs: {arrow_lib_dirs}")
            print(f"Arrow libraries: {arrow_libraries}")
        except Exception as e:
            print(f"[WARN] Arrow preparation failed: {e}")
            print("Continuing without Arrow...")
    
    # Clean target build directory to avoid conflicts with previous builds or parallel builds
    for item in target_build_dir.iterdir():
        if item.is_file() and (item.suffix in ['.obj', '.o', '.exe', '.pdb', '.ilk']):
            try:
                item.unlink()
                print(f"cleaned: {item}")
            except (OSError, PermissionError):
                # file might be in use, continue anyway
                pass
    
    # Final executable path
    final_out_path = workspace_target_dir / (out_name + (".exe" if os.name == "nt" else ""))
    
    # All artifacts go directly to target (no build_dir copy step)
    temp_out_path = final_out_path

    # discover cxxbridge include dirs and generated .cc files (do not copy)
    include_dirs, generated_cc = find_cxxbridge_artifacts(Path(dora_target), profile)
    if not include_dirs and not generated_cc:
        raise RuntimeError("no cxxbridge outputs found under Dora target; build Dora or set DORA_TARGET_DIR")

    # If Dora is vendored under third_party/dora or cached in ~/.doracxx/dora, some generated headers expect
    # companion headers from the examples (for instance operator.h). Add any
    # example dirs containing operator.h to the include path so these headers
    # can be resolved without copying files.
    try:
        # Check both cache and local locations
        dora_locations = [
            get_dora_cache_path(dora_git, dora_rev),
            project_root / "third_party" / "dora"
        ]
        
        for vendor_dora in dora_locations:
            if vendor_dora.exists():
                # include any example operator.h parent dirs
                for p in vendor_dora.rglob("operator.h"):
                    inc = str(p.parent)
                    if inc not in include_dirs:
                        include_dirs.append(inc)
                # also add the C API apis path so includes like "operator/operator_api.h" resolve
                apis_c = vendor_dora / "apis" / "c"
                if apis_c.exists():
                    if str(apis_c) not in include_dirs:
                        include_dirs.append(str(apis_c))
                break  # Use first available location
    except Exception:
        # non-fatal; continue with discovered include dirs
        pass

    # diagnostics
    print("cxxbridge include dirs:", include_dirs)
    print("cxxbridge generated .cc:", generated_cc)

    # Set up proper C++ project structure in target directory:
    # - target/{profile}/include/ for project headers (.h/.hpp)
    # - target/{profile}/deps/ for generated/dependency headers  
    # - target/{profile}/build/ for temporary compilation artifacts
    
    # Add project include directory to include path (highest priority)
    project_include = str(target_include_dir)
    if project_include not in include_dirs:
        include_dirs.insert(0, project_include)
    
    # Add deps directory for generated/dependency headers
    deps_include = str(target_deps_dir)
    if deps_include not in include_dirs:
        include_dirs.insert(1, deps_include)
    
    # Copy project headers to target/include if they exist
    project_include_src = node_dir / "include"
    if project_include_src.exists():
        for header in project_include_src.glob("**/*.h"):
            rel_path = header.relative_to(project_include_src)
            dest = target_include_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copyfile(header, dest)
                print(f"copied project header: {header} -> {dest}")
            except Exception:
                pass
    
    # Copy convenience headers to target/deps/ directory
    # These are generated/dependency headers from cxxbridge
    try:
        # search for any lib.rs.h under the discovered cxxbridge root(s)
        for root in [Path(dora_target) / profile / "cxxbridge", Path(dora_target) / "cxxbridge"]:
            if not root.exists():
                continue
            for crate_dir in root.iterdir():
                src_h = crate_dir / "src" / "lib.rs.h"
                if src_h.exists():
                    # produce name like dora-operator-api.h by stripping -cxx or -c
                    crate_name = crate_dir.name
                    out_name = crate_name
                    if out_name.endswith("-cxx"):
                        out_name = out_name[: -len("-cxx")]
                    if out_name.endswith("-c"):
                        out_name = out_name[: -len("-c")]
                    out_name = out_name + ".h"
                    dest = target_deps_dir / out_name
                    try:
                        shutil.copyfile(src_h, dest)
                        print(f"copied dependency header: {src_h} -> {dest}")
                    except Exception:
                        # ignore copy errors; we'll still have original include dirs
                        pass
    except Exception:
        pass

    # add generated .cc sources to compile list
    # For both MSVC and GCC/Clang, if a matching Dora library exists for a crate, prefer linking that
    # library instead of compiling the generated .cc to avoid duplicate symbols.
    filtered = []
    lib_dir = Path(dora_target) / profile
    # Fallback to release if debug doesn't exist, or debug if release doesn't exist
    if not lib_dir.exists():
        if profile == "debug":
            lib_dir = Path(dora_target) / "release"
        elif profile == "release":
            lib_dir = Path(dora_target) / "debug"
    
    # Check which libraries actually exist
    available_libs = set()
    if lib_dir.exists():
        for f in lib_dir.iterdir():
            if f.is_file():
                if kind == "msvc" and f.suffix.lower() == ".lib":
                    available_libs.add(f.stem)
                elif not kind == "msvc" and f.suffix.lower() == ".a" and f.name.startswith("lib"):
                    available_libs.add(f.stem[3:])  # remove "lib" prefix
    
    # Only compile .cc files if their corresponding library doesn't exist
    for p in generated_cc:
        ppath = Path(p)
        # crate name is parent of src (e.g., dora-node-api-cxx)
        crate = ppath.parent.parent.name if ppath.parent.parent.name else None
        should_compile = True
        
        if crate:
            lib_candidates = [crate, crate.replace('-', '_')]
            for candidate in lib_candidates:
                if candidate in available_libs:
                    should_compile = False
                    break
        
        if should_compile:
            filtered.append(ppath)
    
    srcs += filtered
    # Build command differs between MSVC (cl) and gcc/clang (g++, clang++)
    if kind == "msvc":
        # cl compiles+links in one invocation. Use /std:c++17 and /EHsc for exceptions.
        # Ensure runtime library matches Dora's build: always use /MD to match release libs
        runtime_flag = "/MD"
        cmd = [cc, "/nologo", "/EHsc", runtime_flag]
        
        # Add C++ standard from config
        std_flag = f"/std:{config.build.std}" if config else "/std:c++17"
        cmd.append(std_flag)
        
        # Add custom compiler flags from config, converting GCC/Clang flags to MSVC equivalents
        if config:
            msvc_flags = []
            has_warning_suppression = False
            
            # Check for global warning suppression
            if config.build.suppress_warnings:
                msvc_flags.append("/w")  # Disable all warnings
                has_warning_suppression = True
            
            for flag in config.build.cxxflags:
                # Convert common GCC/Clang flags to MSVC equivalents
                if flag == "-Wall":
                    if not config.build.suppress_warnings:
                        msvc_flags.append("/W3")  # MSVC equivalent of -Wall
                elif flag == "-Wextra":
                    if not config.build.suppress_warnings:
                        msvc_flags.append("/W4")  # MSVC equivalent of -Wextra
                elif flag == "-w":
                    msvc_flags.append("/w")  # Disable all warnings
                    has_warning_suppression = True
                elif flag == "-O2":
                    msvc_flags.append("/O2")  # Optimization level 2
                elif flag == "-O3":
                    msvc_flags.append("/Ox")  # Maximum optimization
                elif flag.startswith("-D"):
                    msvc_flags.append(f"/D{flag[2:]}")  # Convert -DFOO to /DFOO
                elif flag.startswith("/"):
                    msvc_flags.append(flag)  # Already MSVC format
                # Skip other incompatible flags
                elif flag.startswith("-"):
                    print(f"[WARN] Skipping incompatible flag for MSVC: {flag}")
                else:
                    msvc_flags.append(flag)
            
            # Auto-detect problematic dependencies and add warning suppression
            if not has_warning_suppression and config.build.auto_suppress_verbose_deps and dep_manager:
                problematic_deps = ['rs_driver', 'opencv', 'pcl', 'boost']
                for dep_name in problematic_deps:
                    if any(dep_name.lower() in dep_key.lower() for dep_key in dep_manager.config.dependencies.keys()):
                        print(f"[INFO] Detected potentially verbose dependency '{dep_name}', adding targeted warning suppression")
                        msvc_flags.append("/wd4996")  # Disable deprecation warnings
                        msvc_flags.append("/wd4244")  # Disable conversion warnings
                        msvc_flags.append("/wd4267")  # Disable size conversion warnings
                        msvc_flags.append("/wd4101")  # Disable unreferenced variable warnings
                        msvc_flags.append("/wd4189")  # Disable unused variable warnings
                        msvc_flags.append("/wd4251")  # Disable template export warnings
                        msvc_flags.append("/wd4275")  # Disable base class export warnings
                        break
            
            cmd.extend(msvc_flags)
        
        # add include dirs for MSVC (Dora includes first)
        for inc in include_dirs:
            cmd += ["/I", inc]
        
        # Add Arrow include directories
        for inc in arrow_include_dirs:
            cmd += ["/I", inc]
        
        # Add dependency include directories
        if dep_manager:
            dep_include_flags, _, _ = dep_manager.get_compiler_flags()
            for flag in dep_include_flags:
                cmd += ["/I", flag[2:]]  # Remove -I prefix for MSVC
        
        # Add custom include directories from config
        if config:
            for inc_dir in config.build.include_dirs:
                abs_inc = node_dir / inc_dir if not Path(inc_dir).is_absolute() else Path(inc_dir)
                cmd += ["/I", str(abs_inc)]
        
        # Set object file output directory to target/build
        cmd.append(f"/Fo{target_build_dir}\\")
        
        cmd += [str(s) for s in srcs]
        
        # Find any Dora library files under the Dora target dir to pass to linker
        lib_dir = Path(dora_target) / profile
        # Fallback between debug and release profiles
        if not lib_dir.exists():
            if profile == "debug":
                lib_dir = Path(dora_target) / "release"
            elif profile == "release":
                lib_dir = Path(dora_target) / "debug"
        libs = []
        if lib_dir.exists():
            for f in lib_dir.iterdir():
                if not f.is_file():
                    continue
                # only consider .lib files for MSVC linker (avoid .d/.rlib)
                if f.suffix.lower() != ".lib":
                    continue
                name = f.name.lower()
                # collect obvious Dora library names
                if "dora_node_api_cxx" in name or name.startswith("libdora") or name.startswith("dora"):
                    libs.append(f.name)
        # fallback to generic lib name if none found
        if not libs:
            libs = ["dora_node_api_cxx.lib"]
        
        # Add dependency libraries
        if dep_manager:
            libs.extend(dep_manager.libraries)
        
        # Add Arrow libraries
        libs.extend(arrow_libraries)
        
        # Add custom libraries from config
        if config:
            libs.extend(config.build.libraries)
        
        # always link winsock and some common Windows system libs
        libs.append("ws2_32.lib")
        for syslib in ("userenv.lib", "bcrypt.lib", "ole32.lib", "oleaut32.lib", "advapi32.lib", "ntdll.lib", "shell32.lib"):
            if syslib not in libs:
                libs.append(syslib)
        
        # /LINK and /OUT
        cmd += ["/link", "/LIBPATH:" + str(lib_dir)]
        
        # Add Arrow library directories
        for arrow_lib_dir in arrow_lib_dirs:
            cmd += ["/LIBPATH:" + arrow_lib_dir]
        
        # Add dependency library directories
        if dep_manager:
            for lib_dir_path in dep_manager.lib_dirs:
                cmd += ["/LIBPATH:" + lib_dir_path]
        
        # Add custom library directories from config
        if config:
            for lib_dir_path in config.build.lib_dirs:
                abs_lib = node_dir / lib_dir_path if not Path(lib_dir_path).is_absolute() else Path(lib_dir_path)
                cmd += ["/LIBPATH:" + str(abs_lib)]
        
        # Add custom linker flags from config
        if config:
            cmd.extend(config.build.ldflags)
        
        cmd += libs
        cmd += ["/OUT:" + str(temp_out_path)]
        
        # Use configured timeout for build
        timeout = config.build.build_timeout if config else 300
        run(cmd, cwd=node_dir, timeout=timeout, config=config)
    else:
        # assume gcc/clang compatible
        cmd = [cc]
        cmd += [str(s) for s in srcs]
        
        # Add C++ standard from config
        std_flag = f"-std={config.build.std}" if config else "-std=c++17"
        cmd.append(std_flag)
        
        # Add custom compiler flags from config
        if config:
            cmd.extend(config.build.cxxflags)
        
        # include dirs (Dora includes first)
        for inc in include_dirs:
            cmd += ["-I", inc]
        
        # Add Arrow include directories
        for inc in arrow_include_dirs:
            cmd += ["-I", inc]
        
        # Add dependency include directories
        if dep_manager:
            dep_include_flags, _, _ = dep_manager.get_compiler_flags()
            cmd.extend(dep_include_flags)
        
        # Add custom include directories from config
        if config:
            for inc_dir in config.build.include_dirs:
                abs_inc = node_dir / inc_dir if not Path(inc_dir).is_absolute() else Path(inc_dir)
                cmd += ["-I", str(abs_inc)]
        
        # link flags
        # search Dora libs in given dora_target/<profile> and dora_target/<profile>/deps
        # Fallback between debug and release profiles
        base_lib_dir = Path(dora_target) / profile
        if not base_lib_dir.exists():
            if profile == "debug":
                base_lib_dir = Path(dora_target) / "release"
            elif profile == "release":
                base_lib_dir = Path(dora_target) / "debug"
        
        lib_dirs = [base_lib_dir, base_lib_dir / "deps"]
        linked = []
        for ld in lib_dirs:
            if not ld.exists():
                continue
            cmd += ["-L", str(ld)]
            for f in ld.iterdir():
                if not f.is_file():
                    continue
                n = f.name
                # Only link the main API libraries, not all dependencies
                if n == "libdora_node_api_cxx.a" or n == "libdora_node_api_c.a":
                    # libfoo.a -> -lfoo
                    base = n
                    if base.startswith("lib"):
                        base = base[3:]
                    base = base.split(".")[0]
                    if base not in linked:  # avoid duplicates
                        linked.append(base)
        
        # Add dependency library directories and libraries
        if dep_manager:
            _, dep_lib_dir_flags, dep_lib_flags = dep_manager.get_compiler_flags()
            cmd.extend(dep_lib_dir_flags)
        
        # Add Arrow library directories
        for arrow_lib_dir in arrow_lib_dirs:
            cmd += ["-L", arrow_lib_dir]
        
        # Add custom library directories from config
        if config:
            for lib_dir_path in config.build.lib_dirs:
                abs_lib = node_dir / lib_dir_path if not Path(lib_dir_path).is_absolute() else Path(lib_dir_path)
                cmd += ["-L", str(abs_lib)]
                # Add rpath for custom library directories too
                if os.name != "nt":  # Linux/macOS
                    cmd += ["-Wl,-rpath," + str(abs_lib)]
        
        # add common flags
        if os.name == "nt":
            cmd += ["-lws2_32"]
        else:
            cmd += ["-pthread"]
        
        # add -l for discovered libs
        for ln in linked:
            cmd += ["-l", ln]
        
        # Add dependency libraries
        if dep_manager:
            _, _, dep_lib_flags = dep_manager.get_compiler_flags()
            cmd.extend(dep_lib_flags)
        
        # Add Arrow libraries
        for arrow_lib in arrow_libraries:
            cmd += ["-l", arrow_lib]
        
        # Add system dependencies for Arrow static linking
        if arrow_libraries and os.name != "nt":
            # Arrow needs these system libraries when statically linked
            arrow_system_deps = ["dl", "rt"]  # Dynamic loading and real-time extensions
            for sys_dep in arrow_system_deps:
                cmd += ["-l", sys_dep]
        
        # Add custom libraries from config
        if config:
            for lib in config.build.libraries:
                cmd += ["-l", lib]
        
        # Add custom linker flags from config
        if config:
            cmd.extend(config.build.ldflags)
        
        cmd += extras
        cmd += ["-o", str(temp_out_path)]
        
        # Use configured timeout for build
        timeout = config.build.build_timeout if config else 300
        run(cmd, cwd=node_dir, timeout=timeout, config=config)
    
    # Check if executable was created successfully
    if final_out_path.exists():
        print(f"built: {final_out_path}")
        return final_out_path
    else:
        raise RuntimeError(f"executable not created: {final_out_path}")


def ensure_clang_installed(install: bool = False):
    """Ensure clang/clang++ are visible in PATH for this process. If not present and
    install=True, download a portable LLVM zip into third_party/llvm and add its bin to PATH.

    This is intentionally conservative: it only acts if clang is not already present.
    """
    import shutil

    # quick check
    if shutil.which("clang") or shutil.which("clang++"):
        print("clang already available on PATH")
        return True

    if not install:
        print("clang not found and install not requested")
        return False

    # Configure download URL via env to allow offline mirrors; default is a GitHub release for LLVM
    # default to a recent LLVM Windows release; can be overridden with CLANG_DOWNLOAD_URL
    default_url = os.environ.get("CLANG_DOWNLOAD_URL", "https://github.com/llvm/llvm-project/releases/download/llvmorg-20.1.8/clang+llvm-20.1.8-x86_64-pc-windows-msvc.tar.xz")
    
    # Use global cache for LLVM installation
    target_root = get_doracxx_cache_dir() / "llvm"
    target_root.mkdir(parents=True, exist_ok=True)
    zip_name = default_url.split("/")[-1]
    dest_zip = target_root / zip_name

    def try_pkg_manager_install():
        # try winget then choco
        try:
            if shutil.which("winget"):
                print("attempting to install LLVM via winget (non-interactive)")
                # use flags to accept agreements and avoid prompts; allow failure without raising
                cmd = ["winget", "install", "--id", "LLVM.LLVM", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements"]
                try:
                    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                except Exception as e:
                    print("winget run failed:", e)
                # attempt to locate installed bin
                if locate_and_add_llvm_bin():
                    return True
                return False
        except Exception as e:
            print("winget install failed:", e)
        # do not attempt choco by default to avoid elevation prompts
        return False

    def locate_and_add_llvm_bin():
        """Search common LLVM install locations and prepend bin to PATH if found."""
        candidates = [
            Path(r"C:\Program Files\LLVM\bin"),
            Path(r"C:\Program Files (x86)\LLVM\bin"),
            Path(r"C:\Program Files\Microsoft Visual Studio\Shared\LLVM\bin"),
        ]
        for c in candidates:
            if c.exists():
                old = os.environ.get("PATH", "")
                if str(c) not in old:
                    os.environ["PATH"] = str(c) + os.pathsep + old
                    print(f"added {c} to PATH for this process")
                return True
        return False

    try:
        if not dest_zip.exists():
            print(f"Downloading LLVM from {default_url} to {dest_zip}...")
            try:
                with urllib.request.urlopen(default_url) as resp, open(dest_zip, "wb") as out:
                    shutil.copyfileobj(resp, out)
            except Exception as e:
                print("download failed:", e)
                # try package managers as fallback
                if try_pkg_manager_install():
                    # re-check
                    if shutil.which("clang") or shutil.which("clang++"):
                        print("clang is now available after package manager install")
                        return True
                # try to locate typical LLVM install locations and add them to PATH
                if locate_and_add_llvm_bin():
                    if shutil.which("clang") or shutil.which("clang++"):
                        print("clang is now available after package manager install and path fixup")
                        return True
                print("Please set CLANG_DOWNLOAD_URL to a valid archive or install clang manually (winget/choco)")
                return False
        else:
            print(f"Using cached LLVM archive {dest_zip}")

        # extract (support zip and tar.xz)
        extract_dir = target_root / zip_name.replace('.zip', '').replace('.tar.xz', '')
        if not extract_dir.exists():
            print(f"Extracting {dest_zip} to {extract_dir}...")
            if zip_name.endswith('.zip'):
                with zipfile.ZipFile(dest_zip, 'r') as z:
                    z.extractall(extract_dir)
            elif zip_name.endswith('.tar.xz') or zip_name.endswith('.tar'):
                with tarfile.open(dest_zip, 'r:xz') as t:
                    t.extractall(extract_dir)
            else:
                # try generic tar extraction
                with tarfile.open(dest_zip, 'r:*') as t:
                    t.extractall(extract_dir)

        # try to find bin dir
        bin_candidate = None
        for root, dirs, files in os.walk(str(extract_dir)):
            if 'clang.exe' in files or 'clang++.exe' in files:
                bin_candidate = Path(root)
                break

        if not bin_candidate:
            print("failed to locate clang in the extracted archive")
            # try package manager fallback
            if try_pkg_manager_install():
                if shutil.which("clang") or shutil.which("clang++"):
                    print("clang is now available after package manager install")
                    return True
                # try locating installed LLVM bin dirs
                if locate_and_add_llvm_bin():
                    if shutil.which("clang") or shutil.which("clang++"):
                        print("clang is now available after package manager install and path fixup")
                        return True
            return False

        # prepend to PATH
        old = os.environ.get("PATH", "")
        os.environ["PATH"] = str(bin_candidate) + os.pathsep + old
        print(f"prepended {bin_candidate} to PATH for this process")
        return True
    except Exception as e:
        print("error while installing clang:", e)
        return False


def copy_shared_libraries_to_executable_dir(executable_path: Path, lib_dirs: List[str]):
    """Copy shared libraries from library directories to the same directory as the executable.
    
    This is used as a fallback when static linking is not possible or desired.
    Only copies libraries that are actually needed by the executable.
    """
    if not executable_path.exists():
        print(f"Warning: Executable not found: {executable_path}")
        return
    
    exe_dir = executable_path.parent
    copied_libs = []
    
    for lib_dir in lib_dirs:
        lib_path = Path(lib_dir)
        if not lib_path.exists():
            continue
            
        # Find shared libraries (.so on Linux, .dylib on macOS, .dll on Windows)
        if os.name == "nt":
            patterns = ["*.dll"]
        elif sys.platform == "darwin":
            patterns = ["*.dylib"]
        else:
            patterns = ["*.so", "*.so.*"]
            
        for pattern in patterns:
            for lib_file in lib_path.glob(pattern):
                if lib_file.is_file():
                    dest_file = exe_dir / lib_file.name
                    if not dest_file.exists():
                        try:
                            shutil.copy2(lib_file, dest_file)
                            copied_libs.append(lib_file.name)
                            print(f"[COPY] Copied shared library: {lib_file.name}")
                        except Exception as e:
                            print(f"Warning: Could not copy {lib_file.name}: {e}")
    
    if copied_libs:
        print(f"[COPY] Copied {len(copied_libs)} shared libraries to {exe_dir}")
    
    return copied_libs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-dir", default=None, help="directory containing the node (defaults to current directory if it contains doracxx.toml)")
    parser.add_argument("--profile", default=None, help="build profile: debug or release (overrides config)")
    parser.add_argument("--dora-target")
    parser.add_argument("--skip-build-packages", action="store_true", help="skip attempting to cargo build Dora packages in workspace")
    parser.add_argument("--fetch-dora", action="store_true", help="clone and build Dora automatically into third_party/dora")
    parser.add_argument("--dora-git", default=None, help="git URL to Dora repo (overrides config)")
    parser.add_argument("--dora-rev", default=None, help="git ref to checkout when fetching Dora (overrides config)")
    parser.add_argument("--out", default=None, help="output executable name (defaults to node name from config)")
    parser.add_argument("--install-clang", action="store_true", help="if clang is missing, attempt to download a portable LLVM and add it to PATH for this run")
    parser.add_argument("--config", default=None, help="path to doracxx.toml configuration file")
    parser.add_argument("--no-config", action="store_true", help="disable automatic config loading")
    parser.add_argument("--no-auto-prepare", action="store_true", help="disable automatic Dora preparation")
    args = parser.parse_args()

    # Auto-detect node directory if not specified
    if args.node_dir is None:
        # Check if current directory contains doracxx.toml
        current_dir = Path.cwd()
        if (current_dir / "doracxx.toml").exists():
            node_dir = current_dir
            print(f"[AUTO] Auto-detected node directory: {node_dir}")
        else:
            # Try to find project root and check if it's a node directory
            try:
                project_root = find_project_root(current_dir)
                if (project_root / "doracxx.toml").exists():
                    node_dir = project_root
                    print(f"[AUTO] Auto-detected node directory at project root: {node_dir}")
                else:
                    print("[ERROR] Error: No doracxx.toml found in current directory or project root.")
                    print("   Please specify --node-dir or run from a directory containing doracxx.toml")
                    sys.exit(1)
            except Exception:
                print("[ERROR] Error: No doracxx.toml found in current directory.")
                print("   Please specify --node-dir or run from a directory containing doracxx.toml")
                sys.exit(1)
    else:
        node_dir = Path(args.node_dir).resolve()

    build_dir = node_dir / "build"
    build_dir.mkdir(exist_ok=True)

    # Load configuration if available and not disabled
    config = None
    if not args.no_config:
        try:
            if args.config:
                config = load_config(args.config)
            else:
                # Look for doracxx.toml in node directory first, then find project root
                project_root = find_project_root(node_dir)
                config_candidates = [
                    node_dir / "doracxx.toml",
                    project_root / "doracxx.toml"
                ]
                for config_path in config_candidates:
                    if config_path.exists():
                        config = load_config(config_path)
                        print(f"[CONFIG] Loaded configuration: {config_path}")
                        break
        except Exception as e:
            print(f"[WARN] Warning: Failed to load configuration: {e}")
            print("Continuing with command-line arguments only...")
    
    # Determine settings (command-line overrides config)
    if config:
        profile = args.profile or config.build.profile
        dora_git = args.dora_git or config.node.dora_git or "https://github.com/dora-rs/dora"
        dora_rev = args.dora_rev or config.node.dora_rev
        out_name = args.out or config.node.name
        install_clang = args.install_clang or config.build.install_clang
    else:
        profile = args.profile or "debug"
        dora_git = args.dora_git or "https://github.com/dora-rs/dora"
        dora_rev = args.dora_rev
        out_name = args.out or "node"
        install_clang = args.install_clang

    print(f"[BUILD] Building node: {out_name}")
    print(f"[NODE] Node directory: {node_dir}")
    print(f"[BUILD] Build profile: {profile}")
    if config:
        print(f"[DEPS] Dependencies: {len(config.dependencies)}")

    # If the node appears to be a native C++ node (contains .cc sources), we
    # should not attempt to cargo-build Dora Rust packages by default because
    # the build only needs the cxxbridge generated sources and the Dora libs.
    # Auto-set skip_build_packages to avoid cargo workspace parsing issues when
    # Dora is vendored under third_party/dora.
    if any(node_dir.glob("**/*.cc")):
        if not args.skip_build_packages:
            print("detected C++ sources in node; enabling --skip-build-packages to avoid cargo builds")
        args.skip_build_packages = True

    # Prefer an explicit argument, then env, then ensure Dora is prepared
    dora_target = args.dora_target or os.environ.get("DORA_TARGET_DIR")
    if not dora_target:
        if not args.no_auto_prepare:
            # Automatically ensure Dora is prepared with the right version
            try:
                dora_target = ensure_dora_prepared(dora_git, dora_rev, profile)
                print(f"Using Dora target directory: {dora_target}")
            except Exception as e:
                print(f"[ERROR] Failed to prepare Dora automatically: {e}")
                # Fallback to manual target detection
                dora_target = find_dora_target_dir(dora_git, dora_rev)
                print(f"Using fallback Dora target directory: {dora_target}")
        else:
            # Manual mode - just find existing target
            dora_target = find_dora_target_dir(dora_git, dora_rev)
            print(f"Using Dora target directory: {dora_target}")
    else:
        print(f"Using explicit Dora target directory: {dora_target}")

    # If requested, fetch Dora and build required packages
    if args.fetch_dora:
        # Use global cache for fetched Dora
        vendor = get_dora_cache_path(dora_git, dora_rev)
        print(f"Fetching Dora into global cache {vendor} from {dora_git}...")
        repo = git_clone(dora_git, vendor, dora_rev)
        
        # build the entire Dora workspace to ensure cxxbridge outputs are generated
        cargo_cmd = [os.environ.get("CARGO", "cargo"), "build", "--workspace"]
        if profile == "release":
            cargo_cmd.append("--release")
        print("Running:", " ".join(cargo_cmd), "in", repo)
        try:
            subprocess.check_call(cargo_cmd, cwd=repo)
        except subprocess.CalledProcessError:
            print("warning: cargo build --workspace failed; attempting to continue and locate cxxbridge outputs")
        # ensure we look at the Dora target dir
        dora_target = str(repo / "target")

        # If workspace build failed (often due to system deps), try building just the C++ API crates
        # Build the C++ API crates' manifests directly to avoid pulling in heavy optional dependencies.
        manifests = [
            repo / "apis" / "c++" / "node" / "Cargo.toml",
            repo / "apis" / "c++" / "operator" / "Cargo.toml",
            repo / "apis" / "c" / "node" / "Cargo.toml",
            repo / "apis" / "c" / "operator" / "Cargo.toml",
        ]
        for m in manifests:
            if m.exists():
                build_manifest(m, profile=profile)

    # try to build packages if present (when Dora not fetched into repo we still attempt generic package builds)
    if not args.fetch_dora and not args.skip_build_packages:
        for pkg in ["dora-node-api-cxx", "dora-operator-api-cxx", "dora-node-api-c", "dora-operator-api-c"]:
            build_package(pkg)

    # Do not copy cxxbridge outputs; pass Dora target to compiler so it can pick up
    # generated sources and include dirs directly.
    # If requested, try to ensure clang is available (downloads to third_party/llvm if needed)
    if install_clang:
        ensure_clang_installed(install=True)

    try:
        out = compile_node(node_dir, build_dir, out_name, profile, dora_target, 
                          extras=["-l", "dora_node_api_cxx"], config=config, 
                          dora_git=dora_git, dora_rev=dora_rev)
        print("built:", out)
        sys.exit(0)  # Explicit successful exit
    except Exception as e:
        print(f"compilation failed: {e}")
        # Check if the executable was actually created despite the error in target location
        project_root = find_project_root(node_dir)
        expected_exe_target = project_root / "target" / profile / (out_name + (".exe" if os.name == "nt" else ""))
        
        if expected_exe_target.exists():
            print(f"However, executable was successfully created in target: {expected_exe_target}")
            print("built:", expected_exe_target)
            sys.exit(0)  # Explicit successful exit even if there was an exception
        else:
            print(f"Executable not found in target: {expected_exe_target}")
            sys.exit(1)

def load_msvc_env():
    """Locate vcvarsall.bat using vswhere or common install paths, run it and import the environment.

    This attempts to make cl/link visible when the script is run from a plain PowerShell.
    """
    if os.name != "nt":
        return
    candidates = []
    # try vswhere
    vswhere = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
    if vswhere.exists():
        try:
            out = subprocess.check_output([str(vswhere), "-latest", "-property", "installationPath"], stderr=subprocess.DEVNULL, text=True)
            inst = out.strip()
            if inst:
                candidates.append(Path(inst) / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat")
        except Exception:
            pass

    # common fallback locations
    common = [
        Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat"),
    ]
    candidates.extend(common)

    vc = None
    for c in candidates:
        if c and c.exists():
            vc = c
            break
    if not vc:
        # nothing found
        print("vcvars not found among candidates:")
        for c in candidates:
            print(" -", c)
        return

    # Try multiple argument names for 64-bit environment and other host-target variants.
    variants = ["x64", "amd64", "x86_amd64", "amd64_x86", "x86"]
    out = None
    last_err = None
    for v in variants:
        try:
            # Use shell execution so that 'call' and 'set' are interpreted correctly by cmd.exe
            cmd_line = f'call "{str(vc)}" {v} >nul 2>&1 && set'
            out = subprocess.check_output(cmd_line, shell=True, text=True, stderr=subprocess.STDOUT)
            print(f"vcvars succeeded with variant: {v} (using {vc})")
            break
        except subprocess.CalledProcessError as e:
            last_err = e.output if hasattr(e, 'output') else str(e)
            print(f"vcvars attempt failed for variant {v} at {vc}: {last_err}")
        except Exception as e:
            last_err = str(e)
            print(f"vcvars attempt error for variant {v} at {vc}: {last_err}")
    if out is None:
        print("vcvarsall attempts failed; cl may not be available")
        return
    # parse KEY=VALUE lines
    vc_env = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        vc_env[k] = v
    # Merge PATH from vcvars: put vcvars PATH first so cl/link are found
    vc_path = vc_env.get("PATH") or vc_env.get("Path")
    if vc_path:
        existing = os.environ.get("PATH", "")
        # Prepend vc_path to existing PATH if not already present
        if vc_path not in existing:
            os.environ["PATH"] = vc_path + os.pathsep + existing
    # Diagnostics: which compilers are now visible
    try:
        import shutil as _sh
        found = {"cl": _sh.which("cl"), "clang-cl": _sh.which("clang-cl"), "g++": _sh.which("g++")}
        print("post-vcvars compiler detection:")
        for k, v in found.items():
            print(f" - {k}: {v}")
    except Exception:
        pass
    # Import other important vars if missing
    for k, v in vc_env.items():
        if k == "PATH" or k == "Path":
            continue
        if k not in os.environ:
            os.environ[k] = v
    return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBuild interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)

