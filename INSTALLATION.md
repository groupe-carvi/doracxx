# 🎉 doracxx - Installation and Usage

## Installation

### Option 1: Simple installation with pip (Recommended)
```bash
pip install doracxx
```

### Option 2: Installation from source
```bash
git clone https://github.com/groupe-carvi/doracxx.git
cd doracxx
pip install -e .
```

### Option 3: Installation for development with uv
```bash
git clone https://github.com/groupe-carvi/doracxx.git
cd doracxx
uv pip install -e .
```

## Usage

### Main commands

#### 1. Help
```bash
doracxx help
```

#### 2. Compile a C++ node
```bash
doracxx build --node-dir nodes/your-node --profile release --out your-node
```

#### 3. Prepare Dora environment
```bash
doracxx prepare --profile release
```

### Complete examples

#### Recommended project structure
```
your-project/
├── nodes/
│   └── your-node/
│       ├── include/      # Project headers (.h/.hpp)
│       ├── deps/         # Dependency headers (auto-generated)
│       ├── src/          # Sources (.c/.cpp/.cc)
│       └── build/        # Temporary files
├── target/
│   ├── debug/           # Debug executables
│   └── release/         # Release executables
└── dataflow.yml         # Dora configuration
```

#### Compilation example
```bash
# Create structure
mkdir -p nodes/my-node/{include,src}

# Add your C++ code
echo '#include "dora-node-api.h"
int main() { return 0; }' > nodes/my-node/src/node.cc

# Compile
doracxx build --node-dir nodes/my-node --profile release --out my-node

# Executable will be in target/release/my-node.exe
```

#### Integration in dataflow.yml
```yaml
nodes:
  - id: my-cpp-node
    build: doracxx build --node-dir nodes/my-node --profile release --out my-node
    path: target/release/my-node
    inputs:
      image: camera/rgb
```

## Usage with uv (if installed with uv)

If you use uv for development:

```bash
# Help
uv run doracxx help

# Compilation
uv run doracxx build --node-dir nodes/your-node --profile release --out your-node

# Preparation
uv run doracxx prepare
```

## Compilation options

- `--node-dir`: C++ node directory (required)
- `--profile`: Compilation profile `debug` or `release` (required)
- `--out`: Output executable name (required)
- `--skip-build-packages`: Skip Rust package compilation (optional)

## Features

✅ **Multi-file support**: `.c`, `.cpp`, `.cc`  
✅ **Modern structure**: `include/`, `deps/`, `src/`, `build/`  
✅ **Dora integration**: Automatic compilation against cxxbridge  
✅ **Cross-platform**: Windows (MSVC/clang-cl), Linux/macOS (clang++/g++)  
✅ **Dependency management**: Automatic copying of Dora headers  
✅ **Smart placement**: Executables in `target/<profile>/`  

## Troubleshooting

### Command `doracxx` not found
- Check that the package is installed: `pip show doracxx`
- With uv: use `uv run doracxx` instead of `doracxx`
- Activate your virtual environment if necessary

### Compilation errors
- Check that MSVC or clang is installed on Windows
- Check that the project structure is correct (`src/` with .cc/.cpp/.c files)
- Check compilation logs for more details

### Dora dependency problems
- Run `doracxx prepare` to configure the Dora environment
- Check that Dora is compiled in `third_party/dora/`

## Support

- **Issues**: https://github.com/groupe-carvi/doracxx/issues
- **Documentation**: https://github.com/groupe-carvi/doracxx
- **Examples**: https://github.com/groupe-carvi/doracxx/tree/main/examples

---

**doracxx** - A modern build system for C++ nodes in the Dora framework 🚀
