#!/usr/bin/env bash
# OrbitCode Universal Installer - Works on Linux, macOS, and Windows (via WSL/Git Bash)
# Usage: curl -fsSL https://raw.githubusercontent.com/orbit-omen/orbitcode/main/install.sh | bash
#        or: wget -qO- https://raw.githubusercontent.com/orbit-omen/orbitcode/main/install.sh | bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
REPO="orbit-omen/orbitcode"
INSTALL_DIR="${HOME}/.local/bin"
GITHUB_RAW="https://raw.githubusercontent.com/${REPO}/main"
VERSION="${VERSION:-latest}"

# Print banner
print_banner() {
    echo -e "${CYAN}${BOLD}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║  ██████╗ ███████╗██████╗ ██████╗ ███████╗███████╗██╗  ██╗     ║
║  ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██════╝██║  ██║     ║
║  ██████╔╝█████╗  ██████╔╝██████╔╝█████╗  ███████╗███████║     ║
║  ██═══╝ ██══╝  ██══██╗██══██╗██═══╝  ╚════██║██══██║     ║
║  ██║     ███████╗██║  ██║██║  ██║███████╗███████║██║  ██║     ║
║  ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝     ║
║                                                              ║
║   AI Coding Agent  •  Model Failover  •  MCP  •  Plugins    ║
║   Made by orbit-omen                                          ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${CYAN}${BOLD}[STEP]${NC} $*"; }

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS="linux" ;;
        Darwin*)    OS="macos" ;;
        CYGWIN*|MINGW*|MSYS*) OS="windows" ;;
        *)          OS="unknown" ;;
    esac
    ARCH=$(uname -m)
    log_info "Detected OS: $OS, Architecture: $ARCH"
}

# Check Python version
check_python() {
    log_step "Checking Python installation..."

    if ! command -v python3 &> /dev/null; then
        if ! command -v python &> /dev/null; then
            log_error "Python 3.11+ not found. Please install Python first."
            case "$OS" in
                linux)
                    echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip python3-venv"
                    echo "  Fedora: sudo dnf install python3 python3-pip"
                    echo "  Arch: sudo pacman -S python python-pip"
                    ;;
                macos)
                    echo "  brew install python@3.11"
                    echo "  Or download from https://python.org"
                    ;;
                windows)
                    echo "  Install from Microsoft Store or https://python.org"
                    echo "  Or use winget: winget install Python.Python.3.11"
                    ;;
            esac
            exit 1
        fi
        PYTHON_CMD="python"
    else
        PYTHON_CMD="python3"
    fi

    # Check version
    PY_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
        log_error "Python 3.11+ required, found $PY_VERSION"
        exit 1
    fi

    log_success "Python $PY_VERSION found"
}

# Check pip
check_pip() {
    log_step "Checking pip..."
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        log_warn "pip not found, installing..."
        $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || {
            case "$OS" in
                linux)
                    curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD
                    ;;
                macos)
                    $PYTHON_CMD -m ensurepip --upgrade
                    ;;
                windows)
                    $PYTHON_CMD -m ensurepip --upgrade
                    ;;
            esac
        }
    fi
    log_success "pip available"
}

# Install system dependencies
install_system_deps() {
    log_step "Installing system dependencies..."

    case "$OS" in
        linux)
            # Detect package manager
            if command -v apt &> /dev/null; then
                log_info "Detected apt (Debian/Ubuntu)..."
                sudo apt update -qq
                sudo apt install -y -qq python3-venv python3-dev build-essential git curl wget 2>/dev/null || true
            elif command -v dnf &> /dev/null; then
                log_info "Detected dnf (Fedora)..."
                sudo dnf install -y python3-devel gcc git curl wget 2>/dev/null || true
            elif command -v pacman &> /dev/null; then
                log_info "Detected pacman (Arch)..."
                sudo pacman -S --needed --noconfirm python python-pip base-devel git curl wget 2>/dev/null || true
            elif command -v zypper &> /dev/null; then
                log_info "Detected zypper (openSUSE)..."
                sudo zypper install -y python3-devel gcc git curl wget 2>/dev/null || true
            elif command -v apk &> /dev/null; then
                log_info "Detected apk (Alpine)..."
                sudo apk add python3-dev gcc musl-dev git curl wget 2>/dev/null || true
            else
                log_warn "Unknown package manager. Please ensure python3-dev, build-essential, git are installed."
            fi
            ;;
        macos)
            if command -v brew &> /dev/null; then
                log_info "Homebrew found, installing dependencies..."
                brew install python@3.11 git curl wget 2>/dev/null || true
            else
                log_warn "Homebrew not found. Install from https://brew.sh for easier dependency management."
            fi
            # Install Xcode command line tools if needed
            xcode-select --install 2>/dev/null || true
            ;;
        windows)
            log_info "Windows detected. Using Python's built-in tools."
            # On Windows, we rely on Python's built-in pip
            ;;
    esac
}

# Create virtual environment
create_venv() {
    log_step "Creating virtual environment..."
    VENV_DIR="${HOME}/.orbitcode/venv"

    if [ -d "$VENV_DIR" ]; then
        log_info "Virtual environment already exists at $VENV_DIR"
    else
        $PYTHON_CMD -m venv "$VENV_DIR"
        log_success "Virtual environment created at $VENV_DIR"
    fi

    # Activate venv
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    pip install --upgrade pip setuptools wheel -q
}

# Install OrbitCode
install_orbitcode() {
    log_step "Installing OrbitCode..."

    # Try to install from PyPI first (if published), otherwise from GitHub
    if pip install orbitcode 2>/dev/null; then
        log_success "Installed from PyPI"
    else
        log_info "Installing from GitHub (development version)..."

        # Create temp directory
        TMP_DIR=$(mktemp -d)
        cd "$TMP_DIR"

        # Clone or download
        if command -v git &> /dev/null; then
            git clone --depth 1 "https://github.com/${REPO}.git" 2>/dev/null || {
                log_error "Failed to clone repository"
                exit 1
            }
            cd orbitcode
        else
            # Download zip if no git
            curl -fsSL "https://github.com/${REPO}/archive/refs/heads/main.zip" -o orbitcode.zip
            unzip -q orbitcode.zip
            cd orbitcode-main
        fi

        # Install with all optional dependencies
        pip install -e ".[dev,browser,web]" -q

        # Install playwright chromium
        log_info "Installing Playwright Chromium..."
        playwright install chromium 2>/dev/null || log_warn "Playwright install failed, you may need to run 'playwright install chromium' manually"

        # Cleanup
        cd /
        rm -rf "$TMP_DIR"

        log_success "Installed from GitHub"
    fi
}

# Add to PATH
setup_path() {
    log_step "Setting up PATH..."

    # Determine shell config file
    SHELL_CONFIG=""
    case "$SHELL" in
        */zsh)   SHELL_CONFIG="${HOME}/.zshrc" ;;
        */bash)  SHELL_CONFIG="${HOME}/.bashrc" ;;
        */fish)  SHELL_CONFIG="${HOME}/.config/fish/config.fish" ;;
        *)       SHELL_CONFIG="${HOME}/.profile" ;;
    esac

    # Add ~/.local/bin to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_CONFIG"
        log_info "Added ~/.local/bin to PATH in $SHELL_CONFIG"
    fi

    # Also add venv bin to PATH for orbitcode command
    VENV_BIN="${HOME}/.orbitcode/venv/bin"
    if [[ ":$PATH:" != *":$VENV_BIN:"* ]]; then
        echo "export PATH=\"$VENV_BIN:\$PATH\"" >> "$SHELL_CONFIG"
        log_info "Added OrbitCode venv to PATH in $SHELL_CONFIG"
    fi

    # Export for current session
    export PATH="$VENV_BIN:$HOME/.local/bin:$PATH"
}

# Verify installation
verify_install() {
    log_step "Verifying installation..."

    if command -v orbitcode &> /dev/null || command -v ocode &> /dev/null; then
        log_success "OrbitCode installed successfully!"
        echo ""
        echo -e "${CYAN}${BOLD}Quick Start:${NC}"
        echo -e "  ${GREEN}orbitcode${NC}           # Start interactive mode"
        echo -e "  ${GREEN}orbitcode --setup${NC}   # Run setup wizard"
        echo -e "  ${GREEN}orbitcode --help${NC}    # Show all commands"
        echo -e "  ${GREEN}ocode${NC}               # Short alias"
        echo ""
        echo -e "${YELLOW}Note:${NC} Restart your shell or run: ${BOLD}source $SHELL_CONFIG${NC}"
        echo ""
        echo -e "${BLUE}Configuration:${NC}"
        echo -e "  Set your OpenRouter API key: ${BOLD}export OPENROUTER_API_KEY=your_key${NC}"
        echo -e "  Or run ${BOLD}orbitcode --setup${NC} to configure interactively"
        echo ""
        echo -e "${BLUE}Graphify Knowledge Graph:${NC}"
        echo -e "  View at: ${BOLD}/workspaces/codespaces-blank/graphify-out/graph.html${NC}"
        echo ""
    else
        log_error "Installation verification failed. Try restarting your shell."
        exit 1
    fi
}

# Main installation flow
main() {
    print_banner
    log_info "Starting OrbitCode installation..."
    echo ""

    detect_os
    check_python
    check_pip
    install_system_deps
    create_venv
    install_orbitcode
    setup_path
    verify_install

    log_success "Installation complete! 🎉"
}

# Run main
main "$@"