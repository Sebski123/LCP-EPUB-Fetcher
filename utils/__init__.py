import os
import shutil
import sys


def find_thorium_path():
    """
    Attempts to find the path to the Thorium Reader executable.
    Works on Windows and Linux. If not found, asks the user to provide it.

    Returns:
        str: Path to the Thorium Reader executable.
    """
    possible_names = ["thorium.exe", "thorium"]
    possible_paths: list[str] = []

    if sys.platform.startswith("win"):
        # Common install locations on Windows
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        possible_paths += [
            os.path.join(program_files, "Thorium Reader", "thorium.exe"),
            os.path.join(program_files_x86, "Thorium Reader", "thorium.exe"),
            os.path.join(local_appdata, "Programs", "Thorium", "thorium.exe"),
        ]
    else:
        # Common install locations on Linux
        possible_paths += [
            "/usr/bin/thorium",
            "/usr/local/bin/thorium",
            os.path.expanduser("~/.local/bin/thorium"),
        ]

    # Check if any of the possible paths exist
    for path in possible_paths:
        if os.path.isfile(path):
            print(f"Found Thorium Reader at: {path}")
            return path

    # Try to find in PATH
    for name in possible_names:
        thorium_path = shutil.which(name)
        if thorium_path:
            return thorium_path

    # Not found, ask user
    user_path = input("Thorium Reader executable not found. Please enter the full path: ").strip()
    if os.path.isfile(user_path):
        return user_path
    raise FileNotFoundError("Thorium Reader executable not found.")
