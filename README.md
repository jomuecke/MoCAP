# Multi-Camera Raspberry Pi Motion Tracking Setup

This README guides you through setting up Raspberry Pi Zero 2W devices (with camera modules) and a Raspberry Pi 3 as a master controller, for synchronized multi-angle video recording and transfer. It covers OS flashing, USB gadget mode, static MAC/IP configuration, camera configuration, script deployment, and wiring.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Flashing the SD Cards](#flashing-the-sd-cards)
3. [Pi Zero: USB Gadget & Networking](#pi-zero-usb-gadget--networking)
   - A. `cmdline.txt` and `config.txt` Changes
   - B. Static MAC Addresses (g_ether)
   - C. Static IP Addresses
4. [Pi 3: Master Controller Setup](#pi-3-master-controller-setup)
   - A. Static IP for USB Interfaces
   - B. SSH Key Setup
5. [Camera Configuration](#camera-configuration)
   - A. Disable Legacy Camera Stack
   - B. Verify `libcamera`
6. [Script Deployment](#script-deployment)
   - A. Pi Zero Listener (`video_toggle_listener.py`)
   - B. Systemd Service for Autostart
   - C. Pi 3 Trigger Script (`camera_master.py`)
7. [Wiring & GPIO Pinouts](#wiring--gpio-pinouts)
   - A. Trigger Signal
   - B. LED Indicator
   - C. Common Ground
8. [Post-Processing (Optional)](#post-processing-optional)
9. [Testing & Usage](#testing--usage)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Raspberry Pi Zero 2W (×2) with NoIR camera modules and IR illumination
- Raspberry Pi 3 (master)
- MicroSD cards (≥16 GB) for each device
- USB cables, jumper wires, resistors (330 Ω), LEDs
- A host PC with SD-card flashing tool (Raspberry Pi Imager or `dd`)

---

## Flashing the SD Cards

1. Download **Raspberry Pi OS Lite** (Bullseye or later).
2. Flash each MicroSD with Raspberry Pi Imager or:
   ```bash
   # On Linux (adjust device path e.g. /dev/sdX)
   gunzip -c 2025-xx-xx-raspios-bullseye-armhf-lite.img.gz \
     | sudo dd of=/dev/sdX bs=4M conv=fsync
   ```
3. After flashing, mount the `boot` partition on your host and proceed with edits.

---

## Pi Zero: USB Gadget & Networking

### A. `cmdline.txt` & `config.txt` Changes

- **`/boot/cmdline.txt`**: add `modules-load=dwc2,g_ether` immediately after `rootwait`, e.g.:
  ```text
  ... rootwait modules-load=dwc2,g_ether 
  ```


- **`/boot/config.txt`**: enable camera overlay and USB gadget:
  ```ini
  dtoverlay=dwc2
  camera_auto_detect=1
  start_x=0        # libcamera stack
  gpu_mem=128      # minimal GPU memory
  ```

### B. Static MAC Addresses (USB Ethernet)

To assign fixed MACs on each Zero, edit `config.txt` with overlay parameters:

```ini
# For Pi Zero 1
modules-load=dwc2 g_ether g_ether.dev_addr=02:00:00:00:00:01 g_ether.host_addr=02:00:00:00:00:00 net.ifnames=0
```
Replace addresses as desired, ensuring uniqueness and valid OUI.

- **`/boot/ssh`**: add empty ssh file without extension (touch ssh)

Reboot Pi zero.


### C. Static IP Addresses

On each Pi Zero, configure `dhcpcd` to assign a static IP to the USB interface (`usb0`):

Edit `/etc/dhcpcd.conf`, add:
```ini
interface usb0
  static ip_address=192.168.6.2/24  # Pi Zero 1
# interface usb0
#   static ip_address=192.168.7.2/24  # Pi Zero 2

```
Reboot or restart `dhcpcd`:
```bash
sudo systemctl restart dhcpcd
```

---

## Pi 3: Master Controller Setup


### A: Set Persistent Interface Names with Udev

Find each Pi Zero’s MAC address by connecting them one at a time and running:

ip link show usb0
Then, create a udev rule file:

sudo nano /etc/udev/rules.d/90-pizero-net.rules
Example content:
```ini
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="aa:bb:cc:dd:ee:01", NAME="pi1usb"
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="aa:bb:cc:dd:ee:02", NAME="pi2usb"
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="aa:bb:cc:dd:ee:03", NAME="pi3usb"
```
Reload udev rules:
```bash
sudo udevadm control --reload
sudo udevadm trigger
```

### B. Static IP for USB Interfaces

On the Pi 3, assign static IPs for the USB gadget links from each Zero:

Edit `/etc/dhcpcd.conf`:
```ini
interface pi1usb   # from Pi Zero 1
static ip_address=192.168.6.1/24
interface pi2usb   # from Pi Zero 2
static ip_address=192.168.7.1/24

```

After saving, restart networking:
```bash
sudo systemctl restart dhcpcd
```

### C. Assign Static IPs with a Script

Create a shell script to assign IPs to each interface.


`assign_static_ips.sh`:
```ini
#!/bin/bash

# Mapping: interface name -> IP address
declare -A iface_to_ip=(
  ["pi1usb"]="192.168.6.1"
  ["pi2usb"]="192.168.6.2"
  ["pi3usb"]="192.168.6.3"
)

echo "🔧 Assigning static IPs to known Pi Zero interfaces..."

for iface in "${!iface_to_ip[@]}"; do
  ip="${iface_to_ip[$iface]}"
  if ip link show "$iface" &>/dev/null; then
    echo "➡️  Setting $ip on $iface"
    sudo ip addr flush dev "$iface"
    sudo ip addr add "$ip/24" dev "$iface"
    sudo ip link set "$iface" up
  else
    echo "⚠️  Interface $iface not found — skipping"
  fi
done

echo "✅ Done."
```ini

Make it executable:

```bash
chmod +x assign_static_ips.sh
```
Run manually:
```bash
./assign_static_ips.sh
```

🚀 Optional: Run on Boot

```bash
crontab -e
```

Add:
```ini
@reboot /path/to/assign_static_ips.sh
```

### B. SSH Key Setup

To allow passwordless SCP from Zeros:

1. On Pi Zero, generate key if needed:
   ```bash
   ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
   ```
2. Copy public key to Pi 3:
   ```bash
   ssh-copy-id pi@192.168.6.1
   ssh-copy-id pi@192.168.7.1
   ```

---

## Camera Configuration

### A. Disable Legacy Camera Stack

On each Pi Zero:
```bash
sudo raspi-config
# Interface Options → Legacy Camera → Disable
sudo reboot
```

### B. Verify `libcamera`

After reboot, test:
```bash
libcamera-hello --list-cameras
libcamera-hello  # shows preview
```

---
## Script Deployment

### A. Pi Zero Listener (`video_toggle_listener.py`)

Place this in `/home/pi/video_toggle_listener.py`:
```python
import RPi.GPIO as GPIO
import subprocess, time

TRIGGER_PIN, LED_PIN = 17, 27
recording_process = None
is_recording = False

def start_recording():
    global recording_process, is_recording
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    fname = f"/home/pi/video_{timestamp}.h264"
    GPIO.output(LED_PIN, GPIO.HIGH)
    recording_process = subprocess.Popen([
        "libcamera-vid","--framerate","30",
        "--width","1280","--height","720",
        "--bitrate","4000000","--codec","h264",
        "--timeout","0","-o", fname
    ])
    is_recording = True
    print("Recording started ->", fname)

def stop_recording():
    global recording_process, is_recording
    recording_process.terminate(); recording_process.wait()
    GPIO.output(LED_PIN, GPIO.LOW)
    print("Recording stopped")
    subprocess.run(["scp", fname, "pi@192.168.6.1:/home/pi/captured_videos/"], check=True)
    is_recording = False

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIGGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.add_event_detect(TRIGGER_PIN, GPIO.RISING, bouncetime=500,
                      callback=lambda ch: start_recording() if not is_recording else stop_recording())
print("Listener ready (1st pulse ▶ start; 2nd ▶ stop+send)")
try:
    while True: time.sleep(0.1)
except KeyboardInterrupt:
    if is_recording: stop_recording()
finally:
    GPIO.cleanup()
```

### B. Systemd Service for Autostart

Create `/etc/systemd/system/camera_listener.service`:
```ini
[Unit]
Description=Camera Toggle Listener
After=multi-user.target
[Service]
ExecStart=/usr/bin/python3 /home/pi/video_toggle_listener.py
Restart=always
User=pi
[Install]
WantedBy=multi-user.target
```
Enable & start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable camera_listener.service
sudo systemctl start camera_listener.service
```

### C. Pi 3 Trigger Script (`camera_master.py`)

Place in `/home/pi/camera_master.py`:
```python
import RPi.GPIO as GPIO, time
TRIGGER_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIGGER_PIN, GPIO.OUT, initial=GPIO.LOW)
# START
GPIO.output(TRIGGER_PIN, GPIO.HIGH); time.sleep(0.1)
GPIO.output(TRIGGER_PIN, GPIO.LOW)
print("▶ Recording")
try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    # STOP
    GPIO.output(TRIGGER_PIN, GPIO.HIGH); time.sleep(0.1)
    GPIO.output(TRIGGER_PIN, GPIO.LOW)
    print("■ Stopped")
finally: GPIO.cleanup()
```

---

## Wiring & GPIO Pinouts

1. **Trigger Signal (BCM 17)**
   - Pi 3 GPIO 17 → Pi Zero GPIO 17 (both zeros in parallel)
2. **LED Indicator (BCM 27)**
   - Pi Zero GPIO 27 → 330 Ω resistor → LED anode; LED cathode → GND
3. **Ground (common)**
   - Connect GND from Pi 3 to GND on each Pi Zero

Use BCM numbering throughout.

---

## Post-Processing (Optional)

Convert `.h264` to `.mp4` and grayscale:
```bash
ffmpeg -i input.h264 -vf format=gray -c:v libx264 output_gray.mp4
```

---

## Testing & Usage

1. Boot all devices.
2. On each Pi Zero, verify `camera_listener` is active (`systemctl status`).
3. On Pi 3, run:
   ```bash
   sudo python3 /home/pi/camera_master.py
   ```
4. First Ctrl+C → start; next Ctrl+C → stop + auto-transfer.
5. Check `/home/pi/captured_videos/` on Pi 3 for files.

---

## Troubleshooting

- **`no cameras available`** → ensure legacy camera is disabled and ribbon seated.
- **`halting reached timeout`** → add `--timeout 0` to `libcamera-vid`.
- **`scp` errors** → check static IPs, SSH keys, directory exists.
- **Service not starting** → inspect `journalctl -u camera_listener.service`.

Enjoy your synchronized multi-angle recording rig for motion tracking!
