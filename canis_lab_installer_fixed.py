import os
import sys
import subprocess
import platform
import urllib.request
import zipfile
import tempfile
import shutil
from pathlib import Path

# --- Configuration ---
APP_NAME = "Canis.lab"
REPO_URL = "https://github.com/crasyK/Canis.lab"
ICON_URL_PNG = f"{REPO_URL}/raw/main/icon.png"
ICON_URL_ICO = f"{REPO_URL}/raw/main/icon.ico"

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
    """Downloads a file from a URL to a destination."""
    print(f"⬇️  Downloading {description} from {url}...")
    try:
        urllib.request.urlretrieve(url, dest)
        print_success(f"{description} downloaded successfully.")
    except Exception as e:
        print_error(f"Failed to download {description}: {e}")

def check_venv_support():
    """Check if venv module is available."""
    try:
        subprocess.run([sys.executable, "-m", "venv", "--help"], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def create_virtual_environment(install_path):
    """Creates a Python virtual environment with fallback options."""
    venv_path = install_path / ".venv"
    print(f"🐍 Setting up Python environment in '{venv_path}'...")
    
    # Remove existing venv if it exists
    if venv_path.exists():
        print("   Removing existing virtual environment...")
        shutil.rmtree(venv_path)
    
    # Check if venv module is available
    if not check_venv_support():
        print_warning("Python venv module not available. Installing dependencies globally.")
        return None
    
    # Try multiple approaches to create virtual environment
    success = False
    
    # Method 1: Standard venv
    try:
        print("   Attempting to create virtual environment...")
        result = subprocess.run([sys.executable, "-m", "venv", str(venv_path)], 
                              check=True, capture_output=True, text=True, 
                              cwd=install_path)
        
        # Verify the directory was actually created
        if venv_path.exists():
            print_success("Virtual environment created successfully.")
            success = True
        else:
            print_warning("venv command succeeded but directory was not created.")
            
    except subprocess.CalledProcessError as e:
        print_warning(f"Standard venv failed: {e.stderr}")
    
    # Method 2: Try with --system-site-packages if method 1 failed
    if not success:
        try:
            print("   Trying with --system-site-packages...")
            result = subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv_path)], 
                                  check=True, capture_output=True, text=True,
                                  cwd=install_path)
            
            if venv_path.exists():
                print_success("Virtual environment created with system site packages.")
                success = True
            else:
                print_warning("venv with --system-site-packages succeeded but directory was not created.")
                
        except subprocess.CalledProcessError as e:
            print_warning(f"venv with --system-site-packages failed: {e.stderr}")
    
    # Method 3: Try virtualenv as fallback
    if not success:
        try:
            print("   Trying virtualenv as fallback...")
            # First try to install virtualenv
            subprocess.run([sys.executable, "-m", "pip", "install", "virtualenv"], 
                          check=True, capture_output=True)
            
            # Then create the environment
            result = subprocess.run([sys.executable, "-m", "virtualenv", str(venv_path)], 
                                  check=True, capture_output=True, text=True,
                                  cwd=install_path)
            
            if venv_path.exists():
                print_success("Virtual environment created using virtualenv.")
                success = True
            else:
                print_warning("virtualenv succeeded but directory was not created.")
                
        except subprocess.CalledProcessError as e:
            print_warning(f"virtualenv fallback failed: {e.stderr}")
    
    if success and venv_path.exists():
        # Verify we can find a Python executable
        python_exe = find_venv_python(venv_path)
        if python_exe:
            return venv_path
        else:
            print_warning("Virtual environment created but Python executable not accessible.")
    
    # If all methods failed, fall back to global installation
    print_warning("Could not create virtual environment. Will install dependencies globally.")
    print_warning("This may cause conflicts with other Python projects.")
    return None

def find_venv_python(venv_path):
    """Finds the Python executable in the virtual environment."""
    if not venv_path or not venv_path.exists():
        return None
        
    if platform.system() == "Windows":
        possible_paths = [
            venv_path / "Scripts" / "python.exe",
            venv_path / "Scripts" / "python3.exe"
        ]
    else:
        possible_paths = [
            venv_path / "bin" / "python",
            venv_path / "bin" / "python3",
            venv_path / "bin" / f"python{sys.version_info.major}.{sys.version_info.minor}"
        ]
    
    for python_exe in possible_paths:
        if python_exe.exists():
            # Test if it works
            try:
                subprocess.run([str(python_exe), "--version"], 
                             capture_output=True, text=True, check=True)
                return python_exe
            except subprocess.CalledProcessError:
                continue
    
    return None

def install_dependencies_with_progress(venv_path, requirements_file):
    """Installs dependencies, with or without virtual environment."""
    print("This may take a few minutes...")
    
    if venv_path and venv_path.exists():
        # Try to install in virtual environment
        python_exe = find_venv_python(venv_path)
        if python_exe:
            print("   Installing into virtual environment...")
            command = [str(python_exe), "-m", "pip", "install", "-r", str(requirements_file)]
        else:
            # Fallback to activation script method
            print("   Using virtual environment activation script...")
            return install_with_activation_script(venv_path, requirements_file)
    else:
        # Global installation
        print("   Installing globally (no virtual environment)...")
        command = [sys.executable, "-m", "pip", "install", "--user", "-r", str(requirements_file)]
    
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"   {output.strip()}")
        
        if process.poll() == 0:
            print_success("Dependencies installed successfully!")
        else:
            print_error("Failed to install dependencies. Please check the output above.", exit_code=None)
    
    except Exception as e:
        print_error(f"Failed to install dependencies: {e}", exit_code=None)

def install_with_activation_script(venv_path, requirements_file):
    """Install using activation script as fallback."""
    if platform.system() == "Windows":
        activate_script = venv_path / "Scripts" / "activate.bat"
        command = f'call "{activate_script}" && pip install -r "{requirements_file}"'
        shell_args = {"shell": True}
        cmd = command
    else:
        activate_script = venv_path / "bin" / "activate"
        command = f'. "{activate_script}" && pip install -r "{requirements_file}"'
        shell_args = {}
        cmd = ['bash', '-c', command]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            **shell_args
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"   {output.strip()}")
        
        if process.poll() == 0:
            print_success("Dependencies installed successfully using activation script!")
        else:
            print_error("Failed to install dependencies with activation script.", exit_code=None)
    
    except Exception as e:
        print_error(f"Failed to install with activation script: {e}", exit_code=None)

def prompt_for_api_key(install_path):
    """Asks the user for their OpenAI API key and saves it to the .env file."""
    print_header("Step 6: Set OpenAI API Key")
    print("Canis.lab requires an OpenAI API key to function.")
    api_key = input("Enter your OpenAI API key (or press Enter to skip): ").strip()

    if api_key:
        env_path = install_path / ".env"
        try:
            with open(env_path, "w") as f:
                f.write(f"OPENAI_API_KEY={api_key}\n")
            print_success(f"API key saved to '{env_path}'")
        except (IOError, OSError) as e:
            print_error(f"Could not write to .env file: {e}", exit_code=None)
    else:
        print_warning("API key skipped. The application will not work until you add it manually.")
        print_warning(f"To add it later, edit the '.env' file in '{install_path}'.")

def create_run_scripts_and_shortcut(install_path, has_venv):
    """Creates the run scripts and desktop shortcut."""
    print_header("Step 7: Creating Run Scripts and Shortcut")
    system = platform.system()
    
    # --- Create Run Scripts ---
    if system == "Windows":
        script_name = f"run_{APP_NAME.lower().replace('.', '_')}.bat"
        if has_venv:
            script_content = f"""@echo off
echo Activating virtual environment and starting {APP_NAME}...
cd /D "%~dp0"
call .venv\\Scripts\\activate
echo Launching Streamlit...
streamlit run app.py
pause
"""
        else:
            script_content = f"""@echo off
echo Starting {APP_NAME}...
cd /D "%~dp0"
echo Launching Streamlit...
streamlit run app.py
pause
"""
    else:  # Linux & macOS
        script_name = f"run_{APP_NAME.lower().replace('.', '_')}.sh"
        if has_venv:
            # Use POSIX-compliant '.' instead of 'source', and explicitly use bash
            script_content = f"""#!/bin/bash
cd "$(dirname "$0")"
echo "Activating virtual environment and starting {APP_NAME}..."
. .venv/bin/activate
echo "Launching Streamlit..."
streamlit run app.py
"""
        else:
            script_content = f"""#!/bin/bash
cd "$(dirname "$0")"
echo "Starting {APP_NAME}..."
streamlit run app.py
"""
    
    script_path = install_path / script_name
    script_path.write_text(script_content)
    if system != "Windows":
        script_path.chmod(0o755)
    print_success(f"Created run script: '{script_name}'")

    # --- Create Shortcut ---
    print("🔗 Creating desktop shortcut...")
    icon_name = "icon.ico" if system == "Windows" else "icon.png"
    icon_path = install_path / icon_name
    if not icon_path.exists():
        print_warning(f"Icon file '{icon_path}' not found. Shortcut will not have an icon.")

    if system == "Windows":
        try:
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

    elif system == "Linux":
        desktop_file_dir = Path.home() / ".local/share/applications"
        desktop_file_dir.mkdir(parents=True, exist_ok=True)
        desktop_file_path = desktop_file_dir / f"{APP_NAME.lower().replace('.', '_')}.desktop"
        desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={APP_NAME}
Comment=Synthetic Dataset Generation Platform
Exec=bash "{script_path}"
Icon={icon_path}
Terminal=true
Categories=Development;
"""
        try:
            desktop_file_path.write_text(desktop_content)
            desktop_file_path.chmod(0o755)
            print_success("Linux desktop entry created in your application menu.")
        except (IOError, OSError) as e:
            print_warning(f"Could not create Linux .desktop file: {e}")
    else:
        print_warning("Shortcut creation on macOS is not automated.")

def main():
    """Main installation process."""
    print_header(f"Welcome to the {APP_NAME} Installer")
    
    # Steps 1-4: Path, Download, Extract, Copy
    install_path = get_install_path()
    print_success(f"Installing {APP_NAME} to: {install_path}")
    
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        zip_url = f"{REPO_URL}/archive/refs/heads/main.zip"
        zip_path = temp_dir / "app.zip"
        download_file(zip_url, zip_path, f"{APP_NAME} source code")
        
        print("\n🌀 Extracting files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        print_success("Files extracted.")
        
        extracted_folder = next(temp_dir.glob('*-main'), None)
        if not extracted_folder:
            print_error("Could not find app folder in downloaded archive.")
        
        print(f"📂 Copying application files...")
        for item in extracted_folder.iterdir():
            dest_item = install_path / item.name
            if item.is_dir():
                if dest_item.exists():
                    shutil.rmtree(dest_item)
                shutil.copytree(item, dest_item)
            else:
                shutil.copy2(item, dest_item)
        print_success("Application files copied.")
        
        print("\n🎨 Downloading icons...")
        download_file(ICON_URL_PNG, install_path / "icon.png", "PNG Icon")
        if platform.system() == "Windows":
            download_file(ICON_URL_ICO, install_path / "icon.ico", "ICO Icon")

    # Step 5: Create Virtual Environment
    print_header("Step 5: Setting Up Python Environment")
    venv_path = create_virtual_environment(install_path)
    has_venv = venv_path is not None and venv_path.exists()
    
    # Install dependencies
    requirements_file = install_path / "requirements.txt"
    if requirements_file.exists():
        install_dependencies_with_progress(venv_path, requirements_file)
    else:
        print_warning("'requirements.txt' not found, skipping dependency installation.")

    # Step 6: API Key
    prompt_for_api_key(install_path)

    # Step 7: Run Scripts and Shortcut
    create_run_scripts_and_shortcut(install_path, has_venv)

    # Final Message
    print_header("🎉 Installation Complete! 🎉")
    print(f"You can now start {APP_NAME} using the desktop shortcut.")
    if not has_venv:
        print_warning("Note: Dependencies were installed globally due to virtual environment issues.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")
