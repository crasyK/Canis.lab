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
        # Windows might not support colors
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
        
        # Provide download links
        system = platform.system().lower()
        if system == "windows":
            print_colored("   Download Python: https://www.python.org/downloads/windows/", Colors.WARNING)
        elif system == "darwin":  # macOS
            print_colored("   Download Python: https://www.python.org/downloads/macos/", Colors.WARNING)
        else:  # Linux
            print_colored("   Install Python: sudo apt install python3.8+ (Ubuntu/Debian)", Colors.WARNING)
            print_colored("   Or visit: https://www.python.org/downloads/", Colors.WARNING)
        
        return False
    
    print_colored(f"✅ Python {version.major}.{version.minor}.{version.micro} - Perfect!", Colors.OKGREEN)
    return True

def get_install_location():
    """Ask user where to install Canis.lab"""
    print_colored("\n📍 Choose installation location:", Colors.BOLD)
    
    # Default location
    home = Path.home()
    default_path = home / "canis-lab"
    
    print_colored(f"   Default: {default_path}", Colors.OKCYAN)
    custom_path = input("   Enter custom path (or press Enter for default): ").strip()
    
    if custom_path:
        install_path = Path(custom_path)
    else:
        install_path = default_path
    
    # Check if directory exists
    if install_path.exists():
        print_colored(f"   Directory {install_path} already exists", Colors.WARNING)
        choice = input("   Continue anyway? (y/N): ").strip().lower()
        if choice != 'y':
            print_colored("   Installation cancelled", Colors.WARNING)
            return None
    
    return install_path

def download_canis_lab(install_path):
    """Download Canis.lab from repository"""
    print_colored("📥 Downloading Canis.lab...", Colors.OKBLUE)
    
    # GitHub repository URL (adjust this to your actual repo)
    repo_url = "https://github.com/your-username/canis-lab"  # UPDATE THIS!
    zip_url = f"{repo_url}/archive/main.zip"
    
    try:
        # Create install directory
        install_path.mkdir(parents=True, exist_ok=True)
        
        # Download the zip file
        print_colored("   Downloading from GitHub...", Colors.OKCYAN)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            urllib.request.urlretrieve(zip_url, tmp_file.name)
            zip_path = tmp_file.name
        
        # Extract the zip file
        print_colored("   Extracting files...", Colors.OKCYAN)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(install_path)
        
        # Move files from subfolder to main directory
        extracted_folder = install_path / "canis-lab-main"  # GitHub creates this folder
        if extracted_folder.exists():
            for item in extracted_folder.iterdir():
                shutil.move(str(item), str(install_path))
            extracted_folder.rmdir()
        
        # Clean up
        os.unlink(zip_path)
        
        print_colored("✅ Canis.lab downloaded successfully!", Colors.OKGREEN)
        return True
        
    except Exception as e:
        print_colored(f"❌ Download failed: {e}", Colors.FAIL)
        print_colored("   Please check your internet connection and try again", Colors.WARNING)
        return False

def create_requirements_file(install_path):
    """Create requirements.txt if it doesn't exist"""
    requirements_path = install_path / "requirements.txt"
    
    if not requirements_path.exists():
        print_colored("   Creating requirements.txt...", Colors.OKCYAN)
        requirements_content = """streamlit>=1.28.0
streamlit-flow>=0.7.0
openai>=1.0.0
datasets>=2.14.0
python-dotenv>=1.0.0
"""
        with open(requirements_path, 'w') as f:
            f.write(requirements_content)

def create_basic_files(install_path):
    """Create basic project files if they don't exist"""
    print_colored("📝 Setting up project files...", Colors.OKBLUE)
    
    # Create requirements.txt
    create_requirements_file(install_path)
    
    # Create .env.example
    env_example_path = install_path / ".env.example"
    if not env_example_path.exists():
        print_colored("   Creating .env.example...", Colors.OKCYAN)
        env_content = """# Canis.lab Configuration
# Copy this file to '.env' and add your OpenAI API key

# Required: OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Optional: OpenAI Organization ID
# OPENAI_ORG_ID=your_org_id_here
"""
        with open(env_example_path, 'w') as f:
            f.write(env_content)
    
    # Create basic Home.py if it doesn't exist
    home_py_path = install_path / "Home.py"
    if not home_py_path.exists():
        print_colored("   Creating basic Home.py...", Colors.OKCYAN)
        home_content = """import streamlit as st

st.set_page_config(page_title="Canis.lab", layout="wide")

st.title("🧬 Canis.lab")
st.subheader("Synthetic Dataset Generation Platform")

st.info("Welcome to Canis.lab! Use the sidebar to navigate to different tools.")

# Check if properly configured
import os
from pathlib import Path

if not Path('.env').exists():
    st.error("⚠️ Environment not configured. Please run the installer or set up .env file.")
    st.stop()

# Basic navigation
st.markdown("## Available Tools")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🌱 Seed Architect")
    st.markdown("Create seed files for dataset generation")
    if st.button("Open Seed Architect"):
        st.switch_page("pages/seed_architect.py")

with col2:
    st.markdown("### ⚙️ Workflow Editor") 
    st.markdown("Build and execute data processing workflows")
    if st.button("Open Workflow Editor"):
        st.switch_page("pages/workflow_editor.py")
"""
        with open(home_py_path, 'w') as f:
            f.write(home_content)

def install_dependencies(install_path):
    """Install Python dependencies"""
    print_colored("📦 Installing dependencies...", Colors.OKBLUE)
    
    # Change to install directory
    original_dir = Path.cwd()
    os.chdir(install_path)
    
    try:
        # Check if pip is available
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
        
        # Upgrade pip
        print_colored("   Upgrading pip...", Colors.OKCYAN)
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      capture_output=True, check=True)
        
        # Install requirements
        print_colored("   Installing packages (this may take several minutes)...", Colors.OKCYAN)
        print_colored("   ☕ Perfect time for a coffee break!", Colors.WARNING)
        
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                               capture_output=True, text=True)
        
        if result.returncode != 0:
            print_colored("❌ Failed to install some packages", Colors.FAIL)
            print_colored("Error details:", Colors.WARNING)
            print_colored(result.stderr, Colors.FAIL)
            return False
        
        print_colored("✅ All dependencies installed!", Colors.OKGREEN)
        return True
        
    except Exception as e:
        print_colored(f"❌ Installation failed: {e}", Colors.FAIL)
        return False
    finally:
        # Return to original directory
        os.chdir(original_dir)

def setup_environment(install_path):
    """Interactive environment setup"""
    print_colored("🔧 Setting up environment...", Colors.OKBLUE)
    
    env_file = install_path / ".env"
    
    print_colored("\n🔑 OpenAI API Configuration", Colors.BOLD)
    print_colored("   Canis.lab uses OpenAI for AI processing.", Colors.OKCYAN)
    print_colored("   Get your free API key at: https://platform.openai.com/api-keys", Colors.OKCYAN)
    
    # Option to open browser
    open_browser = input("\n   Open API key page in browser? (Y/n): ").strip().lower()
    if open_browser in ('', 'y', 'yes'):
        webbrowser.open('https://platform.openai.com/api-keys')
        print_colored("   Browser opened! Get your API key and come back here.", Colors.WARNING)
        input("   Press Enter when you have your API key...")
    
    api_key = input("\n   Paste your OpenAI API key (or press Enter to skip): ").strip()
    
    if api_key:
        # Basic validation
        if not api_key.startswith(('sk-', 'sk-proj-')):
            print_colored("   ⚠️  That doesn't look like an OpenAI API key", Colors.WARNING)
            print_colored("   OpenAI keys usually start with 'sk-'", Colors.WARNING)
            proceed = input("   Use it anyway? (y/N): ").strip().lower()
            if proceed != 'y':
                api_key = ""
        
        if api_key:
            with open(env_file, 'w') as f:
                f.write("# Canis.lab Configuration\n")
                f.write(f"OPENAI_API_KEY={api_key}\n")
            print_colored("   ✅ Environment configured!", Colors.OKGREEN)
            return True
    
    # Create template if no API key provided
    with open(env_file, 'w') as f:
        f.write("# Canis.lab Configuration\n")
        f.write("# Add your OpenAI API key below:\n")
        f.write("OPENAI_API_KEY=your_openai_api_key_here\n")
    
    print_colored("   ⚠️  Environment created but API key needed", Colors.WARNING)
    print_colored(f"   Edit {env_file} to add your API key before using the app", Colors.WARNING)
    return True

def create_launch_script(install_path):
    """Create convenient launch scripts"""
    print_colored("🚀 Creating launch scripts...", Colors.OKBLUE)
    
    # Python launch script
    launch_py = install_path / "launch.py"
    with open(launch_py, 'w') as f:
        f.write("""#!/usr/bin/env python3
import subprocess
import sys
import os
from pathlib import Path

# Change to script directory
os.chdir(Path(__file__).parent)

print("🧬 Starting Canis.lab...")
print("Your browser should open automatically")
print("Press Ctrl+C to stop the application")

try:
    subprocess.run([sys.executable, "-m", "streamlit", "run", "Home.py"])
except KeyboardInterrupt:
    print("\\n👋 Canis.lab stopped")
""")
    
    # Shell script for Unix/Mac
    if platform.system() != 'Windows':
        launch_sh = install_path / "launch.sh"
        with open(launch_sh, 'w') as f:
            f.write("""#!/bin/bash
cd "$(dirname "$0")"
echo "🧬 Starting Canis.lab..."
python3 launch.py
""")
        # Make executable
        os.chmod(launch_sh, 0o755)
    
    # Batch file for Windows
    if platform.system() == 'Windows':
        launch_bat = install_path / "launch.bat"
        with open(launch_bat, 'w') as f:
            f.write("""@echo off
cd /d "%~dp0"
echo 🧬 Starting Canis.lab...
python launch.py
pause
""")
    
    print_colored("   ✅ Launch scripts created!", Colors.OKGREEN)

def test_installation(install_path):
    """Test the installation"""
    print_colored("🧪 Testing installation...", Colors.OKBLUE)
    
    original_dir = Path.cwd()
    os.chdir(install_path)
    
    try:
        # Test streamlit
        result = subprocess.run([sys.executable, "-c", "import streamlit; print('Streamlit OK')"], 
                               capture_output=True, text=True)
        if result.returncode != 0:
            print_colored("   ⚠️  Streamlit test failed", Colors.WARNING)
            return False
        
        print_colored("   ✅ Streamlit working", Colors.OKGREEN)
        return True
        
    except Exception as e:
        print_colored(f"   ❌ Test failed: {e}", Colors.FAIL)
        return False
    finally:
        os.chdir(original_dir)

def launch_application(install_path):
    """Launch the application"""
    print_colored("🎉 Installation complete! Ready to launch!", Colors.OKGREEN)
    
    choice = input("\n   Launch Canis.lab now? (Y/n): ").strip().lower()
    if choice in ('', 'y', 'yes'):
        print_colored("   Starting Canis.lab...", Colors.OKCYAN)
        print_colored("   Your browser should open automatically", Colors.OKCYAN)
        print_colored("   Press Ctrl+C to stop the app", Colors.WARNING)
        
        original_dir = Path.cwd()
        os.chdir(install_path)
        
        try:
            subprocess.run([sys.executable, "-m", "streamlit", "run", "Home.py"])
        except KeyboardInterrupt:
            print_colored("\n👋 Thanks for using Canis.lab!", Colors.OKGREEN)
        except Exception as e:
            print_colored(f"❌ Launch failed: {e}", Colors.FAIL)
        finally:
            os.chdir(original_dir)

def show_completion_message(install_path):
    """Show installation completion message"""
    system = platform.system()
    
    if system == 'Windows':
        launch_cmd = "launch.bat"
    else:
        launch_cmd = "./launch.sh"
    
    completion_msg = f"""
    ╔════════════════════════════════════════════╗
    ║               🎉 SUCCESS! 🎉               ║
    ║                                            ║
    ║         Canis.lab is installed!            ║
    ║                                            ║
    ║    📍 Location: {str(install_path):<25} ║
    ║                                            ║
    ║    🚀 To start Canis.lab:                  ║
    ║       cd {str(install_path.name):<30} ║
    ║       {launch_cmd:<35} ║
    ║                                            ║
    ║    📚 Need help? Check README.md           ║
    ║    🐛 Issues? GitHub Issues page          ║
    ╚════════════════════════════════════════════╝
    """
    print_colored(completion_msg, Colors.OKGREEN)

def main():
    """Main installer function"""
    print_header()
    
    print_colored("This installer will download and set up Canis.lab automatically!", Colors.OKCYAN)
    print_colored("No other files needed - everything is downloaded for you! 📥", Colors.OKCYAN)
    
    input("\nPress Enter to continue...")
    
    # System checks
    if not check_internet():
        sys.exit(1)
    
    if not check_python_version():
        sys.exit(1)
    
    # Get installation location
    install_path = get_install_location()
    if not install_path:
        sys.exit(1)
    
    print_colored(f"\n📍 Installing to: {install_path}", Colors.BOLD)
    
    # Download Canis.lab
    if not download_canis_lab(install_path):
        print_colored("Failed to download Canis.lab", Colors.FAIL)
        sys.exit(1)
    
    # Create any missing basic files
    create_basic_files(install_path)
    
    # Install dependencies
    if not install_dependencies(install_path):
        print_colored("Failed to install dependencies", Colors.FAIL)
        sys.exit(1)
    
    # Setup environment
    setup_environment(install_path)
    
    # Create launch scripts
    create_launch_script(install_path)
    
    # Test installation
    if not test_installation(install_path):
        print_colored("Installation test failed, but continuing anyway", Colors.WARNING)
    
    # Launch or show completion
    launch_application(install_path)
    show_completion_message(install_path)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n👋 Installation cancelled by user", Colors.WARNING)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n💥 Unexpected error: {e}", Colors.FAIL)
        print_colored("Please report this issue on GitHub", Colors.WARNING)
        sys.exit(1)
