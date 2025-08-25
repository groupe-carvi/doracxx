"""
doracxx CLI
A cross-platform build system for Dora dataflow nodes

Usage: doracxx.py --node-dir nodes/edris-rsdriver [--profile debug|release] [--dora-target DIR]

This script will:
- optionally build Dora-related Rust packages if available in the workspace
- discover cxxbridge outputs under Dora's target directory and use them directly
    (no file copying).
- compile the node C++ sources together with generated cxxbridge .cc files and
    link against the Dora libraries found in the Dora target directory.
"""
import subprocess
import sys
import shutil
from pathlib import Path
from .cache import get_doracxx_cache_dir, cache_info, cache_clean, cache_clean_dora


def _run_script(name: str, args=None):
    """Run a script from the doracxx package"""
    args = args or []
    
    # If invoked via `uv run <cmd> -- --arg ...` the uv runner may forward a leading
    # '--' as the first argv; strip it so the target script receives only its flags.
    if args and args[0] == "--":
        args = args[1:]
    
    # Import and run the function directly instead of subprocess
    if name == "build-cxx-node.py":
        from . import build_cxx_node
        # Save original sys.argv and replace it temporarily
        original_argv = sys.argv
        try:
            sys.argv = [name] + args
            build_cxx_node.main()
        finally:
            sys.argv = original_argv
    elif name == "prepare-dora.py":
        from . import prepare_dora
        original_argv = sys.argv
        try:
            sys.argv = [name] + args
            prepare_dora.main()
        finally:
            sys.argv = original_argv
    else:
        # Fallback to subprocess for unknown scripts
        package_root = Path(__file__).resolve().parent
        script = package_root / name
        cmd = [sys.executable, str(script)] + args
        print("$", " ".join(cmd))
        subprocess.check_call(cmd)


def build_node():
    """Build a C++ Dora node with automatic dependency resolution"""
    # Transform positional argument to --node-dir if provided
    args = list(sys.argv[1:])
    if args and not args[0].startswith('-'):
        # First non-option argument is the node directory
        node_dir = args.pop(0)
        args = ["--node-dir", node_dir] + args
    _run_script("build-cxx-node.py", args)


def prepare_dora():
    """Prepare Dora environment and dependencies"""
    _run_script("prepare-dora.py", list(sys.argv[1:]))


def main():
    """Main entry point for doracxx command with subcommands"""
    if len(sys.argv) < 2:
        print_help()
        return
    
    subcommand = sys.argv[1]
    
    if subcommand in ["build", "b"]:
        # Remove 'build' from args and call build_node
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        build_node()
    elif subcommand in ["prepare", "prep", "p"]:
        # Remove 'prepare' from args and call prepare_dora
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        prepare_dora()
    elif subcommand in ["init", "new"]:
        # Create a new doracxx.toml configuration
        init_config()
    elif subcommand == "clean":
        # Handle clean command with options
        if len(sys.argv) >= 3:
            if sys.argv[2] == "--cache":
                cache_clean()
            elif sys.argv[2] == "--dora":
                cache_clean_dora()
            else:
                print(f"Unknown clean option: {sys.argv[2]}")
                print("Clean options:")
                print("  --cache      Clear entire cache")
                print("  --dora       Clear only Dora from cache")
                print("\nUsage: doracxx clean [--cache|--dora]")
        else:
            print("Clean options:")
            print("  --cache      Clear entire cache")
            print("  --dora       Clear only Dora from cache")
            print("\nUsage: doracxx clean [--cache|--dora]")
    elif subcommand == "cache":
        # Handle cache subcommands (legacy support)
        if len(sys.argv) < 3:
            print("Cache subcommands: info, clean, clean-dora")
            return
            
        cache_subcommand = sys.argv[2]
        if cache_subcommand == "info":
            cache_info()
        elif cache_subcommand == "clean":
            cache_clean()
        elif cache_subcommand == "clean-dora":
            cache_clean_dora()
        else:
            print(f"Unknown cache subcommand: {cache_subcommand}")
            print("Available: info, clean, clean-dora")
    elif subcommand in ["help", "-h", "--help"]:
        print_help()
    else:
        print(f"Unknown subcommand: {subcommand}")
        print_help()
        sys.exit(1)


def init_config():
    """Initialize a new doracxx.toml configuration file"""
    try:
        from .config import create_example_config
    except ImportError:
        # When run directly, import from the same directory
        sys.path.insert(0, str(Path(__file__).parent))
        from config import create_example_config
    
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Parse arguments for init command
    output_path = None
    force = False
    
    i = 0
    while i < len(args):
        if args[i] in ["-o", "--output"]:
            if i + 1 < len(args):
                output_path = args[i + 1]
                i += 2
            else:
                print("Error: --output requires a path")
                return
        elif args[i] in ["-f", "--force"]:
            force = True
            i += 1
        elif args[i] in ["-h", "--help"]:
            print("""
doracxx init - Create a new doracxx.toml configuration file

Usage: doracxx init [options]

Options:
  -o, --output PATH    Output path for the configuration file (default: doracxx.toml)
  -f, --force         Overwrite existing file
  -h, --help          Show this help message

Examples:
  doracxx init                           # Create doracxx.toml in current directory
  doracxx init -o my-node/doracxx.toml   # Create in specific location
  doracxx init -f                        # Overwrite existing file
""")
            return
        else:
            print(f"Unknown option: {args[i]}")
            print("Use 'doracxx init --help' for usage information")
            return
    
    # Determine output path
    if output_path is None:
        output_path = Path.cwd() / "doracxx.toml"
    else:
        output_path = Path(output_path)
    
    # Check if file exists and force not specified
    if output_path.exists() and not force:
        print(f"Configuration file already exists: {output_path}")
        print("Use --force to overwrite or specify a different path with --output")
        return
    
    try:
        created_path = create_example_config(output_path)
        print(f"✅ Created configuration file: {created_path}")
        print("\n📋 Next steps:")
        print("1. Edit the configuration file to match your project")
        print("2. Add your dependencies to the [dependencies] section")
        print("3. Build your node with: doracxx build --node-dir .")
    except Exception as e:
        print(f"❌ Error creating configuration file: {e}")


def print_help():
    """Print help information for doracxx command"""
    help_text = """
doracxx - A cross-platform C++ build system for Dora dataflow nodes

Usage: doracxx <command> [options]

Commands:
  init, new      Create a new doracxx.toml configuration file
  build, b       Build a C++ Dora node
  prepare, p     Prepare Dora environment and dependencies
  clean          Clean cache
    --cache      Clear entire cache
    --dora       Clear only Dora from cache
  cache          Manage global cache (~/.doracxx) [legacy]
    info         Show cache information
    clean        Clear entire cache
    clean-dora   Clear only Dora from cache
  help           Show this help message

Examples:
  doracxx init                                   # Create new doracxx.toml
  doracxx build --node-dir nodes/my-node        # Build with CLI args
  doracxx build --node-dir .                    # Build using doracxx.toml
  doracxx prepare --profile release
  doracxx cache info
  doracxx cache clean-dora
  doracxx help

Configuration:
  doracxx automatically looks for doracxx.toml in the node directory or current
  working directory. This file can define dependencies, build settings, and
  node properties. Use 'doracxx init' to create an example configuration.

For detailed options for each command, use:
  doracxx build --help
  doracxx prepare --help
  doracxx init --help

Note: doracxx now uses a global cache (~/.doracxx) to share dependencies
between projects. Use --use-local flag with prepare to use project-local mode.
"""
    print(help_text)


# Legacy compatibility functions
def cxx_node_builder():
    """Legacy compatibility - use build_node() instead"""
    build_node()


if __name__ == "__main__":
    main()
