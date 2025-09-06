#!/usr/bin/env python3
"""
🔨 Canis.lab Installer Builder
=============================
Converts the Python installer into a standalone executable
that users can double-click without having Python installed.
"""

import subprocess
import sys
import platform
import shutil
from pathlib import Path

def install_pyinstaller():
    """Install PyInstaller if not available"""
    print("📦 Installing PyInstaller...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("✅ PyInstaller installed!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install PyInstaller")
        return False

def create_installer_spec():
    """Create PyInstaller spec file for customization"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['canis_lab_installer.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['urllib.request', 'urllib.error', 'zipfile', 'tempfile', 'webbrowser'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CanisLab_Installer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if Path('icon.ico').exists() else None,
)
'''
    
    with open('installer.spec', 'w') as f:
        f.write(spec_content)
    
    print("✅ Created installer.spec")

def build_executable():
    """Build the standalone executable"""
    system = platform.system().lower()
    
    print(f"🔨 Building executable for {system}...")
    print("⏳ This may take several minutes...")
    
    try:
        # Build using PyInstaller
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",  # Single executable file
            "--console",  # Keep console window
            "--name", "CanisLab_Installer",
            "--distpath", "release",
            "--workpath", "build_temp",
            "--specpath", "build_temp"
        ]
        
        # Add icon if available
        if Path('icon.ico').exists():
            cmd.extend(["--icon", "icon.ico"])
        
        # Add the main script
        cmd.append("canis_lab_installer.py")
        
        subprocess.run(cmd, check=True)
        
        print("✅ Executable built successfully!")
        
        # Show output location
        if system == "windows":
            exe_name = "CanisLab_Installer.exe"
        else:
            exe_name = "CanisLab_Installer"
        
        exe_path = Path("release") / exe_name
        if exe_path.exists():
            file_size = exe_path.stat().st_size / (1024*1024)  # MB
            print(f"📁 Executable: {exe_path} ({file_size:.1f} MB)")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        return False

def create_release_package():
    """Create a release package with the executable"""
    print("📦 Creating release package...")
    
    system = platform.system().lower()
    release_dir = Path("release")
    
    if system == "windows":
        exe_name = "CanisLab_Installer.exe"
        readme_name = "README_Windows.txt"
        readme_content = """🧬 Canis.lab Installer for Windows

QUICK START:
1. Double-click CanisLab_Installer.exe
2. Follow the on-screen instructions
3. The installer will download and set up everything automatically!

REQUIREMENTS:
- Windows 10 or newer
- Internet connection
- About 500MB free disk space

WHAT IT DOES:
✅ Downloads Canis.lab automatically
✅ Installs all required components
✅ Sets up your environment
✅ Launches the application

Need help? Visit: https://github.com/your-repo/canis-lab

Enjoy creating synthetic datasets! 🚀
"""
    
    elif system == "darwin":  # macOS
        exe_name = "CanisLab_Installer"
        readme_name = "README_Mac.txt"
        readme_content = """🧬 Canis.lab Installer for macOS

QUICK START:
1. Double-click CanisLab_Installer
2. If blocked by security, go to System Preferences > Security & Privacy
3. Click "Open Anyway" 
4. Follow the on-screen instructions

REQUIREMENTS:
- macOS 10.14 or newer
- Internet connection
- About 500MB free disk space

WHAT IT DOES:
✅ Downloads Canis.lab automatically
✅ Installs all required components
✅ Sets up your environment
✅ Launches the application

Need help? Visit: https://github.com/your-repo/canis-lab

Enjoy creating synthetic datasets! 🚀
"""
    
    else:  # Linux
        exe_name = "CanisLab_Installer"
        readme_name = "README_Linux.txt"
        readme_content = """🧬 Canis.lab Installer for Linux

QUICK START:
1. Make executable: chmod +x CanisLab_Installer
2. Run: ./CanisLab_Installer
3. Follow the on-screen instructions

OR just double-click if your file manager supports it.

REQUIREMENTS:
- Linux (Ubuntu 18.04+, CentOS 7+, or similar)
- Internet connection
- About 500MB free disk space
- Python 3.8+ (usually pre-installed)

WHAT IT DOES:
✅ Downloads Canis.lab automatically
✅ Installs all required components
✅ Sets up your environment
✅ Launches the application

Need help? Visit: https://github.com/your-repo/canis-lab

Enjoy creating synthetic datasets! 🚀
"""
    
    # Write README
    with open(release_dir / readme_name, 'w') as f:
        f.write(readme_content)
    
    print(f"✅ Release package ready in 'release/' folder")
    print(f"📁 Files: {exe_name}, {readme_name}")

def main():
    """Main build process"""
    print("🔨 Canis.lab Executable Builder")
    print("===============================")
    
    # Check if installer source exists
    if not Path("canis_lab_installer.py").exists():
        print("❌ canis_lab_installer.py not found")
        print("   Please make sure the installer script is in the current directory")
        return
    
    # Install PyInstaller
    if not install_pyinstaller():
        return
    
    # Build executable
    if not build_executable():
        return
    
    # Create release package
    create_release_package()
    
    print("\n🎉 SUCCESS!")
    print("Your standalone installer is ready!")
    print("Users can now double-click to install Canis.lab without Python!")

if __name__ == "__main__":
    main()
