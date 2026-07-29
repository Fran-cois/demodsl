#!/bin/sh
# Usage: curl -fsSL https://raw.githubusercontent.com/Fran-cois/demodsl/main/dist/install.sh | sh
# Or:    wget -qO- https://raw.githubusercontent.com/Fran-cois/demodsl/main/dist/install.sh | sh
set -e

REPO="Fran-cois/demodsl"
INSTALL_DIR="${DEMODSL_INSTALL_DIR:-/usr/local/bin}"

# ---------- helpers ----------
info()  { printf "\033[1;34m==>\033[0m %s\n" "$1"; }
error() { printf "\033[1;31mERROR:\033[0m %s\n" "$1" >&2; exit 1; }

detect_os() {
  case "$(uname -s)" in
    Linux*)  echo "linux" ;;
    Darwin*) echo "macos" ;;
    MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
    *) error "Unsupported OS: $(uname -s)" ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64)  echo "x86_64" ;;
    aarch64|arm64) echo "aarch64" ;;
    *) error "Unsupported architecture: $(uname -m)" ;;
  esac
}

# ---------- main ----------
OS=$(detect_os)
ARCH=$(detect_arch)
TAG="${DEMODSL_VERSION:-latest}"

info "Detecting platform: ${OS}/${ARCH}"

# Resolve latest version tag
if [ "$TAG" = "latest" ]; then
  TAG=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
    | grep '"tag_name"' | head -1 | sed 's/.*"v\(.*\)".*/\1/')
  [ -z "$TAG" ] && error "Could not fetch latest release version"
fi

info "Installing demodsl v${TAG}"

ASSET="demodsl-${TAG}-${OS}-${ARCH}"
case "$OS" in
  windows) ASSET="${ASSET}.zip" ;;
  *)       ASSET="${ASSET}.tar.gz" ;;
esac

URL="https://github.com/${REPO}/releases/download/v${TAG}/${ASSET}"
info "Downloading ${URL}"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

curl -fsSL "$URL" -o "${TMPDIR}/${ASSET}"

case "$ASSET" in
  *.tar.gz) tar -xzf "${TMPDIR}/${ASSET}" -C "$TMPDIR" ;;
  *.zip)    unzip -q "${TMPDIR}/${ASSET}" -d "$TMPDIR" ;;
esac

# Install binary
if [ -w "$INSTALL_DIR" ]; then
  cp "${TMPDIR}/demodsl" "${INSTALL_DIR}/demodsl"
else
  info "Need sudo to install to ${INSTALL_DIR}"
  sudo cp "${TMPDIR}/demodsl" "${INSTALL_DIR}/demodsl"
fi
chmod +x "${INSTALL_DIR}/demodsl"

info "Installed demodsl to ${INSTALL_DIR}/demodsl"
info "Run 'demodsl --help' to get started"
