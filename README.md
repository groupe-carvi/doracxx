# doracxx

A sophisticated build system for dora-rs C/C++ nodes with intelligent configuration and dependency management.

## Why doracxx
After trying different ways to actually build the C and C++ nodes using the examples from dora-rs, we found that there was not an ideal way to actually make it easy to build our C++ nodes. This is why we decided to create doracxx, it just works out of the box and can just be dropped inside a dataflow to build any C and C++ nodes.

## Features

- **Configuration-driven builds**: Use `doracxx.toml` for declarative project configuration
- **Smart auto-detection**: Automatically finds node directories when `doracxx.toml` is present
- **Flexible source management**: Configure which files to include/exclude from builds
- **Automatic compilation**: Intelligently detects and compiles `.c`, `.cpp` and `.cc` files
- **Modern project structure**: Organization with `include/`, `deps/`, `src/` and `build/`
- **Dora resolution**: Compilation and linkage against Dora cxxbridge artifacts
- **Cross-platform**: Windows support with MSVC/clang-cl, Linux/macOS with GCC/Clang
- **Dependency management**: Automatic copying of Dora headers and dependency resolution
- **Global caching**: Shared dependency cache (~/.doracxx) for faster builds across projects

## Planned

- **Dora C/CXX node template**: Create new nodes with 'doracxx new'.
- **Making it a dora-rs core feature**: We could look into rewriting it in Rust and make a PR to dora-rs so that it becomes part of the framework directly.

## Installation

```bash
# Install from PyPI (when published)
pip install doracxx

# Or install from source
git clone https://github.com/groupe-carvi/doracxx.git
cd doracxx
pip install -e .
```

## Quick Start

1. **Install doracxx**:
   ```bash
   pip install doracxx
   ```

2. **Create a new node configuration**:
   ```bash
   doracxx init
   ```
   This creates a `doracxx.toml` configuration file with sensible defaults.

3. **Create your C++ node directory structure**:
   ```
   my-node/
   ├── doracxx.toml     # Project configuration
   ├── include/         # Your project headers (.h/.hpp)
   ├── src/            # Your source files (.cc/.cpp/.c)
   └── deps/           # Dependencies .h (auto-created)
   ```

4. **Build your node** (with auto-detection):
   ```bash
   # From the node directory
   cd my-node
   doracxx build
   
   # Or specify the directory
   doracxx build --node-dir my-node
   ```

5. **Use in Dora dataflow**:
   ```yaml
   nodes:
     - id: my-cpp-node
       build: doracxx build --node-dir nodes/my-node --profile release
       path: target/release/my-node
   ```

## Examples

See the `examples/` directory for complete working examples:

- **simple-node**: Basic C++ node demonstrating project structure
- **dataflow.yml**: Example Dora configuration

To try the example:
```bash
cd examples
doracxx build --node-dir simple-node --profile release --out simple-node
./target/release/simple-node
```

## Configuration with doracxx.toml

doracxx now supports configuration files for more sophisticated project management:

```toml
[project]
name = "my-node"
version = "0.1.0"

[build]
sources = ["src/**/*.cc", "src/**/*.cpp", "src/**/*.c"]
exclude_sources = ["src/test_*.cc", "**/*_test.cpp"]
executable_name = "my-node"

[dependencies]
# Future: dependency management will be configured here
```

### Configuration Options

- **`sources`**: Glob patterns for source files to include (defaults to all .c/.cc/.cpp in src/)
- **`exclude_sources`**: Glob patterns for files to exclude (e.g., test files)
- **`executable_name`**: Name of the output executable
- **Auto-detection**: When `doracxx.toml` is present, `doracxx build` automatically detects the node directory

## Usage

### Modern Usage (Recommended)

With configuration file:
```bash
# Create configuration
doracxx init

# Build with auto-detection
doracxx build

# Build specific profile
doracxx build --profile release
```

### Legacy Usage (Still Supported)

```bash
doracxx build --node-dir <path-to-node> --profile <debug|release> --out <executable-name>
```

### Available Commands

- `doracxx init`: Create a new `doracxx.toml` configuration file
- `doracxx build`: Build a C++ node (with auto-detection when `doracxx.toml` is present)
- `doracxx prepare`: Prepare Dora environment and dependencies
- `doracxx clean --cache`: Clear entire dependency cache
- `doracxx clean --dora`: Clear only Dora from cache
- `doracxx cache info`: Show cache information (legacy compatibility)

### Build Options

- `--node-dir`: Path to the C++ node directory (auto-detected if `doracxx.toml` present)
- `--profile`: Build profile (`debug` or `release`)
- `--out`: Output executable name (can be configured in `doracxx.toml`)
- `--dora-target`: Custom Dora target directory (optional)
- `--skip-build-packages`: Skip building Dora packages (for pre-built environments)
- `--no-auto-prepare`: Disable automatic Dora preparation

### Cache Management

doracxx uses a global cache (`~/.doracxx`) to share dependencies between projects:

```bash
# Show cache information
doracxx cache info

# Clean entire cache
doracxx clean --cache

# Clean only Dora from cache  
doracxx clean --dora
```

### Dora Preparation

If you don't have the dora C++ bridge available, running this will clone and prepare dora in your project. It can take some time to build at first and it will be installed in the global cache.

```bash
doracxx prepare --dora-git <git-url> --dora-rev <rev> --profile <debug or release>
```

## Project Structure

The builder expects and creates this directory structure:

```
your-node/
├── doracxx.toml          # Project configuration (recommended)
├── include/              # Project headers (.h/.hpp)
│   ├── my_header.h
│   └── utilities.hpp
├── deps/                 # Dependency headers (auto-generated)
│   ├── dora-node-api.h   # Auto-copied from Dora
│   └── dora-operator-api.h
├── src/                  # Source files
│   ├── node.cc           # Main node implementation
│   ├── helpers.cpp       # Additional C++ sources
│   └── legacy.c          # C sources (if any)
├── build/               # Temporary build artifacts
└── target/              # Output directory
    ├── debug/           # Debug builds
    └── release/         # Release builds
```

### doracxx.toml Example

```toml
[node]
name = "sensor-processor"
type = "node"             # or "processor"
description = "High-performance sensor data processor"
version = "1.0.0"

[build]
# Toolchain selection: "auto", "gcc", "clang", "msvc"
toolchain = "auto"

# Build system: "native", "cmake", "make", "ninja" 
system = "native"

# Build profile: "debug" or "release"
profile = "release"

# C++ standard: "c++11", "c++14", "c++17", "c++20", "c++23"
std = "c++17"

# Compiler flags
cflags = ["-Wall"]
cxxflags = ["-Wall", "-Wextra", "-O3"]
ldflags = ["-pthread"]

# Include and library paths
include_dirs = ["include", "external/headers"]
lib_dirs = ["external/libs"]
libraries = ["m", "pthread"]

# Source files configuration
sources = [
    "src/**/*.cc",
    "src/**/*.cpp",
    "src/special/*.c"
]
exclude_sources = [
    "src/test_*.cc",
    "src/**/*_test.cpp",
    "src/benchmarks/*.cc"
]

# Enable automatic clang installation if not found (Windows)
install_clang = false

[dependencies]
# Git-based dependency example
[dependencies.eigen3]
type = "git"
url = "https://gitlab.com/libeigen/eigen.git"
tag = "3.4.0"
build_system = "cmake"
include_dirs = ["include/eigen3"]

[dependencies.eigen3.cmake_options]
BUILD_TESTING = "OFF"
EIGEN_BUILD_DOC = "OFF"
EIGEN_BUILD_PKGCONFIG = "OFF"

# Future: more dependency types
# [dependencies.opencv]
# type = "vcpkg"
# package = "opencv4"

# [dependencies.boost]
# type = "conan"
# package = "boost/1.82.0"
```

### Configuration Sections

#### `[node]` Section
- **`name`**: Node executable name (used for output binary)
- **`type`**: Node type ("node" or "processor") for future optimizations
- **`description`**: Human-readable description of the node
- **`version`**: Semantic version of your node

#### `[build]` Section
- **`toolchain`**: Compiler preference ("auto", "gcc", "clang", "msvc")
- **`system`**: Build system ("native", "cmake", "make", "ninja")
- **`profile`**: Build configuration ("debug" or "release")
- **`std`**: C++ standard version
- **`sources`**: Glob patterns for source files to include
- **`exclude_sources`**: Glob patterns for files to exclude (e.g., tests)
- **`include_dirs`**: Additional include directories
- **`libraries`**: System libraries to link against

#### `[dependencies]` Section
Configure external dependencies with different source types:
- **Git repositories**: Clone and build from source
- **Package managers**: vcpkg, Conan support (planned)
- **System libraries**: Link against installed libraries

## Integration Examples

### With Dora Dataflow (Modern Configuration)

```yaml
# dataflow.yml
nodes:
  - id: sensor-node
    build: doracxx build --node-dir nodes/sensor --profile release
    path: target/release/sensor-node  # Name from doracxx.toml
    outputs:
      data: sensor/raw_data

  - id: processor-node  
    build: doracxx build --node-dir nodes/processor --profile release
    path: target/release/data-processor  # Name from doracxx.toml
    inputs:
      raw: sensor-node/data
    outputs:
      processed: processor/output
```

### With uv (Python package manager)

```yaml
# In dataflow.yml  
nodes:
  - id: my-node
    build: uv run doracxx build --node-dir nodes/my-node --profile release
    path: target/release/my-node
```

### Auto-Detection Workflow

```bash
# Navigate to your node directory
cd nodes/my-awesome-node

# Initialize configuration
uv run doracxx init

# Edit doracxx.toml to your needs
# ...

# Build with auto-detection (no need to specify --node-dir)
uv run doracxx build --profile release
```

## Supported Compilers

### Windows
- **MSVC** (`cl.exe`) - Primary choice
- **Clang-CL** (`clang-cl.exe`) - MSVC-compatible mode
- **Clang++** (`clang++.exe`) - GNU-compatible mode
- **GCC** (`g++.exe`) - Via MinGW/MSYS2

### Linux/macOS
- **Clang++** (`clang++`) - Primary choice
- **GCC** (`g++`) - Fallback option

The builder automatically detects available compilers and chooses the best option for your platform.

## Advanced Configuration

### Source File Management

Control exactly which files are built:

```toml
[build]
# Include specific patterns
sources = [
    "src/core/*.cc",
    "src/modules/**/*.cpp",
    "src/platform/linux/*.c"  # Platform-specific
]

# Exclude test and benchmark files
exclude_sources = [
    "**/*_test.*",
    "**/*_bench.*",
    "src/experimental/*"
]
```

### Custom Compiler

```bash
export CXX=/path/to/custom/compiler
doracxx build --profile release
```

### Development vs Production

```bash
# Development build with debug symbols and faster compilation
doracxx build --profile debug

# Production build with optimizations
doracxx build --profile release
```

### Cache Management for CI/CD

```bash
# Show cache status
doracxx cache info

# Clean cache in CI environments
doracxx clean --cache

# Clean only Dora for version updates
doracxx clean --dora
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/groupe-carvi/dora-cxx-builder/issues)
- **Documentation**: [GitHub Wiki](https://github.com/groupe-carvi/dora-cxx-builder/wiki)
- **Dora Project**: [dora-rs/dora](https://github.com/dora-rs/dora)
