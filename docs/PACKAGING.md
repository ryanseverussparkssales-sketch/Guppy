# Guppy Packaging Guide

## Quick Build (PyInstaller)

### Prerequisites
- Python 3.12+ installed
- All dependencies from requirements.txt installed
- Windows 10/11

### One-Command Build (default: one-folder)
```bash
build_executable.bat
```

Fast/automation variants:

```bash
build_executable.bat --no-clean
build_executable.bat --no-clean --ci
build_executable.bat --lean --no-clean --ci
build_executable.bat --onefile
```

This will:
1. Install PyInstaller (if needed)
2. Clean previous builds
3. Create one-folder app: `dist/Guppy/Guppy.exe` (default)
4. Launch test instance

**Expected output:** `dist/Guppy/Guppy.exe` with adjacent runtime assets.

Use `--onefile` only when extraction/startup behavior is acceptable for support and pilot rollout.

`--lean` uses `Guppy.spec` with a reduced optional dependency set for faster iteration builds.

---

## Manual Build Steps

### 1. Install PyInstaller
```bash
pip install pyinstaller
```

### 2. Create Spec File (Optional - for customization)
```bash
pyi-makespec --onefile --windowed --icon=assets/guppy.ico guppy_launcher.py
```

Edit `Guppy.spec` to add hidden imports and data files.

### 3. Build Executable
```bash
pyinstaller --onefile --windowed --name Guppy guppy_launcher.py
```

### 4. Test
```bash
dist\Guppy.exe
```

---

## Distribution Checklist

### Before Building
- [ ] Update version number in `pyproject.toml` (guppy_core is now a package under `guppy_core/`)
- [ ] Test all features in development mode
- [ ] Update README.md with current feature list
- [ ] Create CHANGELOG.md for this version
- [ ] Tag git commit: `git tag v1.0.0`

### After Building
- [ ] Test executable on clean Windows VM
- [ ] Verify file size is reasonable (<250 MB)
- [ ] Test first-run experience (no errors)
- [ ] Verify .guppy directory creation in AppData
- [ ] Test with/without internet connection
- [ ] Test voice features
- [ ] Test all tools (file ops, screenshots, etc.)

### For Release
- [ ] Create GitHub release
- [ ] Upload Guppy.exe to release assets
- [ ] Generate SHA256 checksum: `certutil -hashfile dist\Guppy.exe SHA256`
- [ ] Include checksum in release notes
- [ ] Update download link in README

---

## File Size Optimization

### Current: ~200 MB
**Breakdown:**
- PySide6: ~120 MB
- Python interpreter: ~30 MB
- Other deps: ~40 MB
- Guppy code: ~10 MB

### Reduction Strategies

#### 1. Exclude Unnecessary Qt Modules
Edit spec file:
```python
excludes = [
    'PySide6.QtBluetooth',
    'PySide6.QtDBus',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtLocation',
    'PySide6.QtMultimedia',
    'PySide6.QtNetwork',
    'PySide6.QtOpenGL',
    'PySide6.QtPositioning',
    'PySide6.QtPrintSupport',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtSensors',
    'PySide6.QtSerialPort',
    'PySide6.QtSql',
    'PySide6.QtSvg',
    'PySide6.QtTest',
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngine',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    'PySide6.QtXml',
]
```

**Savings:** ~30-50 MB

#### 2. UPX Compression
```bash
pip install pyinstaller[compression]
pyinstaller --onefile --upx-dir=C:\path\to\upx guppy_launcher.py
```

**Savings:** ~20-30% size reduction

#### 3. Separate Core and Optional Features
Create multiple executables:
- `Guppy-Lite.exe` - Core features only (~100 MB)
- `Guppy-Full.exe` - All features (~200 MB)

---

## Advanced: Inno Setup Installer

### Prerequisites
- Download Inno Setup: https://jrsoftware.org/isdl.php
- Install to default location

### Create Installer Script
File: `installer.iss`

```iss
#define MyAppName "Guppy AI Assistant"
#define MyAppVersion "1.0"
#define MyAppPublisher "Master Ryan"
#define MyAppExeName "Guppy.exe"

[Setup]
AppId={{UNIQUE-GUID-HERE}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Guppy
DefaultGroupName=Guppy AI
OutputBaseFilename=GuppySetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\guppy.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\Guppy.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Guppy AI"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Guppy AI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Guppy AI"; Flags: postinstall nowait skipifsilent
```

### Compile Installer
```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

**Output:** `Output\GuppySetup.exe` (~205 MB installer)

---

## Code Signing (Optional but Recommended)

### Why Sign?
- Eliminates Windows SmartScreen warnings
- Builds user trust
- Professional appearance

### Get Certificate
1. Purchase from DigiCert, Sectigo, or similar ($200-400/year)
2. Download certificate (.pfx file)
3. Store securely (NOT in git repo)

### Sign Executable
```bash
signtool sign /f certificate.pfx /p PASSWORD /t http://timestamp.digicert.com /d "Guppy AI" dist\Guppy.exe
```

---

## CI/CD: GitHub Actions (Automated Builds)

### File: `.github/workflows/build.yml`

```yaml
name: Build Guppy Executable

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller
    
    - name: Build executable
      run: |
        pyinstaller --onefile --windowed --name Guppy guppy_launcher.py
    
    - name: Upload artifact
      uses: actions/upload-artifact@v3
      with:
        name: Guppy-${{ github.ref_name }}
        path: dist/Guppy.exe
    
    - name: Create Release
      uses: softprops/action-gh-release@v1
      with:
        files: dist/Guppy.exe
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Usage:**
```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub automatically builds and releases executable.

---

## Troubleshooting Builds

### Error: "Module not found"
**Solution:** Add to hidden imports in build script
```bash
--hidden-import=missing_module_name
```

### Error: "Failed to execute script"
**Solution:** Run without --windowed flag to see error messages
```bash
pyinstaller --onefile guppy_launcher.py
dist\Guppy.exe  # Run in terminal to see errors
```

### Executable won't start
**Solution:** Check for missing data files
```bash
--add-data "missing_file.json;."
```

### Antivirus blocks executable
**Solution:** 
1. Code sign the executable
2. Submit to antivirus vendors for whitelisting
3. Use cx_Freeze instead (fewer false positives)

---

## Distribution Best Practices

1. **Version numbering:** Follow semantic versioning (1.0.0, 1.0.1, 1.1.0)
2. **Changelog:** Document changes between versions
3. **SHA256 checksums:** Include in release notes
4. **Testing:** Always test on clean VM before release
5. **Rollback plan:** Keep previous version available
6. **User data:** Never break compatibility with user's .guppy directory

---

## Next Steps

Choose your packaging strategy:

**Quick & Dirty (Today):**
Run `build_executable.bat` → Share dist/Guppy.exe

**Professional (This Week):**
Create Inno Setup installer → Distribute GuppySetup.exe

**Long-term (Next Month):**
Set up GitHub Actions → Automated releases on git tags

---

For questions or issues, create GitHub issue or contact Master Ryan.
