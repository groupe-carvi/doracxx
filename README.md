# doracxx

A simple build system for dora-rs C/C++ nodes. 

## Why doracxx
After trying different ways to actually build the C and C++ nodes using the examples from dora-rs, we found that there was not an ideal way to actually make it easy to build our C++ nodes. This is why we decided to create doracxx, it just work out of the box and can just be dropped inside a dataflow to build any C and C++ nodes.

## Features

- **Automatic compilation**: Automatically detects and compiles `.c`, `.cpp` and `.cc` files
- **Modern project structure**: Organization with `include/`, `deps/`, `src/` and `build/`
- **Dora resolution**: Compilation and linkage against Dora cxxbridge artifacts
- **Cross-platform**: Windows support with MSVC/clang-cl
- **Dependency management**: Automatic copying of Dora headers into `deps/`

## Planned

- **Dependancy managemement**: From a TOML file, we would be able to specify C++ dependencies and they would be resolved during build time. It would support git fetching for doracxx own toml package system, cmake, vcpkg and conan.
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

2. **Create a C++ node directory structure**:
   ```
   my-node/
   ├── include/          # Your project headers (.h/.hpp)
   ├── src/             # Your source files (.cc/.cpp/.c)
   └── deps/            # dependancies .h (auto-created)
   ```

3. **Build your node**:
   ```bash
   doracxx build --node-dir my-node --profile release --out my-node-exe
   ```

4. **Use in Dora dataflow**:
   ```yaml
   nodes:
     - id: my-cpp-node
       build: doracxx build --node-dir nodes/my-node --profile release --out my-node
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

## Usage

### Basic Build Command

```bash
doracxx build --node-dir <path-to-node> --profile <debug|release> --out <executable-name>
```

### Options

- `--node-dir`: Path to the C++ node directory
- `--profile`: Build profile (`debug` or `release`)
- `--out`: Output executable name
- `--dora-target`: Custom Dora target directory (optional)
- `--skip-build-packages`: Skip building Dora packages (for pre-built environments)

### Dora Preparation

If you dont have the dora C++ bridge available, runing this will clone and prepare dora in your project. It can take some time to build at first and it will be installed in the third_party folder relative to where you runned the command.

```bash
doracxx prepare --dora-git <git-url> --dora-rev <rev> --profile <debug or release>
```

## Project Structure

The builder expects and creates this directory structure:

```
your-node/
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
└── build/               # Temporary build artifacts
```

## Integration Examples

### With Dora Dataflow

```yaml
# dataflow.yml
nodes:
  - id: sensor-node
    build: doracxx build --node-dir nodes/sensor --profile release --out sensor
    path: target/release/sensor
    outputs:
      data: sensor/raw_data

  - id: processor-node  
    build: doracxx build --node-dir nodes/processor --profile release --out processor
    path: target/release/processor
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
    build: uv run doracxx build --node-dir nodes/my-node --profile release --out my-node
    path: target/release/my-node
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

### Custom Compiler

```bash
export CXX=/path/to/custom/compiler
doracxx build --node-dir my-node --profile release --out my-node
```

### Development vs Production

```bash
# Development build with debug symbols
doracxx build --node-dir my-node --profile debug --out my-node-debug

# Production build with optimizations
doracxx build --node-dir my-node --profile release --out my-node
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
