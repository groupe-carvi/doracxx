#!/usr/bin/env python3
"""
Configuration management for doracxx.toml files

This module handles parsing and validation of doracxx.toml configuration files
that define node properties, build settings, and dependencies.
"""

import os
try:
    import tomllib
except ImportError:
    # For Python < 3.11
    import tomli as tomllib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    """Type of Dora node"""
    NODE = "node"
    PROCESSOR = "processor"


class Toolchain(Enum):
    """Supported toolchains"""
    GCC = "gcc"
    CLANG = "clang" 
    MSVC = "msvc"
    AUTO = "auto"


class BuildSystem(Enum):
    """Supported build systems"""
    NATIVE = "native"  # doracxx built-in compiler
    CMAKE = "cmake"
    MAKE = "make"
    NINJA = "ninja"


class DependencyType(Enum):
    """Types of dependencies"""
    GIT = "git"
    VCPKG = "vcpkg"
    CMAKE = "cmake"
    SYSTEM = "system"
    LOCAL = "local"


@dataclass
class GitDependency:
    """Git-based dependency configuration"""
    url: str
    rev: Optional[str] = None
    branch: Optional[str] = None
    tag: Optional[str] = None
    subdir: Optional[str] = None
    build_system: Optional[BuildSystem] = None
    cmake_options: Dict[str, Any] = field(default_factory=dict)
    include_dirs: List[str] = field(default_factory=list)
    lib_dirs: List[str] = field(default_factory=list)
    libraries: List[str] = field(default_factory=list)


@dataclass
class VcpkgDependency:
    """vcpkg-based dependency configuration"""
    name: str
    version: Optional[str] = None
    features: List[str] = field(default_factory=list)
    triplet: Optional[str] = None


@dataclass
class SystemDependency:
    """System dependency configuration"""
    name: str
    pkg_config: Optional[str] = None
    include_dirs: List[str] = field(default_factory=list)
    lib_dirs: List[str] = field(default_factory=list)
    libraries: List[str] = field(default_factory=list)


@dataclass
class LocalDependency:
    """Local dependency configuration"""
    path: str
    build_system: Optional[BuildSystem] = None
    cmake_options: Dict[str, Any] = field(default_factory=dict)
    include_dirs: List[str] = field(default_factory=list)
    lib_dirs: List[str] = field(default_factory=list)
    libraries: List[str] = field(default_factory=list)


@dataclass
class NodeConfig:
    """Node configuration section"""
    name: str
    type: NodeType = NodeType.NODE
    dora_version: Optional[str] = None
    dora_git: Optional[str] = None
    dora_rev: Optional[str] = None
    description: Optional[str] = None
    version: str = "0.1.0"


@dataclass  
class ArrowConfig:
    """Arrow configuration section"""
    git: Optional[str] = None
    rev: Optional[str] = None
    enabled: bool = True


@dataclass
class BuildConfig:
    """Build configuration section"""
    toolchain: Toolchain = Toolchain.AUTO
    system: BuildSystem = BuildSystem.NATIVE
    profile: str = "debug"
    std: str = "c++17"
    optimization: Optional[str] = None
    debug_info: bool = True
    warnings_as_errors: bool = False
    
    # Warning management
    suppress_warnings: bool = False  # Global warning suppression
    auto_suppress_verbose_deps: bool = True  # Auto-suppress warnings for known verbose dependencies
    warning_filter_patterns: List[str] = field(default_factory=list)  # Custom patterns to filter
    build_timeout: int = 300  # Build timeout in seconds (5 minutes default)
    
    # Source file configuration
    sources: Optional[List[str]] = None
    exclude_sources: Optional[List[str]] = None
    
    # Compiler flags
    cflags: List[str] = field(default_factory=list)
    cxxflags: List[str] = field(default_factory=list)
    ldflags: List[str] = field(default_factory=list)
    
    # Include and library paths
    include_dirs: List[str] = field(default_factory=list)
    lib_dirs: List[str] = field(default_factory=list)
    libraries: List[str] = field(default_factory=list)
    
    # CMAKE specific options
    cmake_options: Dict[str, Any] = field(default_factory=dict)
    cmake_build_type: Optional[str] = None
    
    # Advanced options
    parallel_jobs: Optional[int] = None
    install_clang: bool = False


@dataclass
class DoracxxConfig:
    """Complete doracxx configuration"""
    node: NodeConfig
    build: BuildConfig = field(default_factory=BuildConfig)
    arrow: Optional[ArrowConfig] = None
    dependencies: Dict[str, Union[GitDependency, VcpkgDependency, SystemDependency, LocalDependency]] = field(default_factory=dict)


def parse_dependency(name: str, dep_config: Dict[str, Any]) -> Union[GitDependency, VcpkgDependency, SystemDependency, LocalDependency]:
    """Parse a dependency configuration from TOML data"""
    dep_type = dep_config.get("type", "git")
    
    if dep_type == "git":
        return GitDependency(
            url=dep_config["url"],
            rev=dep_config.get("rev"),
            branch=dep_config.get("branch"),
            tag=dep_config.get("tag"),
            subdir=dep_config.get("subdir"),
            build_system=BuildSystem(dep_config.get("build_system", "cmake")) if dep_config.get("build_system") else None,
            cmake_options=dep_config.get("cmake_options", {}),
            include_dirs=dep_config.get("include_dirs", []),
            lib_dirs=dep_config.get("lib_dirs", []),
            libraries=dep_config.get("libraries", [])
        )
    elif dep_type == "vcpkg":
        return VcpkgDependency(
            name=dep_config["name"],
            version=dep_config.get("version"),
            features=dep_config.get("features", []),
            triplet=dep_config.get("triplet")
        )
    elif dep_type == "system":
        return SystemDependency(
            name=dep_config["name"],
            pkg_config=dep_config.get("pkg_config"),
            include_dirs=dep_config.get("include_dirs", []),
            lib_dirs=dep_config.get("lib_dirs", []),
            libraries=dep_config.get("libraries", [])
        )
    elif dep_type == "local":
        return LocalDependency(
            path=dep_config["path"],
            build_system=BuildSystem(dep_config.get("build_system", "cmake")) if dep_config.get("build_system") else None,
            cmake_options=dep_config.get("cmake_options", {}),
            include_dirs=dep_config.get("include_dirs", []),
            lib_dirs=dep_config.get("lib_dirs", []),
            libraries=dep_config.get("libraries", [])
        )
    else:
        raise ValueError(f"Unknown dependency type: {dep_type}")


def find_project_root(start_path: Optional[Path] = None) -> Path:
    """Find the project root directory containing doracxx.toml"""
    if start_path is None:
        start_path = Path.cwd()
    
    current = start_path if start_path.is_dir() else start_path.parent
    for path in [current] + list(current.parents):
        config_file = path / "doracxx.toml"
        if config_file.exists():
            return path
    
    # If no doracxx.toml found, return current working directory as fallback
    return Path.cwd()


def load_config(config_path: Optional[Union[str, Path]] = None) -> DoracxxConfig:
    """Load doracxx configuration from a TOML file"""
    if config_path is None:
        # Find project root and use its doracxx.toml
        project_root = find_project_root()
        config_path = project_root / "doracxx.toml"
        
        if not config_path.exists():
            raise FileNotFoundError("No doracxx.toml found in current directory or parent directories")
    
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    
    # Parse node section
    node_data = data.get("node", {})
    if "name" not in node_data:
        raise ValueError("Node name is required in [node] section")
    
    node = NodeConfig(
        name=node_data["name"],
        type=NodeType(node_data.get("type", "node")),
        dora_version=node_data.get("dora_version"),
        dora_git=node_data.get("dora_git"),
        dora_rev=node_data.get("dora_rev"),
        description=node_data.get("description"),
        version=node_data.get("version", "0.1.0")
    )
    
    # Parse build section
    build_data = data.get("build", {})
    build = BuildConfig(
        toolchain=Toolchain(build_data.get("toolchain", "auto")),
        system=BuildSystem(build_data.get("system", "native")),
        profile=build_data.get("profile", "debug"),
        std=build_data.get("std", "c++17"),
        optimization=build_data.get("optimization"),
        debug_info=build_data.get("debug_info", True),
        warnings_as_errors=build_data.get("warnings_as_errors", False),
        cflags=build_data.get("cflags", []),
        cxxflags=build_data.get("cxxflags", []),
        ldflags=build_data.get("ldflags", []),
        include_dirs=build_data.get("include_dirs", []),
        lib_dirs=build_data.get("lib_dirs", []),
        libraries=build_data.get("libraries", []),
        cmake_options=build_data.get("cmake_options", {}),
        cmake_build_type=build_data.get("cmake_build_type"),
        parallel_jobs=build_data.get("parallel_jobs"),
        install_clang=build_data.get("install_clang", False)
    )
    
    # Parse arrow section
    arrow_data = data.get("arrow", {})
    arrow = None
    if arrow_data:
        arrow = ArrowConfig(
            git=arrow_data.get("git"),
            rev=arrow_data.get("rev"),
            enabled=arrow_data.get("enabled", True)
        )
    
    # Parse dependencies section
    deps_data = data.get("dependencies", {})
    dependencies = {}
    for dep_name, dep_config in deps_data.items():
        dependencies[dep_name] = parse_dependency(dep_name, dep_config)
    
    return DoracxxConfig(
        node=node,
        build=build,
        arrow=arrow,
        dependencies=dependencies
    )


def create_example_config(path: Optional[Union[str, Path]] = None) -> Path:
    """Create an example doracxx.toml configuration file"""
    if path is None:
        path = Path.cwd() / "doracxx.toml"
    else:
        path = Path(path)
    
    node_name = Path.cwd().name
    example_config = f'''# doracxx.toml - Minimal configuration for Dora C++ node

[node]
name = "{node_name}"
type = "node"
description = "Minimal Dora C++ node configuration"
version = "0.1.0"

[build]
toolchain = "auto"
system = "native"
profile = "debug"
std = "c++17"

# Optional: Enable Apache Arrow support
# [arrow]
# enabled = true
# git = "https://github.com/apache/arrow.git"
# rev = "apache-arrow-15.0.0"
'''
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(example_config)
    
    return path


def validate_config(config: DoracxxConfig) -> List[str]:
    """Validate a doracxx configuration and return list of warnings/errors"""
    warnings = []
    
    # Validate node configuration
    if not config.node.name:
        warnings.append("Node name cannot be empty")
    
    if config.node.dora_git and not config.node.dora_git.startswith(("https://", "git@")):
        warnings.append("dora_git should be a valid git URL")
    
    # Validate build configuration
    if config.build.profile not in ["debug", "release"]:
        warnings.append(f"Unknown build profile: {config.build.profile}")
    
    if config.build.parallel_jobs is not None and config.build.parallel_jobs < 1:
        warnings.append("parallel_jobs must be >= 1")
    
    # Validate dependencies
    for dep_name, dep in config.dependencies.items():
        if isinstance(dep, GitDependency):
            if not dep.url:
                warnings.append(f"Git dependency '{dep_name}' missing URL")
            ref_count = sum(1 for x in [dep.rev, dep.branch, dep.tag] if x is not None)
            if ref_count > 1:
                warnings.append(f"Git dependency '{dep_name}' should specify only one of: rev, branch, tag")
        
        elif isinstance(dep, VcpkgDependency):
            if not dep.name:
                warnings.append(f"vcpkg dependency '{dep_name}' missing package name")
        
        elif isinstance(dep, SystemDependency):
            if not dep.name:
                warnings.append(f"System dependency '{dep_name}' missing name")
        
        elif isinstance(dep, LocalDependency):
            if not dep.path:
                warnings.append(f"Local dependency '{dep_name}' missing path")
            elif not Path(dep.path).exists():
                warnings.append(f"Local dependency '{dep_name}' path does not exist: {dep.path}")
    
    return warnings


if __name__ == "__main__":
    # Create example configuration
    example_path = create_example_config()
    print(f"Created example configuration: {example_path}")
    
    # Load and validate the example
    try:
        config = load_config(example_path)
        warnings = validate_config(config)
        
        if warnings:
            print("\nValidation warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        else:
            print("\nConfiguration is valid!")
            
        print(f"\nLoaded configuration for node: {config.node.name}")
        print(f"Build system: {config.build.system.value}")
        print(f"Dependencies: {len(config.dependencies)}")
        
    except Exception as e:
        print(f"Error loading configuration: {e}")
