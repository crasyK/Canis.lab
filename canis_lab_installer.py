#!/usr/bin/env python3
"""
🧬 CANIS.LAB SINGLE-CLICK INSTALLER 🧬
=====================================
Complete standalone installer - downloads and sets up everything!

Just download this file and run: python canis_lab_installer.py
No other files needed!
"""

import os
import sys
import subprocess
import platform
import urllib.request
import urllib.error
import json
import zipfile
import tempfile
import shutil
from pathlib import Path
import webbrowser
import time

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_colored(text, color=Colors.OKGREEN):
    """Print colored text to terminal"""
    if platform.system() == 'Windows':
        print(text)
    else:
        print(f"{color}{text}{Colors.ENDC}")

def print_header():
    """Print fancy installer header"""
    header = """
    ╔════════════════════════════════════════════╗
    ║            🧬 CANIS.LAB 🧬                 ║
    ║       Synthetic Dataset Generation         ║
    ║         SINGLE-CLICK INSTALLER            ║
    ║                                            ║
    ║  📥 Downloads everything automatically     ║
    ║  ⚡ Sets up in minutes                     ║
    ║  🚀 Launches when ready                    ║
    ╚════════════════════════════════════════════╝
    """
    print_colored(header, Colors.HEADER)

def check_internet():
    """Check if internet connection is available"""
    print_colored("🌐 Checking internet connection...", Colors.OKBLUE)
    try:
        urllib.request.urlopen('https://www.google.com', timeout=5)
        print_colored("✅ Internet connection available", Colors.OKGREEN)
        return True
    except urllib.error.URLError:
        print_colored("❌ No internet connection", Colors.FAIL)
        print_colored("   Internet is required to download Canis.lab", Colors.WARNING)
        return False

def check_python_version():
    """Check if Python version is compatible"""
    print_colored("🐍 Checking Python version...", Colors.OKBLUE)
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_colored(f"❌ Python {version.major}.{version.minor} detected", Colors.FAIL)
        print_colored("   Canis.lab requires Python 3.8 or higher", Colors.FAIL)
        system = platform.system().lower()
        if system == "windows":
            print_colored("   Download Python: https://www.python.org/downloads/windows/", Colors.WARNING)
        elif system == "darwin":  # macOS
            print_colored("   Download Python: https://www.python.org/downloads/macos/", Colors.WARNING)
        else:  # Linux
            print_colored("   Install Python: sudo apt install python3.8+ (Ubuntu/Debian)", Colors.WARNING)
        return False
    print_colored(f"✅ Python {version.major}.{version.minor}.{version.micro} - Perfect!", Colors.OKGREEN)
    return True

def get_install_location():
    """Ask user where to install Canis.lab"""
    print_colored("\n📍 Choose installation location:", Colors.BOLD)
    home = Path.home()
    default_path = home / "canis-lab"
    print_colored(f"   Default: {default_path}", Colors.OKCYAN)
    custom_path = input("   Enter custom path (or press Enter for default): ").strip()
    
    install_path = Path(custom_path) if custom_path else default_path
    
    if install_path.exists():
        print_colored(f"   Directory {install_path} already exists", Colors.WARNING)
        choice = input("   Overwrite or continue installation in this folder? (y/N): ").strip().lower()
        if choice not in ('y', 'yes'):
            print_colored("   Installation cancelled.", Colors.WARNING)
            return None
    
    return install_path

def download_canis_lab(install_path):
    """Download Canis.lab from repository"""
    print_colored("📥 Downloading Canis.lab...", Colors.OKBLUE)
    repo_url = "https://github.com/crasyK/Canis.lab"
    zip_url = f"{repo_url}/archive/main.zip"
    
    try:
        install_path.mkdir(parents=True, exist_ok=True)
        print_colored("   Downloading from GitHub...", Colors.OKCYAN)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            urllib.request.urlretrieve(zip_url, tmp_file.name)
            zip_path = tmp_file.name
        
        print_colored("   Extracting files...", Colors.OKCYAN)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(install_path)
        
        # Correctly handle the extracted folder name (e.g., 'Canis.lab-main')
        extracted_folder_name = "Canis.lab-main"
        extracted_folder = install_path / extracted_folder_name
        
        if extracted_folder.exists():
            for item in extracted_folder.iterdir():
                shutil.move(str(item), install_path / item.name)
            extracted_folder.rmdir()
        
        os.unlink(zip_path)
        print_colored("✅ Canis.lab downloaded successfully!", Colors.OKGREEN)
        return True
    except Exception as e:
        print_colored(f"❌ Download failed: {e}", Colors.FAIL)
        return False

def create_basic_files(install_path):
    """Create basic project files if they don't exist"""
    print_colored("📝 Setting up project files...", Colors.OKBLUE)
    
    # Create requirements.txt
    requirements_path = install_path / "requirements.txt"
    if not requirements_path.exists():
        print_colored("   Creating requirements.txt...", Colors.OKCYAN)
        requirements_content = "streamlit\nstreamlit-flow\nopenai\ndatasets\npython-dotenv\n"
        with open(requirements_path, 'w') as f:
            f.write(requirements_content)

    # Create .env example
    env_file = install_path / ".env"
    if not env_file.exists():
        print_colored("   Creating .env file for API key...", Colors.OKCYAN)
        env_content = "# Canis.lab Configuration\nOPENAI_API_KEY=your_openai_api_key_here\n"
        with open(env_file, 'w') as f:
            f.write(env_content)
    
    # Create basic Home.py
    home_py_path = install_path / "Home.py"
    if not home_py_path.exists():
        print_colored("   Creating basic Home.py...", Colors.OKCYAN)
        home_content = """import streamlit as st
st.set_page_config(page_title="Canis.lab", layout="wide")
st.title("🧬 Canis.lab")
st.info("Welcome! Use the sidebar to navigate.")
"""
        with open(home_py_path, 'w') as f:
            f.write(home_content)

def install_dependencies(install_path):
    """Install Python dependencies with real-time output"""
    print_colored("📦 Installing dependencies...", Colors.OKBLUE)
    original_dir = Path.cwd()
    os.chdir(install_path)
    
    try:
        print_colored("   Installing packages (this may take several minutes)...", Colors.OKCYAN)
        print_colored("   ☕ Perfect time for a coffee break!", Colors.WARNING)
        
        # Stream output directly to the console
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True
        )
        
        print_colored("✅ All dependencies installed!", Colors.OKGREEN)
        return True
    except subprocess.CalledProcessError:
        print_colored("\n❌ An error occurred during package installation.", Colors.FAIL)
        print_colored("   Please scroll up to review the error messages from 'pip'.", Colors.WARNING)
        print_colored("   This could be due to network issues or package conflicts.", Colors.WARNING)
        return False
    except Exception as e:
        print_colored(f"❌ A critical error occurred: {e}", Colors.FAIL)
        return False
    finally:
        os.chdir(original_dir)

def setup_environment(install_path):
    """Interactive environment setup"""
    print_colored("🔧 Setting up environment...", Colors.OKBLUE)
    env_file = install_path / ".env"
    
    print_colored("\n🔑 OpenAI API Configuration", Colors.BOLD)
    print_colored("   Get your API key at: https://platform.openai.com/api-keys", Colors.OKCYAN)
    
    api_key = input("\n   Paste your OpenAI API key (or press Enter to skip): ").strip()
    
    if api_key:
        with open(env_file, 'w') as f:
            f.write(f"OPENAI_API_KEY={api_key}\n")
        print_colored("   ✅ Environment configured!", Colors.OKGREEN)
    else:
        print_colored("   ⚠️  API key skipped. You must edit the .env file later.", Colors.WARNING)

def create_launch_script(install_path):
    """Create convenient launch scripts"""
    print_colored("🚀 Creating launch scripts...", Colors.OKBLUE)
    
    # Common python launcher
    launch_py_content = """import subprocess, sys, os
os.chdir(os.path.dirname(__file__))
print("🧬 Starting Canis.lab...")
try:
    subprocess.run([sys.executable, "-m", "streamlit", "run", "Home.py"])
except KeyboardInterrupt:
    print("\\n👋 Canis.lab stopped")
"""
    with open(install_path / "launch.py", 'w') as f:
        f.write(launch_py_content)

    # OS-specific scripts
    if platform.system() == 'Windows':
        with open(install_path / "launch.bat", 'w') as f:
            f.write('@echo off\ncd /d "%~dp0"\npython launch.py\npause')
    else:
        launch_sh_path = install_path / "launch.sh"
        with open(launch_sh_path, 'w') as f:
            f.write('#!/bin/bash\ncd "$(dirname "$0")"\npython3 launch.py')
        os.chmod(launch_sh_path, 0o755)
        
    print_colored("   ✅ Launch scripts created!", Colors.OKGREEN)

def launch_application(install_path):
    """Launch the application"""
    print_colored("\n🎉 Installation complete!", Colors.OKGREEN)
    choice = input("   Launch Canis.lab now? (Y/n): ").strip().lower()
    if choice in ('', 'y', 'yes'):
        if platform.system() == 'Windows':
            subprocess.run([install_path / "launch.bat"])
        else:
            subprocess.run([install_path / "launch.sh"])

def show_completion_message(install_path):
    launch_cmd = "launch.bat" if platform.system() == 'Windows' else "./launch.sh"
    completion_msg = f"""
    ╔════════════════════════════════════════════╗
    ║               🎉 SUCCESS! 🎉               ║
    ║         Canis.lab is installed in:         ║
    ║    {str(install_path):<37} ║
    ║                                            ║
    ║    To start it later, run:                 ║
    ║       cd "{str(install_path)}"             ║
    ║       {launch_cmd:<35} ║
    ╚════════════════════════════════════════════╝
    """
    print_colored(completion_msg, Colors.OKGREEN)

def main():
    """Main installer function"""
    print_header()
    input("Press Enter to begin the installation...")
    
    if not (check_internet() and check_python_version()):
        sys.exit(1)
    
    install_path = get_install_location()
    if not install_path:
        sys.exit(1)
    
    print_colored(f"\n📍 Installing to: {install_path}", Colors.BOLD)
    
    if not download_canis_lab(install_path):
        sys.exit(1)
        
    create_basic_files(install_path)
    
    if not install_dependencies(install_path):
        sys.exit(1)
    
    setup_environment(install_path)
    create_launch_script(install_path)
    
    show_completion_message(install_path)
    launch_application(install_path)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n👋 Installation cancelled by user.", Colors.WARNING)
    except Exception as e:
        print_colored(f"\n💥 An unexpected error occurred: {e}", Colors.FAIL)
