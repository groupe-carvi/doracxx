#!/usr/bin/env python3
"""Cache management utilities for doracxx."""

from pathlib import Path
import subprocess
import shutil


def get_doracxx_cache_dir():
    """Get the global doracxx cache directory (~/.doracxx)."""
    home = Path.home()
    cache_dir = home / ".doracxx"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_latest_git_tag(url: str) -> str | None:
    """Get the latest git tag from a remote repository."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=-version:refname", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line and 'refs/tags/' in line:
                    # Extract tag name from "hash refs/tags/v1.2.3" format
                    tag = line.split('refs/tags/')[-1]
                    # Skip pre-release tags (containing alpha, beta, rc, etc.)
                    if not any(pre in tag.lower() for pre in ['alpha', 'beta', 'rc', 'pre', 'dev']):
                        return tag
    except Exception:
        pass
    return None


def get_dora_cache_path(url: str | None = None, rev: str | None = None):
    """Get the path for cached Dora installation, versioned by URL and revision.
    
    Creates a versioned cache directory:
    - If rev is specified: dora-{rev} 
    - If no rev specified: determines the latest version from git and uses dora-{latest_version}
    """
    cache_dir = get_doracxx_cache_dir()
    
    # Create a unique directory name based on URL and revision
    # Use the repo name from URL (e.g., "dora" from "https://github.com/dora-rs/dora")
    if url:
        repo_name = url.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
    else:
        repo_name = "dora"
        url = "https://github.com/dora-rs/dora"  # Default URL for tag lookup
    
    if rev:
        # Include revision in the path for version-specific caching
        # Sanitize revision name for filesystem compatibility
        safe_rev = sanitize_for_filesystem(rev)
        return cache_dir / f"{repo_name}-{safe_rev}"
    else:
        # No specific revision: determine the latest version from git
        latest_tag = get_latest_git_tag(url)
        if latest_tag:
            safe_tag = sanitize_for_filesystem(latest_tag)
            return cache_dir / f"{repo_name}-{safe_tag}"
        else:
            # Fallback if can't determine latest version
            return cache_dir / f"{repo_name}-main"


def cache_info():
    """Show information about the doracxx cache"""
    cache_dir = get_doracxx_cache_dir()
    print(f"doracxx cache directory: {cache_dir}")
    
    # Check cache contents
    if cache_dir.exists():
        print("\nCache contents:")
        for item in cache_dir.iterdir():
            if item.is_dir():
                try:
                    size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    size_mb = size / (1024 * 1024)
                    print(f"  {item.name}/  ({size_mb:.1f} MB)")
                except Exception:
                    print(f"  {item.name}/  (size unknown)")
            else:
                try:
                    size_mb = item.stat().st_size / (1024 * 1024)
                    print(f"  {item.name}  ({size_mb:.1f} MB)")
                except Exception:
                    print(f"  {item.name}  (size unknown)")
    else:
        print("Cache directory does not exist yet.")


def cache_clean():
    """Clean the doracxx cache"""
    cache_dir = get_doracxx_cache_dir()
    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir)
            print(f"Cache cleared: {cache_dir}")
        except Exception as e:
            print(f"Error clearing cache: {e}")
    else:
        print("Cache directory does not exist.")


def get_arrow_cache_path(url: str | None = None, rev: str | None = None):
    """Get the path for cached Arrow installation, versioned by URL and revision.
    
    Creates a versioned cache directory:
    - If rev is specified: arrow-{rev} 
    - If no rev specified: determines the latest version from git and uses arrow-{latest_version}
    """
    cache_dir = get_doracxx_cache_dir()
    
    # Create a unique directory name based on URL and revision
    # Use the repo name from URL (e.g., "arrow" from "https://github.com/apache/arrow")
    if url:
        repo_name = url.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
    else:
        repo_name = "arrow"
        url = "https://github.com/apache/arrow.git"  # Default URL for tag lookup
    
    if rev:
        # Include revision in the path for version-specific caching
        # Sanitize revision name for filesystem compatibility
        safe_rev = sanitize_for_filesystem(rev)
        return cache_dir / f"{repo_name}-{safe_rev}"
    else:
        # No specific revision: determine the latest version from git
        latest_tag = get_latest_git_tag(url)
        if latest_tag:
            safe_tag = sanitize_for_filesystem(latest_tag)
            return cache_dir / f"{repo_name}-{safe_tag}"
        else:
            # Fallback if can't determine latest version
            return cache_dir / f"{repo_name}-main"


def sanitize_for_filesystem(name: str) -> str:
    """Sanitize a string to be safe for use as a filesystem path component."""
    import re
    # Replace problematic characters with underscores
    # This includes: / \ : * ? " < > | ^ { } and other special characters
    safe_name = re.sub(r'[/\\:*?"<>|^{}]', '_', name)
    # Remove any leading/trailing dots or spaces
    safe_name = safe_name.strip('. ')
    # Ensure it's not empty
    if not safe_name:
        safe_name = "default"
    return safe_name


def cache_clean_dora():
    """Clean only Dora from the cache"""
    cache_dir = get_doracxx_cache_dir()
    if cache_dir.exists():
        print("Cleaning Dora cache directories...")
        removed_count = 0
        for item in cache_dir.iterdir():
            if item.is_dir() and item.name.startswith('dora'):
                try:
                    # On Windows, git files might be read-only, so we need to handle permissions
                    if hasattr(shutil, 'rmtree'):
                        def handle_remove_readonly(func, path, exc):
                            import stat
                            import os
                            if exc[1].errno == 13:  # Permission denied
                                os.chmod(path, stat.S_IWRITE)
                                func(path)
                            else:
                                raise exc[1]
                        
                        shutil.rmtree(item, onerror=handle_remove_readonly)
                    else:
                        shutil.rmtree(item)
                    print(f"  Removed: {item.name}")
                    removed_count += 1
                except Exception as e:
                    print(f"  Error removing {item.name}: {e}")
        
        if removed_count > 0:
            print(f"Cleaned {removed_count} Dora cache director{'ies' if removed_count > 1 else 'y'}")
        else:
            print("No Dora cache directories found.")
    else:
        print("Cache directory does not exist.")


def cache_clean_arrow():
    """Clean only Arrow from the cache"""
    cache_dir = get_doracxx_cache_dir()
    if cache_dir.exists():
        print("Cleaning Arrow cache directories...")
        removed_count = 0
        for item in cache_dir.iterdir():
            if item.is_dir() and item.name.startswith('arrow'):
                try:
                    # On Windows, git files might be read-only, so we need to handle permissions
                    if hasattr(shutil, 'rmtree'):
                        def handle_remove_readonly(func, path, exc):
                            import stat
                            import os
                            if exc[1].errno == 13:  # Permission denied
                                os.chmod(path, stat.S_IWRITE)
                                func(path)
                            else:
                                raise exc[1]
                        
                        shutil.rmtree(item, onerror=handle_remove_readonly)
                    else:
                        shutil.rmtree(item)
                    print(f"  Removed: {item.name}")
                    removed_count += 1
                except Exception as e:
                    print(f"  Error removing {item.name}: {e}")
        
        if removed_count > 0:
            print(f"Cleaned {removed_count} Arrow cache director{'ies' if removed_count > 1 else 'y'}")
        else:
            print("No Arrow cache directories found.")
    else:
        print("Cache directory does not exist.")
