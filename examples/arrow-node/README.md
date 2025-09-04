# Arrow Node Example

This example demonstrates how to create a Dora C++ node that uses Apache Arrow for efficient data processing.

## Features

- Automatic Arrow preparation and build integration
- Zero-copy data processing with Arrow arrays
- Memory-efficient operations using Arrow's compute engine
- Integration with Dora's dataflow system

## Configuration

The `doracxx.toml` file shows how to enable Arrow support:

```toml
[arrow]
enabled = true
git = "https://github.com/apache/arrow.git"
rev = "apache-arrow-15.0.0"
```

## Building

From this directory:

```bash
# Initialize if doracxx.toml doesn't exist
doracxx init

# Build the node (Arrow will be automatically prepared)
doracxx build --node-dir .

# Or use the global command
doracxx build .
```

## What happens during build

1. **Arrow Preparation**: doracxx automatically detects Arrow dependency and prepares it:
   - Clones Apache Arrow from GitHub
   - Builds Arrow C++ library with minimal configuration
   - Installs Arrow in global cache (`~/.doracxx/arrow-<version>/install`)

2. **Node Compilation**: 
   - Includes Arrow headers automatically
   - Links against Arrow libraries
   - Compiles with Dora APIs

3. **Result**: A node executable that can process data using both Dora and Arrow APIs

## Arrow Integration

The example shows:

- **Memory Management**: Using Arrow's memory pools
- **Array Creation**: Converting raw data to Arrow arrays
- **Compute Operations**: Using Arrow's compute engine for calculations
- **Zero-Copy**: Efficient data handling without unnecessary copies

## Manual Arrow Preparation

You can also prepare Arrow manually:

```bash
# Prepare latest Arrow
doracxx prepare arrow

# Prepare specific version
doracxx prepare arrow --arrow-rev apache-arrow-15.0.0

# Use local Arrow installation
doracxx prepare arrow --use-local
```

## Cache Management

```bash
# View cache info
doracxx cache info

# Clean only Arrow cache
doracxx cache clean-arrow

# Clean all cache
doracxx cache clean
```

## Performance Benefits

Using Arrow provides:

- **Columnar Memory Layout**: Efficient for analytical workloads
- **SIMD Optimization**: Vectorized operations
- **Zero-Copy**: Minimal memory allocations
- **Interoperability**: Standard format for data exchange

## Dependencies Alternative

Instead of the `[arrow]` section, you can also add Arrow as a dependency:

```toml
[dependencies.arrow]
type = "git"
url = "https://github.com/apache/arrow.git"
tag = "apache-arrow-15.0.0"
build_system = "cmake"
cmake_options = { ARROW_BUILD_SHARED = "ON", ARROW_COMPUTE = "ON" }
include_dirs = ["cpp/src"]
libraries = ["arrow"]
```

Both approaches will result in Arrow being available for your node.
