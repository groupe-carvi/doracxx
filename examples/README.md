# Examples for doracxx

This directory contains example Dora C++ nodes to demonstrate how to use doracxx.

## Simple Node Example

The `simple-node` example demonstrates a basic C++ node structure:

```
simple-node/
├── include/
│   └── simple_processor.h    # Example header file
├── src/
│   └── node.cc              # Main node implementation
└── deps/                    # Auto-generated Dora headers (after build)
```

### Building the Example

1. **Install doracxx** (if not already done):
   ```bash
   pip install doracxx
   ```

2. **Build the example node**:
   ```bash
   doracxx build --node-dir examples/simple-node --profile release --out simple-node
   ```

3. **Run the built executable**:
   ```bash
   # On Windows
   target\release\simple-node.exe
   
   # On Linux/macOS
   ./target/release/simple-node
   ```

### Using with Dora

See `dataflow.yml` for an example of how to integrate the C++ node into a Dora dataflow.

### Project Structure

- **include/** - Place your project header files here
- **src/** - Place your source files (.cc, .cpp, .c) here
- **deps/** - Auto-generated directory for Dora dependency headers
- **build/** - Temporary build files (auto-generated)

The compiled executable will be placed in `target/<profile>/` following Rust conventions.

### Next Steps

1. Modify `src/node.cc` to implement your own logic
2. Add any custom headers to `include/`
3. Update `dataflow.yml` to define inputs/outputs for your node
4. Build and test your node with `doracxx build`
