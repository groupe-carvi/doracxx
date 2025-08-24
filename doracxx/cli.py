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
    # Find the script in the current package directory
    package_root = Path(__file__).resolve().parent
    script = package_root / name
    
    # If invoked via `uv run <cmd> -- --arg ...` the uv runner may forward a leading
    # '--' as the first argv; strip it so the target script receives only its flags.
    if args and args[0] == "--":
        args = args[1:]
    
    cmd = [sys.executable, str(script)] + args
    print("$", " ".join(cmd))
    subprocess.check_call(cmd)


def build_node():
    """Build a C++ Dora node with automatic dependency resolution"""
    # Transform positional argument to --node-dir
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
    elif subcommand == "cache":
        # Handle cache subcommands
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


def print_help():
    """Print help information for doracxx command"""
    help_text = """
doracxx - A cross-platform C++ build system for Dora dataflow nodes

Usage: doracxx <command> [options]

Commands:
  build, b       Build a C++ Dora node
  prepare, p     Prepare Dora environment and dependencies
  cache          Manage global cache (~/.doracxx)
    info         Show cache information
    clean        Clear entire cache
    clean-dora   Clear only Dora from cache
  help           Show this help message

Examples:
  doracxx build --node-dir nodes/my-node --profile release --out my-node
  doracxx prepare --profile release
  doracxx cache info
  doracxx cache clean-dora
  doracxx help

For detailed options for each command, use:
  doracxx build --help
  doracxx prepare --help

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
