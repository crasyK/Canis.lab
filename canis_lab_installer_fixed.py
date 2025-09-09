import os
import sys
import subprocess
import platform
import urllib.request
import zipfile
import tempfile
import shutil
import webbrowser
from pathlib import Path

# --- Configuration ---
APP_NAME = "Canis.lab"
REPO_URL = "https://github.com/crasyK/Canis.lab"
# Assuming the icon is in the root of the repo
ICON_URL_PNG = f"{REPO_URL}/raw/main/icon.png"
ICON_URL_ICO = f"{REPO_URL}/raw/main/icon.ico" # You should add this to your repo

# --- Helper Functions ---

def print_header(text):
    """Prints a formatted header."""
    print(f"\n{'='*60}\n {text}\n{'='*60}")

def print_success(text):
    print(f"✅ {text}")

def print_warning(text):
    print(f"⚠️  {text}")

def print_error(text, exit_code=1):
    print(f"❌ ERROR: {text}")
    if exit_code is not None:
        sys.exit(exit_code)

def get_install_path():
    """Prompts the user for an installation path."""
    default_path = Path.home() / "CanisLab"
    prompt = f"Enter install path or press Enter for default [{default_path}]: "
    user_input = input(prompt).strip()

    install_path = Path(user_input).expanduser() if user_input else default_path

    try:
        if install_path.exists() and any(install_path.iterdir()):
            print_warning(f"Directory '{install_path}' is not empty.")
            if input("   Continue and overwrite existing files? (y/N): ").lower() != 'y':
                print("Installation cancelled by user.")
                sys.exit(0)
        install_path.mkdir(parents=True, exist_ok=True)
    except (IOError, OSError) as e:
        print_error(f"Could not create or write to directory: {e}")

    return install_path

def download_file(url, dest, description):
    """Downloads a file from a URL to a destination with progress."""
    print(f"⬇️  Downloading {description} from {url}...")
    try:
        urllib.request.urlretrieve(url, dest)
        print_success(f"{description} downloaded successfully.")
    except Exception as e:
        print_error(f"Failed to download {description}: {e}")

def create_shortcut(install_path):
    """Creates a desktop shortcut for the appropriate OS."""
    print("\n🔗 Creating desktop shortcut...")
    system = platform.system()
    # Use a more robust run script name
    script_name = f"run_{APP_NAME.lower()}"
    script_path = install_path / (f"{script_name}.bat" if system == "Windows" else f"{script_name}.sh")
    icon_name = "icon.ico" if system == "Windows" else "icon.png"
    icon_path = install_path / icon_name

    if not icon_path.exists():
        print_warning(f"Icon file '{icon_path}' not found. Shortcut will not have an icon.")

    if system == "Windows":
        try:
            # Using a more modern approach with winshell
            import winshell
            desktop = winshell.desktop()
            link_filepath = os.path.join(desktop, f"{APP_NAME}.lnk")

            with winshell.shortcut(link_filepath) as shortcut:
                shortcut.path = str(script_path)
                shortcut.working_directory = str(install_path)
                if icon_path.exists():
                    shortcut.icon_location = (str(icon_path), 0)
                shortcut.description = f"Launch {APP_NAME}"

            print_success("Windows desktop shortcut created.")
        except (ImportError, Exception) as e:
            print_warning(f"Could not create Windows shortcut: {e}")
            print_warning("You can run the application manually using the .bat script in the installation folder.")

    elif system == "Linux":
        desktop_file_dir = Path.home() / ".local/share/applications"
        desktop_file_dir.mkdir(parents=True, exist_ok=True)
        desktop_file_path = desktop_file_dir / f"{APP_NAME.lower()}.desktop"

        desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={APP_NAME}
Comment=Synthetic Dataset Generation Platform
Exec=sh "{script_path}"
Icon={icon_path}
Terminal=true
Categories=Development;
"""
        try:
            desktop_file_path.write_text(desktop_content)
            desktop_file_path.chmod(0o755) # Make it executable
            print_success("Linux desktop entry created.")
            print("   You should find it in your application menu.")
        except (IOError, OSError) as e:
            print_warning(f"Could not create Linux .desktop file: {e}")
            print_warning("You can run the application manually using the .sh script in the installation folder.")

    else: # macOS
        print_warning("Shortcut creation on macOS is not automated. You can create an Alias manually.")

def main():
    """Main installation process."""
    print_header(f"Welcome to the {APP_NAME} Installer")

    # 1. Get installation location
    install_path = get_install_path()
    print_success(f"Installing {APP_NAME} to: {install_path}")

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        # 2. Download and extract the application repository
        zip_url = f"{REPO_URL}/archive/refs/heads/main.zip"
        zip_path = temp_dir / "app.zip"
        download_file(zip_url, zip_path, f"{APP_NAME} source code")

        print("\n🌀 Extracting files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        print_success("Files extracted.")

        # The extracted folder is usually named 'RepoName-main'
        extracted_folder = next(temp_dir.glob('*-main'), None)
        if not extracted_folder:
            print_error("Could not find the main application folder in the downloaded archive.")

        # 3. Copy files to the installation directory
        print(f"📂 Copying application files to '{install_path}'...")
        for item in extracted_folder.iterdir():
            dest_item = install_path / item.name
            if item.is_dir():
                if dest_item.exists():
                    shutil.rmtree(dest_item)
                shutil.copytree(item, dest_item)
            else:
                shutil.copy2(item, dest_item)
        print_success("Application files copied.")

        # 4. Download icons
        print("\n🎨 Downloading icons...")
        download_file(ICON_URL_PNG, install_path / "icon.png", "PNG Icon")
        if platform.system() == "Windows":
             # Also get the .ico for Windows shortcuts
            download_file(ICON_URL_ICO, install_path / "icon.ico", "ICO Icon")

        # 5. Install dependencies
        print("\n🐍 Installing Python dependencies...")
        requirements_file = install_path / "requirements.txt"
        if requirements_file.exists():
            try:
                # Use sys.executable to ensure we use the python that's running the script
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)], check=True, capture_output=True)
                print_success("Dependencies installed successfully.")
            except subprocess.CalledProcessError as e:
                print_error(f"Failed to install dependencies:\n{e.stderr.decode()}", exit_code=None)
                print_warning("Please try running 'pip install -r requirements.txt' manually in the installation directory.")
        else:
            print_warning("'requirements.txt' not found, skipping dependency installation.")

    # 6. Create run scripts
    print("\n⚙️ Creating run scripts...")
    system = platform.system()
    if system == "Windows":
        script_name = f"run_{APP_NAME.lower()}.bat"
        script_content = f"""@echo off
echo Starting {APP_NAME}...
cd /D "{install_path}"
python app.py
pause
"""
    else: # Linux & macOS
        script_name = f"run_{APP_NAME.lower()}.sh"
        script_content = f"""#!/bin/sh
cd "{install_path}"
python3 app.py
"""
    script_path = install_path / script_name
    script_path.write_text(script_content)
    if system != "Windows":
        script_path.chmod(0o755)
    print_success(f"Created '{script_name}'.")

    # 7. Create shortcuts
    create_shortcut(install_path)

    # 8. Final message
    print_header("🎉 Installation Complete! 🎉")
    print(f"You can now start {APP_NAME} by using the desktop shortcut")
    print(f"or by running '{script_name}' in '{install_path}'.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")
