import subprocess
import sys
import platform
import shutil
import urllib.request
from pathlib import Path
import os
import zipfile

# --- Configuration ---
INSTALLER_SCRIPT = "canis_lab_installer_fixed.py"
ICON_PNG = "icon.png"
ICON_ICO = "icon.ico"
APP_NAME = "CanisLab_Installer"
RELEASE_DIR = Path("release")

# --- Helper Functions ---

def print_header(text):
    print(f"\n{'='*60}\n {text}\n{'='*60}")

def run_command(command, error_message):
    """Runs a command and exits on failure."""
    try:
        # Use capture_output=True to hide the command's output unless there's an error
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout) # Print stdout on success
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERROR: {error_message}")
        print(f"   COMMAND: {' '.join(command)}")
        print(f"   STDOUT: {e.stdout}")
        print(f"   STDERR: {e.stderr}")
        sys.exit(1)

def check_and_install_deps():
    """Checks for and helps install PyInstaller and Pillow."""
    print_header("Step 1: Checking Build Dependencies")
    try:
        import PyInstaller
        print("✅ PyInstaller is installed.")
    except ImportError:
        if input("⚠️ PyInstaller not found. Install it now? (y/N): ").lower() == 'y':
            run_command([sys.executable, "-m", "pip", "install", "pyinstaller"], "Failed to install PyInstaller.")
        else:
            sys.exit("PyInstaller is required to continue.")

    if platform.system() == "Windows":
        try:
            from PIL import Image
            print("✅ Pillow is installed.")
        except ImportError:
            if input("⚠️ Pillow (for icon conversion) not found. Install it now? (y/N): ").lower() == 'y':
                run_command([sys.executable, "-m", "pip", "install", "Pillow"], "Failed to install Pillow.")
            else:
                sys.exit("Pillow is required for icon conversion on Windows.")

def prepare_assets():
    """Prepares assets like icons for the build."""
    print_header("Step 2: Preparing Assets")
    if not Path(ICON_PNG).exists():
        sys.exit(f"❌ ERROR: '{ICON_PNG}' not found. It is required for the installer icon.")
    print(f"✅ Found '{ICON_PNG}'.")

    if platform.system() == "Windows":
        print(f"   Converting '{ICON_PNG}' to '{ICON_ICO}' for Windows executable...")
        try:
            from PIL import Image
            img = Image.open(ICON_PNG)
            # Ensure the ICO contains multiple sizes for better compatibility
            img.save(ICON_ICO, format='ICO', sizes=[(16,16), (32, 32), (48, 48), (64,64), (128, 128), (256, 256)])
            print(f"✅ Successfully created '{ICON_ICO}'.")
        except Exception as e:
            sys.exit(f"❌ Failed to convert icon: {e}")

def build_executable():
    """Builds the core executable using PyInstaller."""
    system = platform.system()
    print_header(f"Step 3: Building Executable for {system}")
    if not Path(INSTALLER_SCRIPT).exists():
        sys.exit(f"❌ ERROR: Main installer script '{INSTALLER_SCRIPT}' not found.")

    # Clean up previous builds
    shutil.rmtree("build", ignore_errors=True)
    shutil.rmtree(RELEASE_DIR, ignore_errors=True)
    RELEASE_DIR.mkdir(exist_ok=True)

    pyinstaller_cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--onefile",
        "--console",
        f"--workpath=./build/pyinstaller_build",
        f"--distpath=./{RELEASE_DIR}",
    ]

    if system == "Windows" and Path(ICON_ICO).exists():
        pyinstaller_cmd.extend(["--icon", ICON_ICO])
    
    pyinstaller_cmd.append(INSTALLER_SCRIPT)

    print("   Running PyInstaller...")
    run_command(pyinstaller_cmd, "PyInstaller build failed.")

    exe_name = f"{APP_NAME}.exe" if system == "Windows" else APP_NAME
    exe_path = RELEASE_DIR / exe_name
    if exe_path.exists():
        print(f"✅ PyInstaller build successful! Executable created at '{exe_path}'")
    else:
        sys.exit("❌ PyInstaller finished, but the executable was not found.")


def download_appimagetool():
    """Downloads the AppImage tool if not present."""
    tool_path = Path("/home/mak-ko/Projects/LLM-Synth/LLM-Synth/appimagetool-x86_64.AppImage")
    if not tool_path.exists():
        print("   AppImageTool not found. Downloading...")
        url = "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
        try:
            with urllib.request.urlopen(url) as response, open(tool_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            tool_path.chmod(0o755)
            print("✅ AppImageTool downloaded successfully.")
        except Exception as e:
            sys.exit(f"❌ Failed to download AppImageTool: {e}")
    return tool_path

def build_appimage():
    """Creates a Linux AppImage."""
    if platform.system() != "Linux":
        print("\nℹ️ AppImage build is only supported on Linux. Skipping.")
        return

    print_header("Step 4: Building Linux AppImage")

    appdir = Path(f"{APP_NAME}.AppDir")
    if appdir.exists():
        shutil.rmtree(appdir)
    appdir.mkdir()

    # Define icon name and desktop file name
    icon_name = APP_NAME.lower()
    desktop_filename = f"{icon_name}.desktop"

    # 1. Create AppRun script
    apprun_content = f"""#!/bin/sh
HERE=$(dirname $(readlink -f "$0"))
$HERE/usr/bin/{APP_NAME} "$@"
"""
    (appdir / "AppRun").write_text(apprun_content)
    (appdir / "AppRun").chmod(0o755)

    # 2. Create .desktop file
    desktop_content = f"""[Desktop Entry]
Name={APP_NAME}
Exec={APP_NAME}
Icon={icon_name}
Type=Application
Categories=Utility;
"""
    (appdir / desktop_filename).write_text(desktop_content)

    # 3. Copy the main executable
    bin_dir = appdir / "usr" / "bin"
    bin_dir.mkdir(parents=True)
    shutil.copy(RELEASE_DIR / APP_NAME, bin_dir / APP_NAME)

    # 4. Copy the icon to the standard path AND the root path
    # The .desktop file's 'Icon' entry will use this one
    icon_dir_standard = appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icon_dir_standard.mkdir(parents=True)
    shutil.copy(ICON_PNG, icon_dir_standard / f"{icon_name}.png")

    # This is a best-practice fallback for appimagetool and desktop environments
    shutil.copy(ICON_PNG, appdir / f"{icon_name}.png")

    # 5. Download AppImageTool and build the AppImage
    appimagetool = download_appimagetool()
    final_appimage_name = f"{APP_NAME}-x86_64.AppImage"
    
    # Set ARCH and run the tool
    env = os.environ.copy()
    env["ARCH"] = "x86_64"
    command = [str(appimagetool), str(appdir), str(RELEASE_DIR / final_appimage_name)]
    
    print("   Running appimagetool...")
    try:
        # We run this command directly instead of using the helper to pass the 'env'
        subprocess.run(command, check=True, capture_output=True, text=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERROR: AppImage creation failed.")
        print(f"   COMMAND: {' '.join(command)}")
        print(f"   STDERR: {e.stderr}")
        sys.exit(1)

    print(f"✅ AppImage created successfully at '{RELEASE_DIR / final_appimage_name}'")


def main():
    """Main build process."""
    print_header("Canis.lab Installer Builder")

    if not Path(INSTALLER_SCRIPT).exists():
        sys.exit(f"❌ ERROR: The source for the new installer '{INSTALLER_SCRIPT}' was not found.")
    
    check_and_install_deps()
    prepare_assets()
    build_executable()
    build_appimage()

    print("\n🎉 SUCCESS! 🎉")
    print(f"Installer artifacts are ready in the '{RELEASE_DIR}' directory.")

if __name__ == "__main__":
    main()
