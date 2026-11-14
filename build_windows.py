#!/usr/bin/env python3
"""
Build Windows executable for OrbitCode using PyInstaller.
Run this on Windows or in a Windows CI environment.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path


def build_windows_exe():
    """Build Windows executable with PyInstaller."""
    # Ensure we're in the project root
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # Install PyInstaller if not present
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=orbitcode",
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        # Include data files
        "--add-data=orbitcode/config:orbitcode/config",
        "--add-data=orbitcode/plugins:orbitcode/plugins",
        "--add-data=orbitcode/themes:orbitcode/themes",
        # Hidden imports
        "--hidden-import=orbitcode.config",
        "--hidden-import=orbitcode.config.settings",
        "--hidden-import=orbitcode.config.customise",
        "--hidden-import=orbitcode.core.agent",
        "--hidden-import=orbitcode.core.model_router",
        "--hidden-import=orbitcode.core.session",
        "--hidden-import=orbitcode.core.tui",
        "--hidden-import=orbitcode.core.learning",
        "--hidden-import=orbitcode.core.planner",
        "--hidden-import=orbitcode.core.indexer",
        "--hidden-import=orbitcode.core.git",
        "--hidden-import=orbitcode.core.mascot.mascot",
        "--hidden-import=orbitcode.tools.registry",
        "--hidden-import=orbitcode.tools.base",
        "--hidden-import=orbitcode.tools.bash",
        "--hidden-import=orbitcode.tools.read",
        "--hidden-import=orbitcode.tools.write",
        "--hidden-import=orbitcode.tools.edit",
        "--hidden-import=orbitcode.tools.glob",
        "--hidden-import=orbitcode.tools.grep",
        "--hidden-import=orbitcode.tools.web_search",
        "--hidden-import=orbitcode.tools.browser",
        "--hidden-import=orbitcode.plugins",
        "--hidden-import=orbitcode.mcp.server",
        "--hidden-import=typer",
        "--hidden-import=rich",
        "--hidden-import=pydantic",
        "--hidden-import=pydantic_settings",
        "--hidden-import=httpx",
        "--hidden-import=sqlalchemy",
        "--hidden-import=aiofiles",
        "--hidden-import=mcp",
        "--hidden-import=anyio",
        "--hidden-import=yaml",
        "--hidden-import=watchdog",
        "--hidden-import=git",
        "--hidden-import=playwright",
        "--hidden-import=tomli",
        "--hidden-import=tomli_w",
        # Entry point
        "orbitcode/cli.py"
    ]

    print("Building Windows executable...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Build failed: {result.stderr}")
        return False

    print("Build successful!")
    exe_path = project_root / "dist" / "orbitcode.exe"
    if exe_path.exists():
        print(f"Executable created at: {exe_path}")
        print(f"Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")

        # Create release zip
        release_dir = project_root / "release"
        release_dir.mkdir(exist_ok=True)
        zip_path = release_dir / "orbitcode-windows-x64.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), 'zip', project_root / "dist")
        print(f"Release zip created at: {zip_path}")
    else:
        print("Warning: Executable not found at expected location")

    return True


if __name__ == "__main__":
    build_windows_exe()