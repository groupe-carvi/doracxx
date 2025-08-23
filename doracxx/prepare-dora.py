#!/usr/bin/env python3
"""Prepare Dora checkout and attempt to build APIs needed by C++ nodes.

This script will:
- clone or update Dora into third_party/dora
- try `cargo build --workspace` (best-effort)
- if workspace build fails, attempt to build only the C/C++ API manifests

The goal is to resolve Dora (sources + cxxbridge artifacts) before node builds.
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
    cmd = [os.environ.get("CARGO", "cargo"), "build", "--workspace"]
    if profile == "release":
        cmd.append("--release")
    try:
        run(cmd, cwd=repo)
        return True
    except subprocess.CalledProcessError:
        print("warning: workspace build failed (some system deps may be missing)")
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
    args = p.parse_args()

    vendor = Path("third_party") / "dora"
    print("Prepare Dora in:", vendor)
    repo = git_clone_or_update(args.dora_git, vendor, args.dora_rev)

    # Try workspace build first; many targets will succeed, but some platform deps may fail.
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
