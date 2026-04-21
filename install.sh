#!/bin/bash
# PhotoBackup Verifier — one-command installer for macOS
# Run with:  bash install.sh

set -e

BLUE='\033[0;34m'; GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${BLUE}▶ $1${NC}"; }
success() { echo -e "${GREEN}✓ $1${NC}"; }
error()   { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo ""
echo "  PhotoBackup Verifier — Installer"
echo "  ================================"
echo ""

# ── 1. macOS only ──────────────────────────────────────────────────────────
[[ "$(uname)" == "Darwin" ]] || error "This app requires macOS."

# ── 2. Homebrew ────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
  info "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add brew to PATH for Apple Silicon and Intel
  [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
  [[ -f /usr/local/bin/brew   ]] && eval "$(/usr/local/bin/brew shellenv)"
else
  success "Homebrew already installed"
fi

# ── 3. Python 3.13 ─────────────────────────────────────────────────────────
if ! brew list python@3.13 &>/dev/null; then
  info "Installing Python 3.13..."
  brew install python@3.13
else
  success "Python 3.13 already installed"
fi

# ── 4. Tkinter for Python 3.13 ─────────────────────────────────────────────
if ! brew list python-tk@3.13 &>/dev/null; then
  info "Installing tkinter for Python 3.13..."
  brew install python-tk@3.13
else
  success "python-tk@3.13 already installed"
fi

# Find the right python binary
PYTHON=""
for candidate in "/opt/homebrew/bin/python3.13" "/usr/local/bin/python3.13"; do
  [[ -x "$candidate" ]] && PYTHON="$candidate" && break
done
[[ -z "$PYTHON" ]] && error "Python 3.13 not found after install. Please restart your terminal and run again."

# Quick tkinter sanity check
"$PYTHON" -c "import tkinter" 2>/dev/null || error "tkinter import failed. Run: brew reinstall python-tk@3.13"
success "Python + tkinter OK ($(\"$PYTHON\" --version))"

# ── 5. Build the .app bundle ───────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DEST="$HOME/Desktop/PhotoVerifier.app"

info "Building PhotoVerifier.app..."

# Remove old copy if present
rm -rf "$APP_DEST"

mkdir -p "$APP_DEST/Contents/MacOS"
mkdir -p "$APP_DEST/Contents/Resources"

# Copy the Python script
cp "$SCRIPT_DIR/photoverifier.py" "$APP_DEST/Contents/Resources/photoverifier.py"

# Write the launcher
cat > "$APP_DEST/Contents/MacOS/PhotoVerifier" <<LAUNCHER
#!/bin/bash
DIR="\$(cd "\$(dirname "\$0")" && pwd)"
SCRIPT="\$DIR/../Resources/photoverifier.py"
PYTHON=""
for candidate in \\
    "/opt/homebrew/bin/python3.13" \\
    "/opt/homebrew/bin/python3.12" \\
    "/opt/homebrew/bin/python3"    \\
    "/usr/local/bin/python3.13"    \\
    "/usr/local/bin/python3"
do
    if [ -x "\$candidate" ]; then
        PYTHON="\$candidate"
        break
    fi
done
if [ -z "\$PYTHON" ]; then
    osascript -e 'display alert "PhotoVerifier" message "Python 3 not found.\n\nRun the install.sh script from the project folder to fix this." as critical'
    exit 1
fi
exec "\$PYTHON" "\$SCRIPT"
LAUNCHER

chmod +x "$APP_DEST/Contents/MacOS/PhotoVerifier"

# Write Info.plist
cat > "$APP_DEST/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>PhotoVerifier</string>
    <key>CFBundleIdentifier</key>
    <string>com.user.photoverifier</string>
    <key>CFBundleName</key>
    <string>PhotoVerifier</string>
    <key>CFBundleDisplayName</key>
    <string>PhotoVerifier</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.photography</string>
</dict>
</plist>
PLIST

# Strip quarantine so macOS doesn't block it
xattr -cr "$APP_DEST" 2>/dev/null || true
# Ad-hoc sign so Gatekeeper accepts it
codesign --sign - --force --deep "$APP_DEST" 2>/dev/null || true

success "PhotoVerifier.app created on your Desktop"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo ""
echo "  • Double-click PhotoVerifier.app on your Desktop to open it"
echo "  • To keep it in the Dock: right-click the dock icon"
echo "    while it's running → Options → Keep in Dock"
echo ""
echo "  If macOS shows 'unidentified developer' on first open:"
echo "  → Right-click the .app → Open → Open (in the dialog)"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
