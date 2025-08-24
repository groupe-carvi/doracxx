#!/usr/bin/env python3
"""Prepare Dora checkout and build only the C++ APIs needed by C++ nodes.

This script will:
- clone or update Dora into third_party/dora
- by default: build only the essential C++ API packages (optimized, faster)
- if --full-workspace: build the entire workspace (slower but complete)
- if package builds fail, attempt to build only the C/C++ API manifests

The goal is to resolve Dora (sources + cxxbridge artifacts) before node builds
while minimizing compilation time by only building what's needed for C++ nodes.
"""

import argparse
import subprocess
from pathlib import Path
import os


def git_clone_or_update(url: str, dest: Path, rev: str | None):
    dest = dest.resolve()
    if dest.exists():
        print(f"Dora already present at {dest}, fetching updates")
        try:
            subprocess.check_call(["git", "-C", str(dest), "fetch", "--all"], stdout=subprocess.DEVNULL)
            if rev:
                subprocess.check_call(["git", "-C", str(dest), "checkout", rev])
            else:
                subprocess.check_call(["git", "-C", str(dest), "checkout", "main"]) 
        except subprocess.CalledProcessError:
            print("warning: git update failed, continuing with existing checkout")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", url, str(dest)]
    if rev:
        cmd += ["--branch", rev]
    subprocess.check_call(cmd)
    return dest


def run(cmd, cwd=None, env=None, check=True):
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, env=env, check=check)


def build_workspace(repo: Path, profile: str):
    """Build only the C++ APIs needed for nodes instead of the full workspace."""
    # Only build the specific C++ API packages we need
    essential_packages = [
        "dora-node-api-cxx", 
        "dora-operator-api-cxx",
        "dora-node-api-c",
        "dora-operator-api-c"
    ]
    
    print("Building only essential C++ API packages instead of full workspace...")
    success_count = 0
    
    for package in essential_packages:
        cmd = [os.environ.get("CARGO", "cargo"), "build", "--package", package]
        if profile == "release":
            cmd.append("--release")
        try:
            run(cmd, cwd=repo)
            print(f"✓ Successfully built package: {package}")
            success_count += 1
        except subprocess.CalledProcessError:
            print(f"⚠ Warning: failed to build package {package} (continuing...)")
    
    if success_count > 0:
        print(f"Successfully built {success_count}/{len(essential_packages)} essential packages")
        return True
    else:
        print("All essential package builds failed, falling back to manifest-based build")
        return False


def build_manifests(repo: Path, profile: str):
    manifests = [
        repo / "apis" / "c++" / "node" / "Cargo.toml",
        repo / "apis" / "c++" / "operator" / "Cargo.toml",
        repo / "apis" / "c" / "node" / "Cargo.toml",
        repo / "apis" / "c" / "operator" / "Cargo.toml",
    ]
    for m in manifests:
        if m.exists():
            cmd = [os.environ.get("CARGO", "cargo"), "build", "--manifest-path", str(m)]
            if profile == "release":
                cmd.append("--release")
            try:
                run(cmd, cwd=repo)
            except subprocess.CalledProcessError:
                print(f"warning: build failed for {m} (ignored)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dora-git", default="https://github.com/dora-rs/dora")
    p.add_argument("--dora-rev", default=None)
    p.add_argument("--profile", choices=("debug", "release"), default="debug")
    p.add_argument("--full-workspace", action="store_true", 
                   help="Build the entire dora workspace instead of only C++ APIs (slower but more complete)")
    args = p.parse_args()

    vendor = Path("third_party") / "dora"
    print("Prepare Dora in:", vendor)
    repo = git_clone_or_update(args.dora_git, vendor, args.dora_rev)

    if args.full_workspace:
        print("Building full workspace as requested...")
        # Original workspace build
        cmd = [os.environ.get("CARGO", "cargo"), "build", "--workspace"]
        if args.profile == "release":
            cmd.append("--release")
        try:
            run(cmd, cwd=repo)
            ok = True
        except subprocess.CalledProcessError:
            print("warning: workspace build failed (some system deps may be missing)")
            ok = False
    else:
        # Optimized build - only essential C++ APIs
        ok = build_workspace(repo, args.profile)
    
    if not ok:
        print("Attempting targeted builds for C/C++ API crates...")
        build_manifests(repo, args.profile)

    target_dir = repo / "target"
    print()
    print("Dora prepared. Target dir:", target_dir)
    print("If build produced cxxbridge artifacts they will be under: <target>/<profile>/cxxbridge")
    print("Set environment variable DORA_TARGET_DIR if you want to read artifacts from a different location.")


if __name__ == '__main__':
    main()
