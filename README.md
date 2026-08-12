# ⚡ Tenda HG7 DNS Cleaner & Auto Router Rebooter

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Router](https://img.shields.io/badge/Router-Tenda%20HG7-00B4D8?style=for-the-badge&logo=tp-link&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?style=for-the-badge&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)

*An automated, one-click network maintenance & Tenda HG7 router reboot solution for Windows.*

</div>

---

## 📌 Overview

**Tenda HG7 DNS Cleaner & Auto Router Rebooter** is a powerful Python & Batch automation suite designed to streamline internet connectivity troubleshooting, clear system junk, and reset public WAN IP addresses on **Tenda HG7** (and compatible Tenda / Realtek / Broadcom firmware) routers.

### 🌟 Key Features

- 🧹 **Deep System Cleanup**: Clears Windows `%TEMP%`, `C:\Windows\Temp`, `Prefetch`, CrashDumps, and browser temporary caches to free up memory & disk space.
- ⚡ **Network Stack Reset**: Automatically executes `ipconfig /release`, `ipconfig /flushdns`, `netsh winsock reset`, `netsh int ip reset`, and `ipconfig /renew`.
- 🔐 **Smart Tenda HG7 Authentication**: Dual-mode login supporting HTTP Basic Authentication (`admin:admin`) and HTML Form login session cookies.
- 🔄 **Automated Router Reboot**: Submits the `Commit and Reboot` form on `http://192.168.1.1/reboot.asp` and monitors connection status until the router is back online.
- 🌐 **Public IP Monitor**: Fetches and compares your public WAN IP address before and after reboot to verify IP rotation.
- 🔀 **Dynamic DNS Switcher**: Toggles active network interfaces between **Google DNS** (`8.8.8.8` / `8.8.4.4`) and **Cloudflare DNS** (`1.1.1.1` / `1.0.0.1`) on every run.
- 🎨 **Nord-Themed Powerline UI**: Styled terminal interface with clear progress banners and result summary boxes.

---

## 📂 Project Structure

```
.
├── LAUNCH.bat            # Main double-click launcher (Auto-elevates Admin & launches NetMaintain.py)
├── NetMaintain.py        # Core suite (Temp Clean + Network Reset + Tenda Reboot + DNS Toggle)
├── reboot_router.bat     # Standalone launcher for router reboot only
├── tenda_reboot_tui.py   # Standalone TUI script for Tenda HG7 router reboot & IP verification
├── .gitignore            # Git ignore file
└── README.md             # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites

- **Windows 10 / 11**
- **Python 3.8+** installed and added to system `PATH`
- **Tenda HG7 Router** connected at `http://192.168.1.1`

Required Python library (`requests`) will be automatically installed on first run if missing:
```bash
pip install requests
```

---

## 💻 Usage

### Option 1: Full Maintenance Suite (Recommended)

Double-click **`LAUNCH.bat`** (or run from Terminal as Administrator):

```cmd
LAUNCH.bat
```

**What it does:**
1. Cleans temporary system junk.
2. Resets the Windows network stack & flushes DNS.
3. Fetches pre-reboot Public WAN IP.
4. Logins into Tenda HG7 (`http://192.168.1.1`) and submits `Commit and Reboot`.
5. Waits for router connection to cycle DOWN and back UP.
6. Verifies new post-reboot Public WAN IP.
7. Alternates DNS servers (Google ↔ Cloudflare).
8. Displays an interactive summary table.

---

### Option 2: Router Reboot Only

If you only want to reboot the Tenda HG7 router and verify IP change without cleaning system files:

Double-click **`reboot_router.bat`**:

```cmd
reboot_router.bat
```

Or run directly via CLI:
```bash
python tenda_reboot_tui.py --host 192.168.1.1 --user admin --password admin
```

---

## ⚙️ Configuration

If your router IP or credentials differ from defaults (`192.168.1.1` / `admin` / `admin`), edit the configuration constants:

In **`NetMaintain.py`**:
```python
ROUTER_HOST = "http://192.168.1.1"
ROUTER_USER = "admin"
ROUTER_PASS = "admin"
```

In **`reboot_router.bat`**:
```cmd
python tenda_reboot_tui.py --host 192.168.1.1 --user admin --password admin
```

---

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for more information.

---

<div align="center">

Crafted with ❤️ for seamless network performance & Tenda router management.

</div>
