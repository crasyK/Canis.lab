#!/usr/bin/env python3
"""
CANIS.LAB STANDALONE INSTALLER
===============================================================================
A self-contained installer that works without Python pre-installed.
Downloads and sets up Canis.lab automatically.
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
import webbrowser
import argparse
from pathlib import Path
import time
import signal

# Version information
__version__ = "1.0.0"
__author__ = "Canis.lab Team"

# Color codes for terminal output
class Colors:
    HEADER = '\\033[95m'
    OKBLUE = '\\033[94m'
    OKCYAN = '\\033[96m'
    OKGREEN = '\\033[92m'
    WARNING = '\\033[93m'
    FAIL = '\\033[91m'
    ENDC = '\\033[0m'
    BOLD = '\\033[1m'

class CanislabInstaller:
    def __init__(self):
        self.system = platform.system()
        self.is_windows = self.system == 'Windows'
        self.temp_dir = None
        self.install_path = None
        self.verbose = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully"""
        self.print_colored("\\n⚠️  Installation interrupted by user", Colors.WARNING)
        self.cleanup()
        sys.exit(1)
    
    def print_colored(self, text, color=Colors.OKGREEN):
        """Print colored text to terminal"""
        if self.is_windows:
            # Try to enable ANSI colors on Windows
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
                print(f"{color}{text}{Colors.ENDC}")
            except:
                print(text)
        else:
            print(f"{color}{text}{Colors.ENDC}")
    
    def print_header(self):
        """Print fancy installer header"""
        header = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║                        🐕 CANIS.LAB 🐕                       ║
║                                                              ║
║              Synthetic Dataset Generation Platform           ║
║                                                              ║
║                    STANDALONE INSTALLER                      ║
║                        Version {__version__}                         ║
║                                                              ║
║  ✨ Downloads everything automatically                       ║
║  ⚡ Sets up in minutes                                       ║
║  🚀 Launches when ready                                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """
        self.print_colored(header, Colors.HEADER)
    
    def check_system_requirements(self):
        """Check system requirements"""
        self.print_colored("🔍 Checking system requirements...", Colors.OKBLUE)
        
        # Check Python version
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.print_colored(f"❌ Python {version.major}.{version.minor} detected", Colors.FAIL)
            self.print_colored("   Canis.lab requires Python 3.8 or higher", Colors.FAIL)
            
            if self.is_windows:
                self.print_colored("   Download from: https://python.org/downloads/", Colors.OKCYAN)
                choice = input("   Open download page? (y/N): ").strip().lower()
                if choice in ('y', 'yes'):
                    webbrowser.open("https://python.org/downloads/")
            
            return False
        
        self.print_colored(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible!", Colors.OKGREEN)
        
        # Check available disk space
        try:
            if self.is_windows:
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(os.getcwd()), ctypes.pointer(free_bytes), None, None)
                free_space_gb = free_bytes.value / (1024**3)
            else:
                statvfs = os.statvfs(os.getcwd())
                free_space_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
            
            if free_space_gb < 1.0:
                self.print_colored(f"⚠️  Low disk space: {free_space_gb:.1f} GB available", Colors.WARNING)
                self.print_colored("   At least 1 GB recommended", Colors.WARNING)
            else:
                self.print_colored(f"✅ Disk space: {free_space_gb:.1f} GB available", Colors.OKGREEN)
        
        except Exception as e:
            if self.verbose:
                self.print_colored(f"⚠️  Could not check disk space: {e}", Colors.WARNING)
        
        return True
    
    def check_internet(self):
        """Check if internet connection is available"""
        self.print_colored("🌐 Checking internet connection...", Colors.OKBLUE)
        
        test_urls = [
            'https://www.google.com',
            'https://github.com',
            'https://httpbin.org/get'
        ]
        
        for url in test_urls:
            try:
                urllib.request.urlopen(url, timeout=10)
                self.print_colored("✅ Internet connection available", Colors.OKGREEN)
                return True
            except urllib.error.URLError:
                continue
        
        self.print_colored("❌ No internet connection", Colors.FAIL)
        self.print_colored("   Internet is required to download Canis.lab", Colors.WARNING)
        self.print_colored("   Please check your connection and try again", Colors.WARNING)
        return False
    
    def get_install_location(self):
        """Ask user where to install Canis.lab"""
        self.print_colored("\\n📁 Choose installation location:", Colors.BOLD)
        
        home = Path.home()
        default_path = home / "canis-lab"
        
        self.print_colored(f"   Default: {default_path}", Colors.OKCYAN)
        
        while True:
            custom_path = input("   Enter custom path (or press Enter for default): ").strip()
            
            if not custom_path:
                install_path = default_path
            else:
                install_path = Path(custom_path).expanduser().resolve()
            
            # Validate path
            try:
                # Check if parent directory exists and is writable
                parent = install_path.parent
                if not parent.exists():
                    self.print_colored(f"❌ Parent directory does not exist: {parent}", Colors.FAIL)
                    continue
                
                if not os.access(parent, os.W_OK):
                    self.print_colored(f"❌ No write permission to: {parent}", Colors.FAIL)
                    continue
                
                # Check if target directory exists
                if install_path.exists():
                    self.print_colored(f"⚠️  Directory already exists: {install_path}", Colors.WARNING)
                    
                    # Show what's in the directory
                    try:
                        contents = list(install_path.iterdir())
                        if contents:
                            self.print_colored(f"   Contains {len(contents)} items", Colors.WARNING)
                            if len(contents) <= 5:
                                for item in contents[:5]:
                                    self.print_colored(f"     - {item.name}", Colors.WARNING)
                    except:
                        pass
                    
                    choice = input("   Continue? This will overwrite existing files (y/N): ").strip().lower()
                    if choice not in ('y', 'yes'):
                        continue
                
                self.install_path = install_path
                self.print_colored(f"✅ Installation path: {install_path}", Colors.OKGREEN)
                return True
                
            except Exception as e:
                self.print_colored(f"❌ Invalid path: {e}", Colors.FAIL)
                continue
    
    def create_temp_directory(self):
        """Create temporary directory for downloads"""
        try:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="canislab_install_"))
            if self.verbose:
                self.print_colored(f"📁 Temp directory: {self.temp_dir}", Colors.OKCYAN)
            return True
        except Exception as e:
            self.print_colored(f"❌ Could not create temp directory: {e}", Colors.FAIL)
            return False
    
    def download_with_progress(self, url, destination, description="file"):
        """Download file with progress indication"""
        self.print_colored(f"⬇️  Downloading {description}...", Colors.OKBLUE)
        
        try:
            def progress_hook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, (block_num * block_size * 100) // total_size)
                    bar_length = 30
                    filled_length = (percent * bar_length) // 100
                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                    
                    size_mb = total_size / (1024 * 1024)
                    downloaded_mb = min(size_mb, (block_num * block_size) / (1024 * 1024))
                    
                    print(f"\\r   [{bar}] {percent:3d}% ({downloaded_mb:.1f}/{size_mb:.1f} MB)", end='', flush=True)
            
            urllib.request.urlretrieve(url, destination, progress_hook)
            print()  # New line after progress bar
            self.print_colored(f"✅ Downloaded {description}", Colors.OKGREEN)
            return True
            
        except Exception as e:
            print()  # New line after progress bar
            self.print_colored(f"❌ Download failed: {e}", Colors.FAIL)
            return False
    
    def download_canis_lab(self):
        """Download Canis.lab from repository"""
        self.print_colored("📦 Downloading Canis.lab...", Colors.OKBLUE)
        
        repo_url = "https://github.com/crasyK/Canis.lab"
        zip_url = f"{repo_url}/archive/main.zip"
        
        zip_path = self.temp_dir / "canis-lab.zip"
        
        if not self.download_with_progress(zip_url, zip_path, "Canis.lab source code"):
            return False
        
        # Extract files
        self.print_colored("📂 Extracting files...", Colors.OKCYAN)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Extract to temp directory first
                extract_dir = self.temp_dir / "extracted"
                zip_ref.extractall(extract_dir)
                
                # Find the extracted folder (usually Canis.lab-main)
                extracted_folders = [f for f in extract_dir.iterdir() if f.is_dir()]
                
                if not extracted_folders:
                    self.print_colored("❌ No folders found in archive", Colors.FAIL)
                    return False
                
                source_dir = extracted_folders[0]
                
                # Create install directory
                self.install_path.mkdir(parents=True, exist_ok=True)
                
                # Copy contents to install path
                for item in source_dir.iterdir():
                    dest_item = self.install_path / item.name
                    
                    if item.is_dir():
                        if dest_item.exists():
                            shutil.rmtree(dest_item)
                        shutil.copytree(item, dest_item)
                    else:
                        shutil.copy2(item, dest_item)
                
                self.print_colored("✅ Files extracted successfully", Colors.OKGREEN)
                return True
                
        except Exception as e:
            self.print_colored(f"❌ Extraction failed: {e}", Colors.FAIL)
            return False
    
    def verify_installation(self):
        """Verify that key files were downloaded correctly"""
        self.print_colored("🔍 Verifying installation...", Colors.OKBLUE)
        
        required_files = ["app.py", "requirements.txt"]
        missing_files = []
        
        for file_name in required_files:
            file_path = self.install_path / file_name
            if file_path.exists():
                self.print_colored(f"   ✅ Found {file_name}", Colors.OKGREEN)
            else:
                self.print_colored(f"   ❌ Missing {file_name}", Colors.FAIL)
                missing_files.append(file_name)
        
        if missing_files:
            self.print_colored(f"❌ Installation verification failed! Missing: {missing_files}", Colors.FAIL)
            return False
        
        self.print_colored("✅ Installation verification passed!", Colors.OKGREEN)
        return True
    
    def setup_python_environment(self):
        """Set up Python environment and install dependencies"""
        self.print_colored("🐍 Setting up Python environment...", Colors.OKBLUE)
        
        # Create .env file for API key
        env_file = self.install_path / ".env"
        if not env_file.exists():
            self.print_colored("📝 Creating .env file for API configuration...", Colors.OKCYAN)
            env_content = '''# Canis.lab Configuration
# Add your OpenAI API key here:
# OPENAI_API_KEY=your_api_key_here

# Other configuration options:
# STREAMLIT_SERVER_PORT=8501
# STREAMLIT_SERVER_ADDRESS=localhost
'''
            with open(env_file, 'w') as f:
                f.write(env_content)
        
        # Install dependencies
        requirements_file = self.install_path / "requirements.txt"
        if requirements_file.exists():
            self.print_colored("📦 Installing Python dependencies...", Colors.OKCYAN)
            self.print_colored("   This may take several minutes...", Colors.WARNING)
            
            try:
                # Use pip to install requirements
                cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
                
                if self.verbose:
                    result = subprocess.run(cmd, cwd=self.install_path, check=True)
                else:
                    result = subprocess.run(cmd, cwd=self.install_path, check=True, 
                                          capture_output=True, text=True)
                
                self.print_colored("✅ Dependencies installed successfully", Colors.OKGREEN)
                return True
                
            except subprocess.CalledProcessError as e:
                self.print_colored("❌ Dependency installation failed", Colors.FAIL)
                if self.verbose and hasattr(e, 'stderr') and e.stderr:
                    self.print_colored(f"Error details: {e.stderr}", Colors.FAIL)
                return False
        else:
            self.print_colored("⚠️  No requirements.txt found, skipping dependency installation", Colors.WARNING)
            return True
    
    def create_shortcuts(self):
        """Create desktop shortcuts and start menu entries"""
        self.print_colored("🔗 Creating shortcuts...", Colors.OKBLUE)
        
        try:
            if self.is_windows:
                self.create_windows_shortcuts()
            elif self.system == "Darwin":
                self.create_macos_shortcuts()
            else:
                self.create_linux_shortcuts()
            
            return True
        except Exception as e:
            self.print_colored(f"⚠️  Could not create shortcuts: {e}", Colors.WARNING)
            return True  # Non-critical failure
    
    def create_windows_shortcuts(self):
        """Create Windows shortcuts"""
        try:
            import winshell
            from win32com.client import Dispatch
            
            desktop = winshell.desktop()
            startup_script = self.install_path / "run_canis_lab.bat"
            
            # Create batch file to run Canis.lab
            batch_content = f'''@echo off
cd /d "{self.install_path}"
python app.py
pause
'''
            with open(startup_script, 'w') as f:
                f.write(batch_content)
            
            # Create desktop shortcut
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(str(Path(desktop) / "Canis.lab.lnk"))
            shortcut.Targetpath = str(startup_script)
            shortcut.WorkingDirectory = str(self.install_path)
            shortcut.IconLocation = str(startup_script)
            shortcut.save()
            
            self.print_colored("   ✅ Desktop shortcut created", Colors.OKGREEN)
            
        except ImportError:
            # Fallback: create simple batch file
            startup_script = self.install_path / "run_canis_lab.bat"
            batch_content = f'''@echo off
echo Starting Canis.lab...
cd /d "{self.install_path}"
python app.py
pause
'''
            with open(startup_script, 'w') as f:
                f.write(batch_content)
            
            self.print_colored("   ✅ Startup script created", Colors.OKGREEN)
    
    def create_macos_shortcuts(self):
        """Create macOS shortcuts"""
        # Create shell script
        startup_script = self.install_path / "run_canis_lab.sh"
        script_content = f'''#!/bin/bash
cd "{self.install_path}"
python3 app.py
'''
        with open(startup_script, 'w') as f:
            f.write(script_content)
        
        os.chmod(startup_script, 0o755)
        self.print_colored("   ✅ Startup script created", Colors.OKGREEN)
    
    def create_linux_shortcuts(self):
        """Create Linux shortcuts"""
        # Create shell script
        startup_script = self.install_path / "run_canis_lab.sh"
        script_content = f'''#!/bin/bash
cd "{self.install_path}"
python3 app.py
'''
        with open(startup_script, 'w') as f:
            f.write(script_content)
        
        os.chmod(startup_script, 0o755)
        
        # Try to create desktop entry
        try:
            desktop_dir = Path.home() / ".local" / "share" / "applications"
            desktop_dir.mkdir(parents=True, exist_ok=True)
            
            desktop_entry = desktop_dir / "canis-lab.desktop"
            entry_content = f'''[Desktop Entry]
Version=1.0
Type=Application
Name=Canis.lab
Comment=Synthetic Dataset Generation Platform
Exec={startup_script}
Path={self.install_path}
Terminal=true
Categories=Development;
'''
            with open(desktop_entry, 'w') as f:
                f.write(entry_content)
            
            os.chmod(desktop_entry, 0o755)
            self.print_colored("   ✅ Desktop entry created", Colors.OKGREEN)
            
        except Exception:
            self.print_colored("   ✅ Startup script created", Colors.OKGREEN)
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                if self.verbose:
                    self.print_colored(f"🧹 Cleaned up temp directory: {self.temp_dir}", Colors.OKCYAN)
            except Exception as e:
                if self.verbose:
                    self.print_colored(f"⚠️  Could not clean temp directory: {e}", Colors.WARNING)
    
    def show_completion_message(self):
        """Show installation completion message"""
        completion_msg = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║                    🎉 INSTALLATION COMPLETE! 🎉              ║
║                                                              ║
║  Canis.lab has been successfully installed to:              ║
║  {str(self.install_path):<58} ║
║                                                              ║
║  🚀 To start Canis.lab:                                      ║
"""
        
        if self.is_windows:
            completion_msg += f"""║     • Double-click "run_canis_lab.bat" in the install folder  ║
║     • Or use the desktop shortcut                            ║"""
        else:
            completion_msg += f"""║     • Run "./run_canis_lab.sh" in the install folder         ║
║     • Or use the desktop entry (Linux)                      ║"""
        
        completion_msg += f"""║                                                              ║
║  ⚙️  Configuration:                                          ║
║     • Edit .env file to add your OpenAI API key             ║
║     • See README.md for detailed setup instructions         ║
║                                                              ║
║  📚 Documentation: https://github.com/crasyK/Canis.lab      ║
║  🐛 Issues: https://github.com/crasyK/Canis.lab/issues      ║
║                                                              ║
║                     Happy dataset generation! 🐕             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """
        
        self.print_colored(completion_msg, Colors.OKGREEN)
        
        # Ask if user wants to start now
        choice = input("\\n🚀 Would you like to start Canis.lab now? (y/N): ").strip().lower()
        if choice in ('y', 'yes'):
            self.launch_canis_lab()
    
    def launch_canis_lab(self):
        """Launch Canis.lab"""
        self.print_colored("🚀 Starting Canis.lab...", Colors.OKBLUE)
        
        try:
            if self.is_windows:
                startup_script = self.install_path / "run_canis_lab.bat"
                subprocess.Popen([str(startup_script)], shell=True)
            else:
                startup_script = self.install_path / "run_canis_lab.sh"
                subprocess.Popen([str(startup_script)], shell=True)
            
            self.print_colored("✅ Canis.lab is starting...", Colors.OKGREEN)
            self.print_colored("   Check your web browser for the application", Colors.OKCYAN)
            
        except Exception as e:
            self.print_colored(f"❌ Could not start Canis.lab: {e}", Colors.FAIL)
            self.print_colored(f"   Please run manually from: {self.install_path}", Colors.WARNING)
    
    def install(self):
        """Main installation process"""
        try:
            # Pre-installation checks
            if not self.check_system_requirements():
                return False
            
            if not self.check_internet():
                return False
            
            # Get installation preferences
            if not self.get_install_location():
                return False
            
            # Create temp directory
            if not self.create_temp_directory():
                return False
            
            # Download and install
            if not self.download_canis_lab():
                return False
            
            if not self.verify_installation():
                return False
            
            if not self.setup_python_environment():
                return False
            
            # Post-installation setup
            self.create_shortcuts()
            
            # Show completion
            self.show_completion_message()
            
            return True
            
        except KeyboardInterrupt:
            self.print_colored("\\n⚠️  Installation cancelled by user", Colors.WARNING)
            return False
        except Exception as e:
            self.print_colored(f"\\n❌ Installation failed: {e}", Colors.FAIL)
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Canis.lab Standalone Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Interactive installation
  %(prog)s --verbose          # Show detailed output
  %(prog)s --help             # Show this help message

For more information, visit: https://github.com/crasyK/Canis.lab
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show verbose output'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'Canis.lab Installer {__version__}'
    )
    
    args = parser.parse_args()
    
    # Create installer instance
    installer = CanislabInstaller()
    installer.verbose = args.verbose
    
    # Show header
    installer.print_header()
    
    # Run installation
    success = installer.install()
    
    if success:
        installer.print_colored("\\n🎉 Installation completed successfully!", Colors.OKGREEN)
        return 0
    else:
        installer.print_colored("\\n❌ Installation failed!", Colors.FAIL)
        installer.print_colored("   Please check the error messages above", Colors.WARNING)
        installer.print_colored("   For help, visit: https://github.com/crasyK/Canis.lab/issues", Colors.OKCYAN)
        return 1

if __name__ == "__main__":
    sys.exit(main())