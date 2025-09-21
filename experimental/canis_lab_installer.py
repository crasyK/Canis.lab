import os
import sys
import subprocess
import platform
import urllib.request
import zipfile
import tempfile
import shutil
from pathlib import Path

import stat

def find_system_python():
    """
    Return (python_cmd_list, python_exe_path) usable to run modules, or (None, None).
    On Windows, tries: py -3, py, python, python3. Else: python3, python.
    """
    candidates = []
    if platform.system() == 'Windows':
        candidates = [
            ['py', '-3'],
            ['py'],
            ['python'],
            ['python3'],
        ]
    else:
        candidates = [
            ['python3'],
            ['python'],
        ]

    for cmd in candidates:
        try:
            ok, out, err = run_with_timeout(cmd + ['-c', 'import sys; print(sys.executable)'], timeout_seconds=10)
            if ok and out.strip():
                return cmd, out.strip()
        except Exception:
            pass
    return None, None


def _remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def safe_rmtree(path: Path):
    if path.exists():
        try:
            shutil.rmtree(path, onerror=_remove_readonly)
        except Exception:
            if platform.system() == 'Windows':
                try:
                    subprocess.run([
                        'powershell', '-NoProfile', '-Command',
                        f"Remove-Item -Recurse -Force -LiteralPath '{str(path)}'"
                    ], check=False)
                except Exception:
                    pass

def _valid_python(exe_path):
    try:
        ok, out, err = run_with_timeout([exe_path, '-c', 'import sys; print(sys.version)'], timeout_seconds=10)
        return ok
    except Exception:
        return False

def _pick_highest(paths):
    # crude but effective: prefer higher major.minor in the path string
    def version_key(p):
        import re
        m = re.search(r'python(\\d{2,3})', p.replace('.', ''))
        return int(m.group(1)) if m else 0
    return sorted(paths, key=version_key, reverse=True)

def find_system_python():
    """
    Find a real system Python for venv creation when running as a frozen EXE.
    Strategy:
    1) py -0p (list all) or py -3 (direct)
    2) python/python3 on PATH
    3) Windows registry (PythonCore) + common install paths
    4) Prompt user for python.exe
    Returns: (cmd_list, python_exe_path) or (None, None)
    """
    candidates_cmds = []
    paths = []

    if platform.system() == 'Windows':
        # 1) Python Launcher discovery
        try:
            ok, out, err = run_with_timeout(['py', '-0p'], timeout_seconds=10)
            if ok and out.strip():
                for line in out.splitlines():
                    p = line.strip()
                    if p.lower().endswith('python.exe') and os.path.exists(p):
                        paths.append(p)
        except Exception:
            pass

        # Also try direct py -3
        try:
            ok, out, err = run_with_timeout(['py', '-3', '-c', 'import sys; print(sys.executable)'], timeout_seconds=10)
            if ok and out.strip():
                p = out.strip()
                if os.path.exists(p):
                    paths.append(p)
        except Exception:
            pass

        # 2) Try python/python3 from PATH
        for name in ['python', 'python3']:
            try:
                ok, out, err = run_with_timeout([name, '-c', 'import sys; print(sys.executable)'], timeout_seconds=10)
                if ok and out.strip():
                    p = out.strip()
                    if os.path.exists(p):
                        paths.append(p)
            except Exception:
                pass

        # 3) Windows registry + common directories
        try:
            import winreg as wr
            for hive in (wr.HKEY_CURRENT_USER, wr.HKEY_LOCAL_MACHINE):
                for root in (r"Software\\Python\\PythonCore", r"Software\\Wow6432Node\\Python\\PythonCore"):
                    try:
                        with wr.OpenKey(hive, root) as k:
                            i = 0
                            while True:
                                try:
                                    ver = wr.EnumKey(k, i)
                                    i += 1
                                except OSError:
                                    break
                                try:
                                    with wr.OpenKey(k, ver + r"\\InstallPath") as ip:
                                        val, _ = wr.QueryValueEx(ip, None)
                                        exe = os.path.join(val, 'python.exe')
                                        if os.path.exists(exe):
                                            paths.append(exe)
                                except OSError:
                                    continue
                    except OSError:
                        continue
        except Exception:
            pass

        # Common install dirs
        env = os.environ
        guesses = []
        for base in [
            env.get('LOCALAPPDATA', ''),
            env.get('PROGRAMFILES', ''),
            env.get('PROGRAMFILES(X86)', ''),
            'C:\\\\Python311', 'C:\\\\Python312', 'C:\\\\Python310', 'C:\\\\Python39',
        ]:
            if not base:
                continue
            guesses.extend([
                os.path.join(base, 'Programs', 'Python', 'Python312', 'python.exe'),
                os.path.join(base, 'Programs', 'Python', 'Python311', 'python.exe'),
                os.path.join(base, 'Programs', 'Python', 'Python310', 'python.exe'),
                os.path.join(base, 'Programs', 'Python', 'Python39', 'python.exe'),
            ])
        for g in guesses:
            if os.path.exists(g):
                paths.append(g)

        # Deduplicate & validate
        uniq = []
        for p in _pick_highest(list(dict.fromkeys(paths))):
            if _valid_python(p):
                uniq.append(p)

        if uniq:
            best = uniq[0]
            return [best], best

        # 4) Prompt as last resort
        print_warning("Could not find a system Python automatically.")
        manual = input("Enter full path to python.exe (or press Enter to cancel): ").strip().strip('\"')
        if manual and os.path.exists(manual) and _valid_python(manual):
            return [manual], manual
        return None, None

    else:
        # Non-Windows: try python3/python
        for name in ['python3', 'python']:
            try:
                ok, out, err = run_with_timeout([name, '-c', 'import sys; print(sys.executable)'], timeout_seconds=10)
                if ok and out.strip():
                    p = out.strip()
                    if os.path.exists(p):
                        return [name], p
            except Exception:
                pass
        return None, None



# --- Python interpreter discovery when running as a frozen EXE ---
def find_system_python():
    candidates = []
    if platform.system() == 'Windows':
        candidates = [
            ['py', '-3'],
            ['py'],
            ['python'],
            ['python3'],
        ]
    else:
        candidates = [
            ['python3'],
            ['python'],
        ]
    for cmd in candidates:
        try:
            success, stdout, stderr = run_with_timeout(cmd + ['-c', 'import sys; print(sys.executable)'], timeout_seconds=10)
            if success and stdout.strip():
                return cmd, stdout.strip()
        except Exception:
            pass
    return None, None


import stat

def _remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def safe_rmtree(path: Path):
    if path.exists():
        try:
            shutil.rmtree(path, onerror=_remove_readonly)
        except Exception:
            # Fallback: attempt PowerShell removal on Windows
            if platform.system() == 'Windows':
                try:
                    subprocess.run([
                        'powershell', '-NoProfile', '-Command', f"Remove-Item -Recurse -Force -LiteralPath '{str(path)}'"
                    ], check=False)
                except Exception:
                    pass


# --- Configuration ---
APP_NAME = "Canis.lab"
REPO_URL = "https://github.com/crasyK/Canis.lab"
ICON_URL_PNG = f"{REPO_URL}/raw/main/icon.png"
ICON_URL_ICO = f"{REPO_URL}/raw/main/Icon.ico"

# --- Helper Functions ---
def print_header(text):
    line = '='*60
    print(f"\n{line}\n {text}\n{line}")

def _supports_unicode():
    try:
        enc = (sys.stdout and sys.stdout.encoding) or ''
        return 'utf' in enc.lower()
    except Exception:
        return False

_UNICODE_OK = _supports_unicode()

def _decorate(prefix_unicode, prefix_ascii, text):
    prefix = prefix_unicode if _UNICODE_OK else prefix_ascii
    return f"{prefix} {text}"

def print_success(text):
    print(_decorate('✅', '[OK]', text))

def print_warning(text):
    print(_decorate('⚠️', '[!]', text))

def print_error(text, exit_code=1):
    print(_decorate('❌', 'ERROR:', text))
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

def run_with_timeout(command, timeout_seconds=30, cwd=None):
    """Run a command with a timeout."""
    try:
        result = subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=timeout_seconds,
            cwd=cwd
        )
        return True, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout_seconds} seconds"
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except Exception as e:
        return False, "", str(e)

def check_tool_available(tool_name, command):
    """Check if a tool/command is available in PATH and responsive."""
    try:
        success, stdout, stderr = run_with_timeout(command, timeout_seconds=10)
        return success
    except FileNotFoundError:
        return False

def create_virtual_environment(install_path):
    """Creates a Python virtual environment, robust on Windows and when frozen."""
    venv_path = install_path / ".venv"
    print(f"🐍 Setting up Python environment in '{venv_path}'...")

    # Clean any previous venv safely (Windows can lock files)
    if venv_path.exists():
        print("   Removing existing virtual environment...")
        try:
            safe_rmtree(venv_path)
        except Exception:
            pass

    # Decide which Python to use
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller EXE -> find a real system Python
        python_cmd, python_exe = find_system_python()
        if not python_cmd:
            print_error("No system Python interpreter found. Please install Python 3.9+ and ensure 'py' or 'python' is on PATH.")
    else:
        # Running as a script -> use the current interpreter
        python_cmd = [sys.executable]
        python_exe = sys.executable

    # Make sure the external interpreter has pip
    run_with_timeout(python_cmd + ['-m', 'ensurepip', '--upgrade'], timeout_seconds=120)
    run_with_timeout(python_cmd + ['-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'], timeout_seconds=300)

    # Build method list using that interpreter; avoid bare 'virtualenv' binary
    methods = []
    methods.append({
        'name': 'venv',
        'check_cmd': python_cmd + ['-m', 'venv', '--help'],
        'install_cmd': None,
        'create_cmd': python_cmd + ['-m', 'venv', str(venv_path)],
        'description': 'built-in venv module'
    })
    methods.append({
        'name': 'virtualenv',
        'check_cmd': python_cmd + ['-m', 'virtualenv', '--version'],
        'install_cmd': python_cmd + ['-m', 'pip', 'install', 'virtualenv'],
        'create_cmd': python_cmd + ['-m', 'virtualenv', '-p', python_exe, str(venv_path)],
        'description': 'virtualenv (fallback)'
    })

    print("   Checking available virtual environment tools...")
    for method in methods:
        print(f"   Trying {method['description']}...")
        if not check_tool_available(method['name'], method['check_cmd']):
            if method.get('install_cmd'):
                print(f"     {method['name']} not found, attempting to install...")
                success, stdout, stderr = run_with_timeout(method['install_cmd'], timeout_seconds=600)
                if not success:
                    print(f"     Failed to install {method['name']}: {stderr}")
                    continue
                print(f"     {method['name']} installed successfully")
            else:
                print(f"     {method['name']} not available")
                continue

        # Try to create venv
        print(f"     Creating virtual environment with {method['name']}...")
        success, stdout, stderr = run_with_timeout(method['create_cmd'], timeout_seconds=900, cwd=install_path)
        if not success:
            print_warning(f"{method['name']} failed to create venv: {stderr}")
            try:
                safe_rmtree(venv_path)
            except Exception:
                pass
            continue

        # Find Python inside venv
        python_in_venv = find_venv_python(venv_path)
        if not python_in_venv:
            print_warning(f"{method['name']} created directory but Python executable not found")
            try:
                safe_rmtree(venv_path)
            except Exception:
                pass
            continue

        # Ensure pip is available in the venv and up to date
        print("     Ensuring pip/setuptools/wheel are available...")
        run_with_timeout([str(python_in_venv), '-m', 'ensurepip', '--upgrade'], timeout_seconds=240)
        ok2, so2, se2 = run_with_timeout([str(python_in_venv), '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'], timeout_seconds=600)
        if not ok2:
            print_warning("Could not upgrade pip/setuptools/wheel; continuing anyway.")

        print_success(f"Virtual environment created with {method['name']}")
        return venv_path

    # If all methods failed
    print_warning("Could not create a virtual environment automatically.")
    print("\nOptions:")
    print("1. Exit and set up Python/venv manually, then rerun installer")
    print("2. Attempt global dependency install (not recommended)")
    choice = input("Choose option (1 or 2): ").strip()
    if choice == '2':
        print_warning("Will install dependencies globally. This may cause conflicts.")
        return None
    else:
        sys.exit(1)


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
            success, stdout, stderr = run_with_timeout([str(python_exe), "--version"], timeout_seconds=5)
            if success:
                print(f"   ✅ Found working Python executable: {python_exe}")
                return python_exe
    
    return None

def install_dependencies_with_progress(venv_path, requirements_file):
    """Installs dependencies, with or without virtual environment."""
    print("Installing Python dependencies...")
    print("This may take a few minutes...")
    
    if venv_path and venv_path.exists():
        # Try to install in virtual environment
        python_exe = find_venv_python(venv_path)
        if python_exe:
            print("   Installing into virtual environment...")
            command = [str(python_exe), "-m", "pip", "install", "-r", str(requirements_file)]
        else:
            print_error("Virtual environment exists but Python executable not found.", exit_code=None)
            return
    else:
        # This should not happen anymore with our improved logic
        print_error("No virtual environment available and global installation not recommended.", exit_code=None)
        return
    
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

def create_windows_shortcut_powershell(script_path, install_path, icon_path):
    """Creates a Windows shortcut using PowerShell."""
    desktop_path = Path.home() / "Desktop"
    shortcut_path = desktop_path / f"{APP_NAME}.lnk"
    
    # PowerShell script to create shortcut
    ps_script = f'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{script_path}"
$Shortcut.WorkingDirectory = "{install_path}"
$Shortcut.Description = "Launch {APP_NAME}"
'''
    
    # Add icon if it exists
    if icon_path and icon_path.exists():
        ps_script += f'$Shortcut.IconLocation = "{icon_path}"\n'
    
    ps_script += '$Shortcut.Save()'
    
    try:
        # Run PowerShell command
        subprocess.run([
            "powershell", "-Command", ps_script
        ], check=True, capture_output=True, text=True)
        
        return shortcut_path.exists()
    except subprocess.CalledProcessError as e:
        print_warning(f"PowerShell shortcut creation failed: {e}")
        return False

def create_windows_shortcut_vbs(script_path, install_path, icon_path):
    """Creates a Windows shortcut using VBScript as fallback."""
    desktop_path = Path.home() / "Desktop"
    shortcut_path = desktop_path / f"{APP_NAME}.lnk"
    
    # Create temporary VBS script
    vbs_content = f'''
Set WshShell = CreateObject("WScript.Shell")
Set oShellLink = WshShell.CreateShortcut("{shortcut_path}")
oShellLink.TargetPath = "{script_path}"
oShellLink.WorkingDirectory = "{install_path}"
oShellLink.Description = "Launch {APP_NAME}"
'''
    
    # Add icon if it exists
    if icon_path and icon_path.exists():
        vbs_content += f'oShellLink.IconLocation = "{icon_path}"\n'
    
    vbs_content += 'oShellLink.Save'
    
    # Write temporary VBS file
    temp_vbs = install_path / "create_shortcut.vbs"
    try:
        temp_vbs.write_text(vbs_content, encoding='utf-8')
        
        # Run the VBS script
        subprocess.run([
            "cscript", "//NoLogo", str(temp_vbs)
        ], check=True, capture_output=True, text=True, cwd=install_path)
        
        # Clean up
        temp_vbs.unlink()
        
        return shortcut_path.exists()
    except Exception as e:
        print_warning(f"VBScript shortcut creation failed: {e}")
        # Clean up on failure
        if temp_vbs.exists():
            temp_vbs.unlink()
        return False

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
call .venv\\Scripts\\activate.bat
echo Launching Streamlit...
python -m python -m streamlit run app.py
pause
"""
        else:
            script_content = f"""@echo off
echo Starting {APP_NAME}...
cd /D "%~dp0"
echo Launching Streamlit...
python -m python -m streamlit run app.py
pause
"""
    else:  # Linux & macOS
        script_name = f"run_{APP_NAME.lower().replace('.', '_')}.sh"
        if has_venv:
            script_content = f"""#!/bin/bash
cd "$(dirname "$0")"
echo "Activating virtual environment and starting {APP_NAME}..."
# Use . instead of source for broader shell compatibility
. .venv/bin/activate
echo "Launching Streamlit..."
python -m python -m streamlit run app.py
"""
        else:
            script_content = f"""#!/bin/bash
cd "$(dirname "$0")"
echo "Starting {APP_NAME}..."
python -m python -m streamlit run app.py
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
        # Try PowerShell method first
        success = create_windows_shortcut_powershell(script_path, install_path, icon_path)
        
        if not success:
            print("   PowerShell method failed, trying VBScript...")
            success = create_windows_shortcut_vbs(script_path, install_path, icon_path)
        
        if success:
            print_success("Windows desktop shortcut created.")
        else:
            print_warning("Could not create Windows shortcut automatically.")
            print_warning(f"You can manually create a shortcut to: {script_path}")

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
    
    if not has_venv:
        print_error("Could not create virtual environment. Installation cannot continue.")
    
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

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")
