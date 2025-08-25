#!/usr/bin/env python3
"""
Dependency management for doracxx

This module handles resolution, downloading, and building of dependencies
defined in doracxx.toml configuration files.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request
import zipfile
import tarfile

from .config import (
    DoracxxConfig, GitDependency, VcpkgDependency, 
    SystemDependency, LocalDependency, BuildSystem
)
from .cache import get_doracxx_cache_dir


class DependencyManager:
    """Manages dependency resolution and building"""
    
    def __init__(self, config: DoracxxConfig, node_dir: Path, target_dir: Optional[Path] = None):
        self.config = config
        self.node_dir = node_dir
        
        # Use target directory structure if provided, otherwise fallback to node_dir/deps
        if target_dir:
            self.deps_dir = target_dir / "deps"
        else:
            self.deps_dir = node_dir / "deps"
            
        self.cache_dir = get_doracxx_cache_dir() / "dependencies"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize dependency cache and build information
        self.resolved_deps: Dict[str, Dict[str, Path]] = {}  # Store both source and install paths
        self.include_dirs: List[str] = []
        self.lib_dirs: List[str] = []
        self.libraries: List[str] = []
    
    def resolve_all_dependencies(self) -> Dict[str, Dict[str, Path]]:
        """Resolve all dependencies and return mapping of name to {source, install} paths"""
        print("🔍 Resolving dependencies...")
        
        for dep_name, dep_config in self.config.dependencies.items():
            print(f"📦 Processing dependency: {dep_name}")
            
            try:
                if isinstance(dep_config, GitDependency):
                    source_dir, install_path = self._resolve_git_dependency(dep_name, dep_config)
                elif isinstance(dep_config, VcpkgDependency):
                    source_dir, install_path = self._resolve_vcpkg_dependency(dep_name, dep_config)
                elif isinstance(dep_config, SystemDependency):
                    source_dir, install_path = self._resolve_system_dependency(dep_name, dep_config)
                elif isinstance(dep_config, LocalDependency):
                    source_dir, install_path = self._resolve_local_dependency(dep_name, dep_config)
                else:
                    raise ValueError(f"Unknown dependency type for {dep_name}")
                
                self.resolved_deps[dep_name] = {
                    'source': source_dir,
                    'install': install_path
                }
                print(f"✅ Resolved {dep_name}: {install_path}")
                
            except Exception as e:
                print(f"❌ Failed to resolve {dep_name}: {e}")
                raise
        
        # Collect all include dirs, lib dirs, and libraries
        self._collect_dependency_info()
        
        return self.resolved_deps
    
    def _resolve_git_dependency(self, name: str, dep: GitDependency) -> Tuple[Path, Path]:
        """Resolve a git-based dependency, returns (source_dir, install_dir)"""
        # Create cache key based on URL and revision
        cache_key = self._create_cache_key(dep.url, dep.rev or dep.branch or dep.tag or "main")
        cache_path = self.cache_dir / "git" / cache_key
        
        # Clone or update repository
        if not cache_path.exists():
            print(f"  🔄 Cloning {dep.url}...")
            self._git_clone(dep.url, cache_path, dep.rev or dep.branch or dep.tag)
        else:
            print(f"  📁 Using cached repository: {cache_path}")
        
        # Determine source directory (handle subdir)
        source_dir = cache_path / dep.subdir if dep.subdir else cache_path
        
        # Create install directory
        install_dir = cache_path / "install"
        try:
            install_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"  ⚠️  Failed to create install directory: {e}")
            # Use alternative path if default fails
            install_dir = cache_path / "inst"
            install_dir.mkdir(parents=True, exist_ok=True)
        
        # Build if necessary
        if not list(install_dir.iterdir()):
            if dep.build_system:
                try:
                    self._build_dependency(source_dir, install_dir, dep.build_system, dep.cmake_options)
                except Exception as e:
                    print(f"  ⚠️  Build failed: {e}")
                    print(f"  📦 Treating as header-only library...")
                    # Fallback to header-only for libraries like Eigen
                    self._setup_header_only_lib(source_dir, install_dir, dep.include_dirs or ["Eigen"])
            else:
                # Header-only library, just create symlinks to include directories
                self._setup_header_only_lib(source_dir, install_dir, dep.include_dirs)
        
        return source_dir, install_dir
    
    def _resolve_vcpkg_dependency(self, name: str, dep: VcpkgDependency) -> Tuple[Path, Path]:
        """Resolve a vcpkg-based dependency, returns (source_dir, install_dir)"""
        vcpkg_exe = self._find_vcpkg()
        if not vcpkg_exe:
            raise RuntimeError("vcpkg not found. Please install vcpkg and add it to PATH.")
        
        # Determine triplet
        triplet = dep.triplet or self._detect_vcpkg_triplet()
        
        # Install package
        cmd = [str(vcpkg_exe), "install", dep.name]
        if dep.version:
            # vcpkg doesn't directly support version constraints in install command
            # This would require a vcpkg.json manifest for proper version control
            print(f"  ⚠️  Version constraint {dep.version} noted but vcpkg install doesn't directly support it")
        
        if dep.features:
            for feature in dep.features:
                cmd.append(f"{dep.name}[{feature}]")
        
        cmd.extend(["--triplet", triplet])
        
        print(f"  🔄 Installing with vcpkg: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"vcpkg install failed: {e.stderr}")
        
        # Return vcpkg installation path
        vcpkg_root = Path(vcpkg_exe).parent.parent
        install_path = vcpkg_root / "installed" / triplet
        # For vcpkg, source and install are the same
        return install_path, install_path
    
    def _resolve_system_dependency(self, name: str, dep: SystemDependency) -> Tuple[Path, Path]:
        """Resolve a system dependency, returns (source_dir, install_dir)"""
        # Try pkg-config first if specified
        if dep.pkg_config:
            try:
                result = subprocess.run(
                    ["pkg-config", "--exists", dep.pkg_config],
                    check=True, capture_output=True
                )
                print(f"  ✅ Found system package via pkg-config: {dep.pkg_config}")
                # Return a dummy path - actual paths will be resolved via pkg-config
                system_path = Path("/usr")  # Placeholder for system dependencies
                return system_path, system_path
            except (subprocess.CalledProcessError, FileNotFoundError):
                print(f"  ⚠️  pkg-config not found or package {dep.pkg_config} not available")
        
        # Check if libraries are available in standard locations
        found_libs = []
        for lib in dep.libraries:
            if self._find_system_library(lib):
                found_libs.append(lib)
        
        if len(found_libs) == len(dep.libraries):
            print(f"  ✅ Found all system libraries: {found_libs}")
            system_path = Path("/usr")  # Placeholder for system dependencies
            return system_path, system_path
        else:
            missing = set(dep.libraries) - set(found_libs)
            raise RuntimeError(f"System dependency {name}: missing libraries {missing}")
    
    def _resolve_local_dependency(self, name: str, dep: LocalDependency) -> Tuple[Path, Path]:
        """Resolve a local dependency, returns (source_dir, install_dir)"""
        source_path = Path(dep.path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Local dependency path not found: {source_path}")
        
        # Create installation directory in cache
        cache_key = f"local_{source_path.name}_{abs(hash(str(source_path)))}"
        install_dir = self.cache_dir / "local" / cache_key
        
        # Build if necessary
        if not install_dir.exists() or not list(install_dir.iterdir()):
            if dep.build_system:
                self._build_dependency(source_path, install_dir, dep.build_system, dep.cmake_options)
            else:
                # Header-only library
                install_dir.mkdir(parents=True, exist_ok=True)
                self._setup_header_only_lib(source_path, install_dir, dep.include_dirs)
        
        return source_path, install_dir
    
    def _build_dependency(self, source_dir: Path, install_dir: Path, 
                         build_system: BuildSystem, cmake_options: Dict[str, str]):
        """Build a dependency using the specified build system"""
        print(f"  🔨 Building with {build_system.value}...")
        
        if build_system == BuildSystem.CMAKE:
            self._build_with_cmake(source_dir, install_dir, cmake_options)
        elif build_system == BuildSystem.MAKE:
            self._build_with_make(source_dir, install_dir)
        elif build_system == BuildSystem.NINJA:
            self._build_with_ninja(source_dir, install_dir)
        else:
            raise ValueError(f"Unsupported build system: {build_system}")
    
    def _build_with_cmake(self, source_dir: Path, install_dir: Path, options: Dict[str, str]):
        """Build using CMake"""
        build_dir = source_dir / "build"
        build_dir.mkdir(exist_ok=True)
        
        # Configure
        cmake_args = [
            "cmake",
            f"-DCMAKE_INSTALL_PREFIX={install_dir}",
            f"-DCMAKE_BUILD_TYPE={self.config.build.profile.title()}",
        ]
        
        # Add custom options
        for key, value in options.items():
            cmake_args.append(f"-D{key}={value}")
        
        cmake_args.append(str(source_dir))
        
        print(f"    💻 Configure: {' '.join(cmake_args)}")
        subprocess.run(cmake_args, cwd=build_dir, check=True)
        
        # Build
        build_args = ["cmake", "--build", ".", "--config", self.config.build.profile.title()]
        if self.config.build.parallel_jobs:
            build_args.extend(["--parallel", str(self.config.build.parallel_jobs)])
        
        print(f"    💻 Build: {' '.join(build_args)}")
        subprocess.run(build_args, cwd=build_dir, check=True)
        
        # Install
        install_args = ["cmake", "--install", "."]
        print(f"    💻 Install: {' '.join(install_args)}")
        subprocess.run(install_args, cwd=build_dir, check=True)
    
    def _build_with_make(self, source_dir: Path, install_dir: Path):
        """Build using Make"""
        make_args = ["make"]
        if self.config.build.parallel_jobs:
            make_args.extend(["-j", str(self.config.build.parallel_jobs)])
        
        subprocess.run(make_args, cwd=source_dir, check=True)
        subprocess.run(["make", "install", f"PREFIX={install_dir}"], cwd=source_dir, check=True)
    
    def _build_with_ninja(self, source_dir: Path, install_dir: Path):
        """Build using Ninja"""
        ninja_args = ["ninja"]
        if self.config.build.parallel_jobs:
            ninja_args.extend(["-j", str(self.config.build.parallel_jobs)])
        
        subprocess.run(ninja_args, cwd=source_dir, check=True)
        subprocess.run(["ninja", "install"], cwd=source_dir, check=True)
    
    def _setup_header_only_lib(self, source_dir: Path, install_dir: Path, include_dirs: List[str]):
        """Setup a header-only library by copying include directories"""
        install_include = install_dir / "include"
        install_include.mkdir(parents=True, exist_ok=True)
        
        if include_dirs:
            for inc_dir in include_dirs:
                src_path = source_dir / inc_dir
                if src_path.exists():
                    dst_path = install_include / inc_dir
                    if src_path.is_dir():
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_path, dst_path)
        else:
            # Copy common include directory patterns
            for pattern in ["include", "src", "."]:
                src_path = source_dir / pattern
                if src_path.exists() and src_path.is_dir():
                    for header in src_path.rglob("*.h*"):
                        rel_path = header.relative_to(src_path)
                        dst_path = install_include / rel_path
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(header, dst_path)
                    break
    
    def _collect_dependency_info(self):
        """Collect include directories, library directories, and libraries from resolved dependencies"""
        for dep_name, dep_config in self.config.dependencies.items():
            dep_paths = self.resolved_deps.get(dep_name)
            if not dep_paths:
                continue
            
            source_path = dep_paths['source']
            install_path = dep_paths['install']
            
            # Add standard paths
            if isinstance(dep_config, (GitDependency, LocalDependency)):
                # Standard include and lib directories from install path
                for subdir in ["include", "inc"]:
                    inc_path = install_path / subdir
                    if inc_path.exists():
                        self.include_dirs.append(str(inc_path))
                
                for subdir in ["lib", "lib64", "libs"]:
                    lib_path = install_path / subdir
                    if lib_path.exists():
                        self.lib_dirs.append(str(lib_path))
                
                # Add explicitly configured paths relative to SOURCE directory (this fixes the issue!)
                for inc_dir in dep_config.include_dirs:
                    self.include_dirs.append(str(source_path / inc_dir))
                
                for lib_dir in dep_config.lib_dirs:
                    self.lib_dirs.append(str(install_path / lib_dir))
                
                self.libraries.extend(dep_config.libraries)
            
            elif isinstance(dep_config, VcpkgDependency):
                # vcpkg standard paths
                self.include_dirs.append(str(install_path / "include"))
                
                lib_dir = install_path / "lib"
                if lib_dir.exists():
                    self.lib_dirs.append(str(lib_dir))
                
                # Auto-detect libraries in vcpkg installation
                if lib_dir.exists():
                    for lib_file in lib_dir.glob("*.lib"):
                        lib_name = lib_file.stem
                        if not lib_name.startswith("lib"):
                            self.libraries.append(lib_name)
                        else:
                            self.libraries.append(lib_name[3:])  # Remove 'lib' prefix
            
            elif isinstance(dep_config, SystemDependency):
                # Handle system dependencies
                if dep_config.pkg_config:
                    try:
                        # Get include dirs from pkg-config
                        result = subprocess.run(
                            ["pkg-config", "--cflags-only-I", dep_config.pkg_config],
                            capture_output=True, text=True, check=True
                        )
                        for flag in result.stdout.split():
                            if flag.startswith("-I"):
                                self.include_dirs.append(flag[2:])
                        
                        # Get library dirs and libraries from pkg-config
                        result = subprocess.run(
                            ["pkg-config", "--libs", dep_config.pkg_config],
                            capture_output=True, text=True, check=True
                        )
                        for flag in result.stdout.split():
                            if flag.startswith("-L"):
                                self.lib_dirs.append(flag[2:])
                            elif flag.startswith("-l"):
                                self.libraries.append(flag[2:])
                    except subprocess.CalledProcessError:
                        # Fallback to manual configuration
                        pass
                
                # Add manually configured paths
                self.include_dirs.extend(dep_config.include_dirs)
                self.lib_dirs.extend(dep_config.lib_dirs)
                self.libraries.extend(dep_config.libraries)
    
    def _git_clone(self, url: str, dest: Path, ref: Optional[str] = None):
        """Clone a git repository"""
        cmd = ["git", "clone", url, str(dest)]
        if ref:
            cmd.extend(["--branch", ref])
        subprocess.run(cmd, check=True)
    
    def _create_cache_key(self, url: str, ref: str) -> str:
        """Create a cache key for a dependency"""
        import hashlib
        key_string = f"{url}#{ref}"
        hash_key = hashlib.md5(key_string.encode()).hexdigest()[:8]
        
        # Create a safe directory name for Windows with shorter length
        repo_name = url.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        # Sanitize for filesystem and keep it short
        safe_name = "".join(c for c in repo_name if c.isalnum() or c in '-_')[:8]
        return f"{safe_name}_{hash_key}"
    
    def _find_vcpkg(self) -> Optional[Path]:
        """Find vcpkg executable"""
        vcpkg_names = ["vcpkg", "vcpkg.exe"]
        for name in vcpkg_names:
            path = shutil.which(name)
            if path:
                return Path(path)
        
        # Check common installation locations
        common_paths = [
            Path("C:/vcpkg/vcpkg.exe"),
            Path("C:/tools/vcpkg/vcpkg.exe"),
            Path("/usr/local/bin/vcpkg"),
            Path.home() / "vcpkg" / "vcpkg",
        ]
        
        for path in common_paths:
            if path.exists():
                return path
        
        return None
    
    def _detect_vcpkg_triplet(self) -> str:
        """Detect appropriate vcpkg triplet for current platform"""
        import platform
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        if system == "windows":
            if machine in ["amd64", "x86_64"]:
                return "x64-windows"
            else:
                return "x86-windows"
        elif system == "linux":
            if machine in ["amd64", "x86_64"]:
                return "x64-linux"
            else:
                return "x86-linux"
        elif system == "darwin":
            return "x64-osx"
        else:
            return "x64-linux"  # Default fallback
    
    def _find_system_library(self, lib_name: str) -> bool:
        """Check if a system library is available"""
        # Common library search paths
        search_paths = [
            "/usr/lib",
            "/usr/local/lib",
            "/lib",
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib64",
        ]
        
        # On Windows, check system32 and common library locations
        if os.name == "nt":
            search_paths.extend([
                "C:/Windows/System32",
                "C:/Program Files/Microsoft Visual Studio/*/VC/lib",
            ])
        
        lib_patterns = [
            f"lib{lib_name}.so",
            f"lib{lib_name}.a",
            f"{lib_name}.lib",
            f"{lib_name}.dll",
        ]
        
        for search_path in search_paths:
            search_dir = Path(search_path)
            if search_dir.exists():
                for pattern in lib_patterns:
                    if list(search_dir.glob(pattern)):
                        return True
        
        return False
    
    def get_compiler_flags(self) -> Tuple[List[str], List[str], List[str]]:
        """Get compiler flags for include dirs, library dirs, and libraries"""
        include_flags = [f"-I{path}" for path in self.include_dirs]
        lib_dir_flags = [f"-L{path}" for path in self.lib_dirs]
        lib_flags = [f"-l{lib}" for lib in self.libraries]
        
        return include_flags, lib_dir_flags, lib_flags


def setup_dependencies(config: DoracxxConfig, node_dir: Path, target_dir: Optional[Path] = None) -> DependencyManager:
    """Setup and resolve all dependencies for a node"""
    dep_manager = DependencyManager(config, node_dir, target_dir)
    dep_manager.resolve_all_dependencies()
    return dep_manager


if __name__ == "__main__":
    # Test dependency resolution
    from .config import load_config
    
    try:
        config = load_config()
        dep_manager = setup_dependencies(config, Path.cwd())
        
        print("\n📋 Dependency Resolution Summary:")
        print(f"  Resolved dependencies: {len(dep_manager.resolved_deps)}")
        print(f"  Include directories: {len(dep_manager.include_dirs)}")
        print(f"  Library directories: {len(dep_manager.lib_dirs)}")
        print(f"  Libraries: {len(dep_manager.libraries)}")
        
    except Exception as e:
        print(f"Error: {e}")
