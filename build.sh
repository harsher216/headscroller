#!/bin/bash
set -e

APP_NAME="HeadScroller"
APP_DIR="$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

# Clean previous build
rm -rf "$APP_DIR"

# ── Step 1: Bundle Python script with PyInstaller ────────────────────────────
echo "Bundling Python with PyInstaller..."

# Find pyinstaller (check common locations)
PYINSTALLER=$(which pyinstaller 2>/dev/null || echo "")
if [ -z "$PYINSTALLER" ]; then
    # Check user-local install
    for p in "$HOME/Library/Python/3.9/bin/pyinstaller" \
             "$HOME/Library/Python/3.10/bin/pyinstaller" \
             "$HOME/Library/Python/3.11/bin/pyinstaller" \
             "$HOME/Library/Python/3.12/bin/pyinstaller"; do
        if [ -x "$p" ]; then
            PYINSTALLER="$p"
            break
        fi
    done
fi
if [ -z "$PYINSTALLER" ]; then
    echo "ERROR: pyinstaller not found. Install it with: pip3 install pyinstaller"
    exit 1
fi

"$PYINSTALLER" headscroller.spec --noconfirm --clean 2>&1 | tail -5

if [ ! -f "dist/headscroller/headscroller" ]; then
    echo "ERROR: PyInstaller build failed"
    exit 1
fi
echo "Python bundle ready ($(du -sh dist/headscroller | cut -f1))"

# ── Step 2: Create .app bundle structure ─────────────────────────────────────
echo "Building .app bundle..."
mkdir -p "$MACOS" "$RESOURCES"

# Compile the Swift menu bar binary
echo "Compiling Swift..."
swiftc HeadScrollerMenuBar.swift -o "$MACOS/HeadScrollerMenuBar" -framework Cocoa

# Copy the entire PyInstaller bundle into Resources
cp -R dist/headscroller/* "$RESOURCES/"

# Copy the menu bar icon
cp MenuBarIcon.png AppIcon.png "$RESOURCES/"

# Create default settings
cat > "$RESOURCES/settings.json" << 'EOF'
{
  "sensitivity" : 10,
  "deadzone" : 0.04,
  "cam" : 0
}
EOF

# Create Info.plist
cat > "$CONTENTS/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>HeadScroller</string>
    <key>CFBundleDisplayName</key>
    <string>HeadScroller</string>
    <key>CFBundleIdentifier</key>
    <string>com.headscroller.app</string>
    <key>CFBundleVersion</key>
    <string>1.3</string>
    <key>CFBundleShortVersionString</key>
    <string>1.3</string>
    <key>CFBundleExecutable</key>
    <string>HeadScrollerMenuBar</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSCameraUsageDescription</key>
    <string>HeadScroller needs camera access to track your head movement for scrolling.</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>HeadScroller needs accessibility access to generate scroll events.</string>
</dict>
</plist>
EOF

# Create an .icns app icon from the AppIcon.png
echo "Creating app icon..."
ICONSET="AppIcon.iconset"
mkdir -p "$ICONSET"
sips -z 16 16     AppIcon.png --out "$ICONSET/icon_16x16.png"      > /dev/null 2>&1
sips -z 32 32     AppIcon.png --out "$ICONSET/icon_16x16@2x.png"   > /dev/null 2>&1
sips -z 32 32     AppIcon.png --out "$ICONSET/icon_32x32.png"      > /dev/null 2>&1
sips -z 64 64     AppIcon.png --out "$ICONSET/icon_32x32@2x.png"   > /dev/null 2>&1
sips -z 128 128   AppIcon.png --out "$ICONSET/icon_128x128.png"    > /dev/null 2>&1
sips -z 256 256   AppIcon.png --out "$ICONSET/icon_128x128@2x.png" > /dev/null 2>&1
sips -z 256 256   AppIcon.png --out "$ICONSET/icon_256x256.png"    > /dev/null 2>&1
sips -z 512 512   AppIcon.png --out "$ICONSET/icon_256x256@2x.png" > /dev/null 2>&1
sips -z 512 512   AppIcon.png --out "$ICONSET/icon_512x512.png"    > /dev/null 2>&1
sips -z 1024 1024 AppIcon.png --out "$ICONSET/icon_512x512@2x.png" > /dev/null 2>&1
iconutil -c icns "$ICONSET" -o "$RESOURCES/AppIcon.icns"
rm -rf "$ICONSET"

# Ad-hoc codesign
echo "Signing..."
codesign --force --deep --sign - "$APP_DIR"

# ── Step 3: Build styled DMG installer ───────────────────────────────────────
echo "Building DMG..."
DMG_NAME="HeadScroller.dmg"
TMP_DMG="HeadScroller.temp.dmg"
VOL_NAME="HeadScroller"
STAGING="dmg-staging"

# Unmount any leftover HeadScroller volumes from previous runs
for v in /Volumes/HeadScroller*; do
    [ -d "$v" ] && hdiutil detach "$v" -force > /dev/null 2>&1 || true
done

rm -f "$DMG_NAME" "$TMP_DMG"
rm -rf "$STAGING"
mkdir "$STAGING"
cp -R "$APP_DIR" "$STAGING/"

# Hidden background folder with Retina (@2x) companion
mkdir "$STAGING/.background"
cp dmg-background.png "$STAGING/.background/background.png"
cp dmg-background@2x.png "$STAGING/.background/background@2x.png"

# Writable DMG first so we can set Finder layout
hdiutil create -size 400m -fs HFS+ -volname "$VOL_NAME" \
    -srcfolder "$STAGING" -format UDRW -ov "$TMP_DMG" > /dev/null
rm -rf "$STAGING"

# Mount and lay out
DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "$TMP_DMG" | \
    grep -E '^/dev/' | head -1 | awk '{print $1}')
MOUNT="/Volumes/$VOL_NAME"

# Applications symlink (created inside the mounted volume so Finder sees it)
ln -s /Applications "$MOUNT/Applications"

# Finder layout via AppleScript
osascript <<EOF
set bgFile to (POSIX file "$MOUNT/.background/background.png") as alias
tell application "Finder"
    tell disk "$VOL_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 120, 800, 520}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 128
        set text size of viewOptions to 13
        set background picture of viewOptions to bgFile
        set position of item "HeadScroller.app" of container window to {160, 250}
        set position of item "Applications" of container window to {440, 250}
        close
        open
        update without registering applications
        delay 2
    end tell
end tell
EOF

# Finalize
sync
hdiutil detach "$DEVICE" > /dev/null
hdiutil convert "$TMP_DMG" -format UDZO -imagekey zlib-level=9 \
    -o "$DMG_NAME" > /dev/null
rm -f "$TMP_DMG"

echo ""
echo "Built: $APP_DIR ($(du -sh "$APP_DIR" | cut -f1))"
echo "Built: $DMG_NAME ($(du -sh "$DMG_NAME" | cut -f1))"
echo ""
echo "You can now:"
echo "  open $APP_DIR                       # run it"
echo "  cp -R $APP_DIR /Applications/       # install it"
echo "  open $DMG_NAME                      # test DMG install flow"
