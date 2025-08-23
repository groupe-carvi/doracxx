# doracxx

A modern build system for C++ nodes in the Dora framework.

## Features

- **Automatic compilation**: Automatically detects and compiles `.c`, `.cpp` and `.cc` files
- **Modern project structure**: Organization with `include/`, `deps/`, `src/` and `build/`
- **Dora integration**: Compilation against Dora cxxbridge artifacts
- **Cross-platform**: Windows support with MSVC/clang-cl
- **Dependency management**: Automatic copying of Dora headers into `deps/`

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
   └── build/           # Build artifacts (auto-created)
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
dora-cxx-build --node-dir <path-to-node> --profile <debug|release> --out <executable-name>
```

### Options

- `--node-dir`: Path to the C++ node directory
- `--profile`: Build profile (`debug` or `release`)
- `--out`: Output executable name
- `--dora-target`: Custom Dora target directory (optional)
- `--skip-build-packages`: Skip building Dora packages (for pre-built environments)

### Environment Preparation

If you need to prepare the Dora environment:

```bash
dora-cxx-prepare
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
    build: dora-cxx-build --node-dir nodes/sensor --profile release --out sensor
    path: target/release/sensor
    outputs:
      data: sensor/raw_data

  - id: processor-node  
    build: dora-cxx-build --node-dir nodes/processor --profile release --out processor
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
    build: uv run dora-cxx-build --node-dir nodes/my-node --profile release --out my-node
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
dora-cxx-build --node-dir my-node --profile release --out my-node
```

### Development vs Production

```bash
# Development build with debug symbols
dora-cxx-build --node-dir my-node --profile debug --out my-node-debug

# Production build with optimizations
dora-cxx-build --node-dir my-node --profile release --out my-node
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
