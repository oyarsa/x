#!/usr/bin/env bash
# Bootstrap script for Nix-based VM provisioning on Ubuntu 24.04
# This script installs Nix, enables flakes, and applies the home-manager configuration.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Ubuntu
check_os() {
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot determine OS. /etc/os-release not found."
        exit 1
    fi

    source /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
        log_warn "This script is designed for Ubuntu. Detected: $ID"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    log_info "Detected OS: $PRETTY_NAME"
}

# Install Nix using the Determinate Systems installer (recommended for multi-user)
install_nix() {
    if command -v nix &> /dev/null; then
        log_info "Nix is already installed: $(nix --version)"
        return 0
    fi

    log_info "Installing Nix using Determinate Systems installer..."
    curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --no-confirm

    # Source nix in current shell
    if [[ -f /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]]; then
        source /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    fi

    log_success "Nix installed successfully"
}

# Configure Nix for flakes (should already be enabled by Determinate installer)
configure_nix() {
    log_info "Verifying Nix flakes support..."

    # The Determinate installer enables flakes by default
    # But let's verify and add user config if needed
    mkdir -p ~/.config/nix
    if [[ ! -f ~/.config/nix/nix.conf ]] || ! grep -q "experimental-features" ~/.config/nix/nix.conf; then
        echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
        log_info "Added flakes configuration to ~/.config/nix/nix.conf"
    fi

    log_success "Nix flakes enabled"
}

# Install home-manager
install_home_manager() {
    log_info "Installing home-manager..."

    # Add home-manager channel
    nix-channel --add https://github.com/nix-community/home-manager/archive/master.tar.gz home-manager
    nix-channel --update

    log_success "Home-manager channel added"
}

# Get the directory where this script is located
get_script_dir() {
    local SOURCE="${BASH_SOURCE[0]}"
    while [[ -h "$SOURCE" ]]; do
        local DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
        SOURCE="$(readlink "$SOURCE")"
        [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
    done
    echo "$(cd -P "$(dirname "$SOURCE")" && pwd)"
}

# Apply home-manager configuration
apply_config() {
    local SCRIPT_DIR
    SCRIPT_DIR="$(get_script_dir)"

    log_info "Applying home-manager configuration from $SCRIPT_DIR..."

    # Get the username
    local USERNAME="${USER:-$(whoami)}"

    # Check if flake.nix exists
    if [[ ! -f "$SCRIPT_DIR/flake.nix" ]]; then
        log_error "flake.nix not found in $SCRIPT_DIR"
        exit 1
    fi

    # Build and switch to the new configuration
    # Use --impure to allow reading environment variables for customization
    nix run home-manager/master -- switch --flake "$SCRIPT_DIR#dev" --impure

    log_success "Configuration applied successfully"
}

# Note: Rust, Playwright, and Claude Code are now managed by Nix/home-manager
# - Rust: rustc, cargo, clippy, rustfmt from nixpkgs
# - Playwright: playwright-driver.browsers with PLAYWRIGHT_BROWSERS_PATH
# - Claude Code: installed via home.activation.installClaude

# Set fish as default shell
set_default_shell() {
    local FISH_PATH
    FISH_PATH="$(which fish 2>/dev/null || echo "")"

    if [[ -z "$FISH_PATH" ]]; then
        # Fish should be in the nix profile
        FISH_PATH="$HOME/.nix-profile/bin/fish"
    fi

    if [[ -x "$FISH_PATH" ]]; then
        # Add to /etc/shells if not present (requires sudo)
        if ! grep -q "$FISH_PATH" /etc/shells 2>/dev/null; then
            log_info "Adding fish to /etc/shells (requires sudo)..."
            echo "$FISH_PATH" | sudo tee -a /etc/shells > /dev/null
        fi

        # Change default shell
        if [[ "$SHELL" != "$FISH_PATH" ]]; then
            log_info "Setting fish as default shell..."
            chsh -s "$FISH_PATH" || log_warn "Could not change default shell. Run: chsh -s $FISH_PATH"
        fi

        log_success "Fish shell configured"
    else
        log_warn "Fish not found at expected location"
    fi
}

# Print post-installation instructions
print_instructions() {
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  Nix VM Provisioning Complete!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Log out and log back in (or run 'exec fish')"
    echo "  2. Verify installation: nix --version && home-manager --version"
    echo ""
    echo "To update your configuration:"
    echo "  cd $(get_script_dir)"
    echo "  home-manager switch --flake .#dev"
    echo ""
    echo "To customize:"
    echo "  - Edit flake.nix to change user details"
    echo "  - Edit modules/*.nix to modify packages/config"
    echo "  - Run 'home-manager switch --flake .#dev' to apply changes"
    echo ""
}

# Main installation flow
main() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Nix VM Provisioning for Ubuntu 24.04${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""

    check_os
    install_nix
    configure_nix
    install_home_manager
    apply_config
    set_default_shell
    print_instructions
}

# Allow running individual steps for debugging
case "${1:-}" in
    --check-os)
        check_os
        ;;
    --install-nix)
        install_nix
        ;;
    --configure-nix)
        configure_nix
        ;;
    --install-hm)
        install_home_manager
        ;;
    --apply)
        apply_config
        ;;
    --shell)
        set_default_shell
        ;;
    --help|-h)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  (no args)       Run full installation"
        echo "  --check-os      Check OS compatibility"
        echo "  --install-nix   Install Nix package manager"
        echo "  --configure-nix Configure Nix for flakes"
        echo "  --install-hm    Install home-manager"
        echo "  --apply         Apply home-manager configuration"
        echo "  --shell         Set fish as default shell"
        echo "  --help, -h      Show this help"
        ;;
    "")
        main
        ;;
    *)
        log_error "Unknown option: $1"
        exit 1
        ;;
esac
