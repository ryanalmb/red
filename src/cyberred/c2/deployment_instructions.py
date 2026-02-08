"""Platform-specific deployment instructions for Drop Box.

Story 12.8: Natural Language Drop Box Setup - Task 5

Generates platform-specific deployment instructions for drop box setup.

Usage:
    from cyberred.c2.deployment_instructions import get_instructions, SUPPORTED_PLATFORMS
    
    instructions = get_instructions("android", cert_path, key_path, ca_path, c2_url)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()

# Supported platforms
SUPPORTED_PLATFORMS = {"android", "windows", "linux", "macos", "ios"}


def get_instructions(
    platform: str,
    cert_path: Path,
    key_path: Path,
    ca_path: Path,
    c2_url: str,
    drop_box_id: Optional[str] = None,
) -> str:
    """Generate platform-specific deployment instructions.
    
    Args:
        platform: Target platform (android, windows, linux, macos, ios).
        cert_path: Path to client certificate.
        key_path: Path to client private key.
        ca_path: Path to CA certificate.
        c2_url: C2 server URL (e.g., wss://c2.example.com:8444).
        drop_box_id: Optional drop box identifier.
        
    Returns:
        Formatted deployment instructions string.
        
    Raises:
        ValueError: If platform is not supported.
    """
    platform = platform.lower()
    
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}. Supported: {', '.join(sorted(SUPPORTED_PLATFORMS))}")
    
    # Get template function
    template_funcs = {
        "android": _android_instructions,
        "windows": _windows_instructions,
        "linux": _linux_instructions,
        "macos": _macos_instructions,
        "ios": _ios_instructions,
    }
    
    instructions = template_funcs[platform](
        cert_path=cert_path,
        key_path=key_path,
        ca_path=ca_path,
        c2_url=c2_url,
        drop_box_id=drop_box_id,
    )
    
    log.info("deployment_instructions_generated", platform=platform)
    
    return instructions


def _android_instructions(
    cert_path: Path,
    key_path: Path,
    ca_path: Path,
    c2_url: str,
    drop_box_id: Optional[str] = None,
) -> str:
    """Generate Android deployment instructions."""
    return f"""# Android Drop Box Deployment

## Prerequisites
- USB debugging enabled on Android device
- ADB installed on your computer
- Device connected via USB

## Deployment Steps

### 1. Push the drop box binary
```bash
adb push dropbox-android-arm64 /data/local/tmp/dropbox
adb shell chmod +x /data/local/tmp/dropbox
```

### 2. Copy certificates
```bash
adb push {cert_path} /data/local/tmp/dropbox.crt
adb push {key_path} /data/local/tmp/dropbox.key
adb push {ca_path} /data/local/tmp/ca.crt
```

### 3. Start the drop box
```bash
adb shell /data/local/tmp/dropbox \\
    -c2 {c2_url} \\
    -cert /data/local/tmp/dropbox.crt \\
    -key /data/local/tmp/dropbox.key \\
    -ca /data/local/tmp/ca.crt
```

### Alternative: Use QR Code
Scan the QR code below with the Cyber-Red mobile app for automatic setup.

## Troubleshooting
- Ensure USB debugging is enabled in Developer Options
- Try `adb devices` to verify device connection
- Check that SELinux isn't blocking execution: `adb shell getenforce`
"""


def _windows_instructions(
    cert_path: Path,
    key_path: Path,
    ca_path: Path,
    c2_url: str,
    drop_box_id: Optional[str] = None,
) -> str:
    """Generate Windows deployment instructions."""
    return f"""# Windows Drop Box Deployment

## Prerequisites
- Administrator access
- Windows Defender exclusion (optional but recommended)

## Deployment Steps

### 1. Download the binary
```powershell
# Download from releases
Invoke-WebRequest -Uri "https://releases.cyber-red.io/dropbox-windows-amd64.exe" -OutFile "C:\\cyber-red\\dropbox.exe"

# Create directory if needed
New-Item -ItemType Directory -Force -Path "C:\\cyber-red"
```

### 2. Copy certificates
```powershell
# Copy certificate files to C:\\cyber-red\\
Copy-Item "{cert_path}" -Destination "C:\\cyber-red\\dropbox.crt"
Copy-Item "{key_path}" -Destination "C:\\cyber-red\\dropbox.key"
Copy-Item "{ca_path}" -Destination "C:\\cyber-red\\ca.crt"
```

### 3. Configure Windows Firewall (if needed)
```powershell
New-NetFirewallRule -DisplayName "Cyber-Red Drop Box" -Direction Outbound -Program "C:\\cyber-red\\dropbox.exe" -Action Allow
```

### 4. Run the drop box
```powershell
C:\\cyber-red\\dropbox.exe `
    -c2 {c2_url} `
    -cert C:\\cyber-red\\dropbox.crt `
    -key C:\\cyber-red\\dropbox.key `
    -ca C:\\cyber-red\\ca.crt
```

### Optional: Install as Windows Service
```powershell
# Use NSSM or sc.exe to install as a service for persistence
sc.exe create CyberRedDropbox binPath= "C:\\cyber-red\\dropbox.exe -c2 {c2_url} -cert C:\\cyber-red\\dropbox.crt -key C:\\cyber-red\\dropbox.key -ca C:\\cyber-red\\ca.crt"
```

## Troubleshooting
- Run PowerShell as Administrator
- Check Windows Defender logs if binary is blocked
- Verify outbound connectivity to C2 server
"""


def _linux_instructions(
    cert_path: Path,
    key_path: Path,
    ca_path: Path,
    c2_url: str,
    drop_box_id: Optional[str] = None,
) -> str:
    """Generate Linux deployment instructions."""
    service_name = drop_box_id or "cyber-red-dropbox"
    
    return f"""# Linux Drop Box Deployment

## Prerequisites
- Root or sudo access
- curl installed

## Deployment Steps

### 1. Download the binary
```bash
curl -O https://releases.cyber-red.io/dropbox-linux-amd64
chmod +x dropbox-linux-amd64
sudo mv dropbox-linux-amd64 /usr/local/bin/dropbox
```

### 2. Copy certificates
```bash
sudo mkdir -p /etc/cyber-red
sudo cp {cert_path} /etc/cyber-red/dropbox.crt
sudo cp {key_path} /etc/cyber-red/dropbox.key
sudo cp {ca_path} /etc/cyber-red/ca.crt

# Secure the private key
sudo chmod 600 /etc/cyber-red/dropbox.key
```

### 3. Run the drop box
```bash
/usr/local/bin/dropbox \\
    -c2 {c2_url} \\
    -cert /etc/cyber-red/dropbox.crt \\
    -key /etc/cyber-red/dropbox.key \\
    -ca /etc/cyber-red/ca.crt
```

### Optional: Install as systemd service
```bash
sudo tee /etc/systemd/system/{service_name}.service << EOF
[Unit]
Description=Cyber-Red Drop Box
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/dropbox -c2 {c2_url} -cert /etc/cyber-red/dropbox.crt -key /etc/cyber-red/dropbox.key -ca /etc/cyber-red/ca.crt
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable {service_name}
sudo systemctl start {service_name}
```

## Troubleshooting
- Check connectivity: `curl -v {c2_url.replace('wss://', 'https://').replace('ws://', 'http://')}`
- View logs: `journalctl -u {service_name} -f`
- Verify certificates: `openssl x509 -in /etc/cyber-red/dropbox.crt -text -noout`
"""


def _macos_instructions(
    cert_path: Path,
    key_path: Path,
    ca_path: Path,
    c2_url: str,
    drop_box_id: Optional[str] = None,
) -> str:
    """Generate macOS deployment instructions."""
    plist_name = drop_box_id or "com.cyber-red.dropbox"
    
    return f"""# macOS Drop Box Deployment

## Prerequisites
- Administrator access
- Security approval for unsigned binary (System Preferences → Security)

## Deployment Steps

### 1. Download the binary
```bash
curl -O https://releases.cyber-red.io/dropbox-darwin-amd64
chmod +x dropbox-darwin-amd64
sudo mv dropbox-darwin-amd64 /usr/local/bin/dropbox
```

### 2. Approve security exception
```bash
# Remove quarantine attribute
sudo xattr -d com.apple.quarantine /usr/local/bin/dropbox

# Or manually approve in System Preferences → Security & Privacy
```

### 3. Copy certificates
```bash
sudo mkdir -p /etc/cyber-red
sudo cp {cert_path} /etc/cyber-red/dropbox.crt
sudo cp {key_path} /etc/cyber-red/dropbox.key
sudo cp {ca_path} /etc/cyber-red/ca.crt

# Secure the private key
sudo chmod 600 /etc/cyber-red/dropbox.key
```

### 4. Run the drop box
```bash
/usr/local/bin/dropbox \\
    -c2 {c2_url} \\
    -cert /etc/cyber-red/dropbox.crt \\
    -key /etc/cyber-red/dropbox.key \\
    -ca /etc/cyber-red/ca.crt
```

### Optional: Install as launchd service
```bash
sudo tee /Library/LaunchDaemons/{plist_name}.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/dropbox</string>
        <string>-c2</string>
        <string>{c2_url}</string>
        <string>-cert</string>
        <string>/etc/cyber-red/dropbox.crt</string>
        <string>-key</string>
        <string>/etc/cyber-red/dropbox.key</string>
        <string>-ca</string>
        <string>/etc/cyber-red/ca.crt</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

sudo launchctl load /Library/LaunchDaemons/{plist_name}.plist
```

## Troubleshooting
- If blocked by Gatekeeper: System Preferences → Security → Allow
- Check logs: `log show --predicate 'process == "dropbox"' --last 1h`
- Verify binary: `codesign -dv /usr/local/bin/dropbox`
"""


def _ios_instructions(
    cert_path: Path,
    key_path: Path,
    ca_path: Path,
    c2_url: str,
    drop_box_id: Optional[str] = None,
) -> str:
    """Generate iOS deployment instructions."""
    return f"""# iOS Drop Box Deployment

## Prerequisites
- Jailbroken iOS device (for full functionality)
- OR use the Cyber-Red iOS app from TestFlight

## Option 1: Cyber-Red iOS App (Recommended)

### 1. Install from TestFlight
- Request TestFlight invite from your administrator
- Install "Cyber-Red Drop Box" app

### 2. Configure via QR Code
- Open the app and tap "Scan QR Code"
- Scan the QR code displayed below
- The app will automatically configure:
  - C2 Server: {c2_url}
  - Certificate fingerprint and drop box ID

### 3. Grant Permissions
- Allow network access when prompted
- Enable background app refresh for persistent connection

## Option 2: Jailbroken Device (Advanced)

### 1. SSH to device
```bash
ssh root@<device-ip>
```

### 2. Download binary
```bash
curl -O https://releases.cyber-red.io/dropbox-ios-arm64
chmod +x dropbox-ios-arm64
mv dropbox-ios-arm64 /usr/local/bin/dropbox
```

### 3. Copy certificates
```bash
mkdir -p /var/mobile/cyber-red
# Transfer cert files via SCP
scp {cert_path} root@<device-ip>:/var/mobile/cyber-red/dropbox.crt
scp {key_path} root@<device-ip>:/var/mobile/cyber-red/dropbox.key
scp {ca_path} root@<device-ip>:/var/mobile/cyber-red/ca.crt
```

### 4. Run drop box
```bash
/usr/local/bin/dropbox \\
    -c2 {c2_url} \\
    -cert /var/mobile/cyber-red/dropbox.crt \\
    -key /var/mobile/cyber-red/dropbox.key \\
    -ca /var/mobile/cyber-red/ca.crt
```

## QR Code Configuration
Scan the QR code below with the Cyber-Red iOS app:

## Troubleshooting
- Ensure device has internet connectivity
- For jailbroken devices, verify SSH access
- Check that background app refresh is enabled
"""


def is_mobile_platform(platform: str) -> bool:
    """Check if platform is a mobile platform (requires QR code).
    
    Args:
        platform: Platform identifier.
        
    Returns:
        True if platform is mobile (android or ios).
    """
    return platform.lower() in {"android", "ios"}
