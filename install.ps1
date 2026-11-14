<#
.SYNOPSIS
    OrbitCode Universal Installer for Windows (PowerShell)

.DESCRIPTION
    Installs OrbitCode AI coding agent on Windows with all dependencies.
    Works on Windows 10/11 with PowerShell 5.1+ or PowerShell 7+.

.USAGE
    # Run in PowerShell (Admin not required):
    irm https://raw.githubusercontent.com/OrbitOmen/orbitcode/main/install.ps1 | iex

    # Or download and run:
    wget https://raw.githubusercontent.com/OrbitOmen/orbitcode/main/install.ps1 -OutFile install.ps1
    .\install.ps1

.NOTES
    Requires: Windows 10/11, Python 3.11+ (will install if missing)
    Installs to: %USERPROFILE%\.orbitcode\venv
    Adds to PATH: %USERPROFILE%\.orbitcode\venv\Scripts
#>

# Prevent running in restricted mode
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-Error "PowerShell 5.1+ required. Current: $($PSVersionTable.PSVersion)"
    exit 1
}

# Colors
$Red = [ConsoleColor]::Red
$Green = [ConsoleColor]::Green
$Yellow = [ConsoleColor]::Yellow
$Blue = [ConsoleColor]::Cyan
$Cyan = [ConsoleColor]::Cyan
$Bold = "Bold"
$Reset = [ConsoleColor]::Gray

function Write-Banner {
    Write-Host @"
╔═══════════════════════════════════════════════════════════════╗
║  ██████╗ ███████╗██████╗ ██████╗ ███████╗███████╗██╗  ██╗     ║
║  ██╔══██╗██═════╝██══██╗██══██╗██════╝██═════╝██║  ██║     ║
║  ██████╔╝█████╗  ██████╔╝██████╔╝█████╗  ███████╗███████║     ║
║  ██═══╝ ██═══╝  ██══██╗██══██╗██═══╝  ╚════██║██══██║     ║
║  ██║     ███████╗██║  ██║██║  ██║███████╗███████║██║  ██║     ║
║  ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝     ║
║                                                              ║
║   AI Coding Agent  •  Model Failover  •  MCP  •  Plugins    ║
║   Made by OrbitOmen                                          ║
╚═══════════════════════════════════════════════════════════════╝
"@ -ForegroundColor $Cyan
}

function Write-Log {
    param([string]$Level, [string]$Message, [ConsoleColor]$Color = $Reset)
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $Color
}

function Write-Info { param([string]$Msg) Write-Log "INFO" $Msg $Blue }
function Write-Success { param([string]$Msg) Write-Log "SUCCESS" $Msg $Green }
function Write-Warn { param([string]$Msg) Write-Log "WARN" $Msg $Yellow }
function Write-Error { param([string]$Msg) Write-Log "ERROR" $Msg $Red }
function Write-Step { param([string]$Msg) Write-Log "STEP" $Msg $Cyan }

# Check if running as admin (not required but nice to know)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Banner
Write-Info "Starting OrbitCode installation for Windows..."
Write-Info "Admin rights: $isAdmin"
Write-Host ""

# Configuration
$REPO = "OrbitOmen/orbitcode"
$INSTALL_DIR = "$env:USERPROFILE\.orbitcode"
$VENV_DIR = "$INSTALL_DIR\venv"
$VENV_SCRIPTS = "$VENV_DIR\Scripts"
$GITHUB_RAW = "https://raw.githubusercontent.com/$REPO/main"

# Check Python
Write-Step "Checking Python installation..."

$pythonCmd = $null
$pythonVersion = $null

# Try python3 first, then python
foreach ($cmd in @("python3", "python", "py -3")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -match '^(\d+)\.(\d+)$') {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            if ($major -eq 3 -and $minor -ge 11) {
                $pythonCmd = $cmd
                $pythonVersion = $ver
                break
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Warn "Python 3.11+ not found. Installing via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.11 --source winget --accept-source-agreements --accept-package-agreements
        # Re-check
        foreach ($cmd in @("python3", "python", "py -3")) {
            try {
                $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($ver -match '^(\d+)\.(\d+)$') {
                    $major = [int]$matches[1]
                    $minor = [int]$matches[2]
                    if ($major -eq 3 -and $minor -ge 11) {
                        $pythonCmd = $cmd
                        $pythonVersion = $ver
                        break
                    }
                }
            } catch { }
        }
    } else {
        Write-Error "winget not available. Please install Python 3.11+ from https://python.org"
        exit 1
    }
}

if (-not $pythonCmd) {
    Write-Error "Failed to install or find Python 3.11+"
    exit 1
}

Write-Success "Found Python $pythonVersion via '$pythonCmd'"

# Check/Install pip
Write-Step "Checking pip..."
try {
    & $pythonCmd -m pip --version 2>$null | Out-Null
    Write-Success "pip available"
} catch {
    Write-Warn "Installing pip..."
    & $pythonCmd -m ensurepip --upgrade
    Write-Success "pip installed"
}

# Create virtual environment
Write-Step "Creating virtual environment at $VENV_DIR..."
if (Test-Path $VENV_DIR) {
    Write-Info "Virtual environment already exists"
} else {
    & $pythonCmd -m venv $VENV_DIR
    Write-Success "Virtual environment created"
}

# Activate venv and upgrade pip
Write-Step "Upgrading pip and setuptools..."
& "$VENV_SCRIPTS\python.exe" -m pip install --upgrade pip setuptools wheel -q
Write-Success "pip upgraded"

# Install OrbitCode
Write-Step "Installing OrbitCode..."

# Try PyPI first
try {
    & "$VENV_SCRIPTS\pip.exe" install orbitcode -q
    Write-Success "Installed from PyPI"
} catch {
    Write-Info "Installing from GitHub (development version)..."

    # Create temp directory
    $tmpDir = [System.IO.Path]::GetTempPath() + "orbitcode-install-" + [Guid]::NewGuid().ToString("N").Substring(0,8)
    New-Item -ItemType Directory -Path $tmpDir | Out-Null
    Set-Location $tmpDir

    # Clone or download
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Info "Cloning repository..."
        git clone --depth 1 "https://github.com/$REPO.git" 2>$null
        if (-not $?) { Write-Error "Git clone failed"; exit 1 }
        Set-Location "$tmpDir\orbitcode"
    } else {
        Write-Info "Downloading repository zip..."
        $zipUrl = "https://github.com/$REPO/archive/refs/heads/main.zip"
        $zipPath = "$tmpDir\orbitcode.zip"
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $tmpDir -Force
        Set-Location "$tmpDir\orbitcode-main"
    }

    # Install with all optional dependencies
    Write-Info "Installing package with dev, browser, web extras..."
    & "$VENV_SCRIPTS\pip.exe" install -e ".[dev,browser,web]" -q

    # Install Playwright Chromium
    Write-Info "Installing Playwright Chromium..."
    & "$VENV_SCRIPTS\playwright.exe" install chromium 2>$null
    if (-not $?) { Write-Warn "Playwright install failed. Run '$VENV_SCRIPTS\playwright.exe install chromium' manually later." }

    # Cleanup
    Set-Location $env:USERPROFILE
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue

    Write-Success "Installed from GitHub"
}

# Add to PATH
Write-Step "Configuring PATH..."

$pathToAdd = "$VENV_SCRIPTS"
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ($currentPath -notlike "*$pathToAdd*") {
    $newPath = $currentPath + ";" + $pathToAdd
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Success "Added $pathToAdd to user PATH"
    Write-Warn "Restart your terminal or run: \$env:PATH += ';$pathToAdd'"
} else {
    Write-Info "Already in PATH"
}

# Also add to current session
$env:PATH += ";$pathToAdd"

# Verify installation
Write-Step "Verifying installation..."
if (Get-Command orbitcode -ErrorAction SilentlyContinue) {
    Write-Success "OrbitCode installed successfully!"
} elseif (Get-Command ocode -ErrorAction SilentlyContinue) {
    Write-Success "OrbitCode installed successfully! (as 'ocode')"
} else {
    Write-Warn "Commands not found in current session. Restart terminal or run:"
    Write-Host "  \$env:PATH += ';$pathToAdd'" -ForegroundColor $Cyan
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host "                    INSTALLATION COMPLETE" -ForegroundColor $Green -Bold
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Cyan
Write-Host ""
Write-Host "Quick Start:" -ForegroundColor $Cyan
Write-Host "  orbitcode           # Start interactive mode" -ForegroundColor $Green
Write-Host "  orbitcode --setup   # Run setup wizard" -ForegroundColor $Green
Write-Host "  orbitcode --help    # Show all commands" -ForegroundColor $Green
Write-Host "  ocode               # Short alias" -ForegroundColor $Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor $Cyan
Write-Host "  Set your OpenRouter API key: \$env:OPENROUTER_API_KEY = 'your_key'" -ForegroundColor $Yellow
Write-Host "  Or run 'orbitcode --setup' to configure interactively" -ForegroundColor $Yellow
Write-Host ""
Write-Host "Graphify Knowledge Graph:" -ForegroundColor $Cyan
Write-Host "  View at: /workspaces/codespaces-blank/graphify-out/graph.html" -ForegroundColor $Yellow
Write-Host ""
Write-Host "Note: Restart your PowerShell/terminal for PATH changes to take effect." -ForegroundColor $Yellow
Write-Host ""