#!/bin/bash
set -e

APP_NAME="HeadScroller"
APP_DIR="$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

# Clean previous build
rm -rf "$APP_DIR"

# Create .app bundle structure
mkdir -p "$MACOS" "$RESOURCES"

# Compile the Swift binary
echo "Compiling..."
swiftc HeadScrollerMenuBar.swift -o "$MACOS/HeadScrollerMenuBar" -framework Cocoa

# Copy resources
cp headscroller.py "$RESOURCES/"
cp face_landmarker.task "$RESOURCES/"
cp MenuBarIcon.png "$RESOURCES/"
cp requirements.txt "$RESOURCES/"

# Create default settings if not present in Resources
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
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
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

# Create an .icns app icon from the MenuBarIcon.png
echo "Creating app icon..."
ICONSET="AppIcon.iconset"
mkdir -p "$ICONSET"
sips -z 16 16     MenuBarIcon.png --out "$ICONSET/icon_16x16.png"      > /dev/null 2>&1
sips -z 32 32     MenuBarIcon.png --out "$ICONSET/icon_16x16@2x.png"   > /dev/null 2>&1
sips -z 32 32     MenuBarIcon.png --out "$ICONSET/icon_32x32.png"      > /dev/null 2>&1
sips -z 64 64     MenuBarIcon.png --out "$ICONSET/icon_32x32@2x.png"   > /dev/null 2>&1
sips -z 128 128   MenuBarIcon.png --out "$ICONSET/icon_128x128.png"    > /dev/null 2>&1
sips -z 256 256   MenuBarIcon.png --out "$ICONSET/icon_128x128@2x.png" > /dev/null 2>&1
sips -z 256 256   MenuBarIcon.png --out "$ICONSET/icon_256x256.png"    > /dev/null 2>&1
sips -z 512 512   MenuBarIcon.png --out "$ICONSET/icon_256x256@2x.png" > /dev/null 2>&1
sips -z 512 512   MenuBarIcon.png --out "$ICONSET/icon_512x512.png"    > /dev/null 2>&1
sips -z 1024 1024 MenuBarIcon.png --out "$ICONSET/icon_512x512@2x.png" > /dev/null 2>&1
iconutil -c icns "$ICONSET" -o "$RESOURCES/AppIcon.icns"
rm -rf "$ICONSET"

# Ad-hoc codesign
echo "Signing..."
codesign --force --deep --sign - "$APP_DIR"

echo ""
echo "Built: $APP_DIR"
echo "You can now:"
echo "  open $APP_DIR              # run it"
echo "  cp -R $APP_DIR /Applications/  # install it"
echo "  zip -r HeadScroller.zip $APP_DIR  # share it"
