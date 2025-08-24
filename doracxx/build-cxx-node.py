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


def get_doracxx_cache_dir():
    """Get the global doracxx cache directory (~/.doracxx)."""
    home = Path.home()
    cache_dir = home / ".doracxx"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_dora_cache_path():
    """Get the path for cached Dora installation."""
    return get_doracxx_cache_dir() / "dora"


def find_dora_target_dir():
    """Find Dora target directory, checking cache first, then local."""
    # Check global cache first
    cache_target = get_dora_cache_path() / "target"
    if cache_target.exists():
        return str(cache_target)
    
    # Fallback to local third_party (backward compatibility)
    local_target = Path.cwd() / "third_party" / "dora" / "target"
    if local_target.exists():
        return str(local_target)
    
    # Last resort: current workspace target
    return str(Path.cwd() / "target")


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


def run(cmd, cwd=None, env=None):
    print("$ ", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd, env=env)


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


def compile_node(node_dir: Path, build_dir: Path, out_name: str, profile: str, dora_target: str, extras: list):
    # Clean build directory to avoid conflicts with previous builds or parallel builds
    if build_dir.exists():
        for item in build_dir.iterdir():
            if item.is_file() and (item.suffix in ['.obj', '.o', '.exe', '.pdb', '.ilk']):
                try:
                    item.unlink()
                    print(f"cleaned: {item}")
                except (OSError, PermissionError):
                    # file might be in use, continue anyway
                    pass
    
    # On Windows, try to load MSVC environment (vcvarsall) so cl/link are visible
    if os.name == "nt":
        try:
            load_msvc_env()
        except Exception:
            # if it fails, we continue and rely on PATH / CXX
            pass

    # Find a C++ compiler (prefer environment, then common names). Use shutil.which to avoid
    # raising FileNotFoundError from subprocess when candidate not present.
    cc_env = os.environ.get("CXX") or os.environ.get("CXX_COMPILER")
    cc = None
    kind = None
    if cc_env and shutil.which(cc_env):
        cc = cc_env
        # heuristics for kind
        if cc_env.lower().endswith("cl.exe") or cc_env.lower().endswith("cl"):
            kind = "msvc"
    else:
        # On Windows prefer MSVC (cl), then clang-cl, clang++, g++
        if os.name == "nt":
            for cand, k in [("cl", "msvc"), ("clang-cl", "msvc"), ("clang++", "gcc"), ("g++", "gcc")]:
                p = shutil.which(cand)
                if p:
                    cc = p
                    kind = k
                    break
        else:
            for cand in ("clang++", "g++"):
                p = shutil.which(cand)
                if p:
                    cc = p
                    kind = "gcc"
                    break

    if not cc:
        # If no compiler found on Windows, try to install clang automatically
        if os.name == "nt":
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
    for pattern in ["**/*.cc", "**/*.cpp", "**/*.c"]:
        srcs.extend(node_dir.glob(pattern))
    
    if not srcs:
        raise RuntimeError("no C/C++ sources found in node dir (looked for .cc, .cpp, .c files)")
    
    # Use target/<profile>/ for final executable (like Rust projects)
    # Use the workspace target directory, not the Dora target directory
    workspace_target_dir = Path.cwd() / "target" / profile
    workspace_target_dir.mkdir(parents=True, exist_ok=True)
    final_out_path = workspace_target_dir / (out_name + (".exe" if os.name == "nt" else ""))
    
    # Build in the build_dir first, then copy to target
    temp_out_path = build_dir / (out_name + (".exe" if os.name == "nt" else ""))

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
            get_dora_cache_path(),
            Path.cwd() / "third_party" / "dora"
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

    # Set up proper C++ project structure:
    # - include/ for project headers (.h/.hpp)
    # - deps/ for generated/dependency headers
    # - build/ for temporary compilation artifacts
    
    # Create structured directories
    include_dir = node_dir / "include"
    deps_dir = node_dir / "deps"
    include_dir.mkdir(exist_ok=True)
    deps_dir.mkdir(exist_ok=True)
    
    # Add project include directory to include path (highest priority)
    project_include = str(include_dir)
    if project_include not in include_dirs:
        include_dirs.insert(0, project_include)
    
    # Add deps directory for generated/dependency headers
    deps_include = str(deps_dir)
    if deps_include not in include_dirs:
        include_dirs.insert(1, deps_include)
    
    # Copy convenience headers to deps/ directory instead of build/
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
                    dest = deps_dir / out_name
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
        cmd = [cc, "/nologo", "/EHsc", "/std:c++17", runtime_flag]
        # add include dirs for MSVC
        for inc in include_dirs:
            cmd += ["/I", inc]
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
        # always link winsock and some common Windows system libs
        libs.append("ws2_32.lib")
        for syslib in ("userenv.lib", "bcrypt.lib", "ole32.lib", "oleaut32.lib", "advapi32.lib", "ntdll.lib", "shell32.lib"):
            if syslib not in libs:
                libs.append(syslib)
        # /LINK and /OUT
        cmd += ["/link", "/LIBPATH:" + str(lib_dir)]
        cmd += libs
        cmd += ["/OUT:" + str(temp_out_path)]
        run(cmd, cwd=node_dir)
    else:
        # assume gcc/clang compatible
        cmd = [cc]
        cmd += [str(s) for s in srcs]
        cmd += ["-std=c++17"]
        # include dirs
        for inc in include_dirs:
            cmd += ["-I", inc]
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
        # add common flags
        if os.name == "nt":
            cmd += ["-lws2_32"]
        else:
            cmd += ["-pthread"]
        # add -l for discovered libs
        for ln in linked:
            cmd += ["-l", ln]
        cmd += extras
        cmd += ["-o", str(temp_out_path)]
        run(cmd, cwd=node_dir)
    
    # Copy the executable to target/<profile>/ directory (like Rust projects)
    if temp_out_path.exists():
        try:
            if final_out_path.exists():
                final_out_path.unlink()
            shutil.copy2(temp_out_path, final_out_path)
            print(f"copied executable: {temp_out_path} -> {final_out_path}")
        except Exception as e:
            print(f"warning: failed to copy to target directory: {e}")
            # Return the temp path if copy fails
            return temp_out_path
        return final_out_path
    else:
        raise RuntimeError(f"executable not created: {temp_out_path}")


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-dir", required=True)
    parser.add_argument("--profile", default="debug")
    parser.add_argument("--dora-target")
    parser.add_argument("--skip-build-packages", action="store_true", help="skip attempting to cargo build Dora packages in workspace")
    parser.add_argument("--fetch-dora", action="store_true", help="clone and build Dora automatically into third_party/dora")
    parser.add_argument("--dora-git", default="https://github.com/dora-rs/dora", help="git URL to Dora repo (used with --fetch-dora)")
    parser.add_argument("--dora-rev", default=None, help="git ref to checkout when fetching Dora (optional)")
    parser.add_argument("--out", default="node")
    parser.add_argument("--install-clang", action="store_true", help="if clang is missing, attempt to download a portable LLVM and add it to PATH for this run")
    args = parser.parse_args()

    node_dir = Path(args.node_dir).resolve()
    build_dir = node_dir / "build"
    build_dir.mkdir(exist_ok=True)

    profile = args.profile

    # If the node appears to be a native C++ node (contains .cc sources), we
    # should not attempt to cargo-build Dora Rust packages by default because
    # the build only needs the cxxbridge generated sources and the Dora libs.
    # Auto-set skip_build_packages to avoid cargo workspace parsing issues when
    # Dora is vendored under third_party/dora.
    if any(node_dir.glob("**/*.cc")):
        if not args.skip_build_packages:
            print("detected C++ sources in node; enabling --skip-build-packages to avoid cargo builds")
        args.skip_build_packages = True

    # Prefer an explicit argument, then env, then cached dora, then local dora,
    # otherwise fall back to the current workspace target dir.
    dora_target = args.dora_target or os.environ.get("DORA_TARGET_DIR")
    if not dora_target:
        dora_target = find_dora_target_dir()
        print(f"Using Dora target directory: {dora_target}")

    # If requested, fetch Dora and build required packages
    if args.fetch_dora:
        # Use global cache for fetched Dora
        vendor = get_dora_cache_path()
        print(f"Fetching Dora into global cache {vendor} from {args.dora_git}...")
        repo = git_clone(args.dora_git, vendor, args.dora_rev)
        
        # Create symlink for backward compatibility
        local_vendor = Path("third_party") / "dora"
        local_vendor.parent.mkdir(exist_ok=True)
        if not local_vendor.exists():
            try:
                if os.name == "nt":
                    subprocess.run(["cmd", "/c", "mklink", "/J", str(local_vendor), str(vendor)], 
                                 check=True, capture_output=True)
                else:
                    local_vendor.symlink_to(vendor, target_is_directory=True)
                print(f"Created symlink: {local_vendor} -> {vendor}")
            except (subprocess.CalledProcessError, OSError):
                print("Warning: could not create symlink, using cache directly")
        
        # build the entire Dora workspace to ensure cxxbridge outputs are generated
        cargo_cmd = [os.environ.get("CARGO", "cargo"), "build", "--workspace"]
        if args.profile == "release":
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
                build_manifest(m, profile=args.profile)

    # try to build packages if present (when Dora not fetched into repo we still attempt generic package builds)
    if not args.fetch_dora and not args.skip_build_packages:
        for pkg in ["dora-node-api-cxx", "dora-operator-api-cxx", "dora-node-api-c", "dora-operator-api-c"]:
            build_package(pkg)

    # Do not copy cxxbridge outputs; pass Dora target to compiler so it can pick up
    # generated sources and include dirs directly.
    # If requested, try to ensure clang is available (downloads to third_party/llvm if needed)
    if args.install_clang:
        ensure_clang_installed(install=True)

    try:
        out = compile_node(node_dir, build_dir, args.out, profile, dora_target, extras=["-l", "dora_node_api_cxx"])
        print("built:", out)
    except Exception as e:
        print(f"compilation failed: {e}")
        # Check if the executable was actually created despite the error in either location
        expected_exe_build = build_dir / (args.out + (".exe" if os.name == "nt" else ""))
        expected_exe_target = Path.cwd() / "target" / profile / (args.out + (".exe" if os.name == "nt" else ""))
        
        if expected_exe_target.exists():
            print(f"However, executable was successfully created in target: {expected_exe_target}")
            print("built:", expected_exe_target)
        elif expected_exe_build.exists():
            print(f"However, executable was successfully created in build: {expected_exe_build}")
            print("built:", expected_exe_build)
        else:
            print(f"Executable not found in target: {expected_exe_target}")
            print(f"Executable not found in build: {expected_exe_build}")
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

