#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tenda HG7 Router Rebooter — TUI Edition
- Clears the terminal at start
- Friendly step-by-step output with Nord color styling
- Compares Public IP before vs after reboot
- Persists the last-seen Public IP in ~/.tenda_hg7_last_ip
"""

import os
import re
import time
import socket
import html
import shutil
import argparse
import requests
from urllib.parse import urljoin
from requests.auth import HTTPBasicAuth
from pathlib import Path

# ---------- Config ----------
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139 Safari/537.36"
CANDIDATE_ROOTS = ["/reboot.asp", "/", "/index.asp", "/login.asp", "/admin/login.asp", "/main.asp", "/home.asp", "/getpage.gch?pid=1002&nextpage=sys_reboot_t.gch"]
CANDIDATE_REBOOT_PAGES = [
    "/reboot.asp", "/admin/reboot.asp", "/system/reboot.asp",
    "/admin/system.asp", "/admin/maintenance.asp", "/tools/reboot.asp",
    "/sysReboot.asp", "/Maintenance.asp",
    "/getpage.gch?pid=1002&nextpage=sys_reboot_t.gch", "/getpage.gch", "/sys_reboot_t.gch", "/boaform/admin/formReboot"
]
CANDIDATE_REBOOT_PAYLOADS = [
    {"reboot": "Commit and Reboot"},  # Tenda HG7
    {"reboot": "Reboot"},             # Tdata / C-Data / Generic
    {"reboot": "1"},
    {"sysSubmit": "Commit and Reboot"},
    {"sysSubmit": "Reboot"},
    {"IF_ACTION": "devrestart"},      # ZTE ZXHN F660
    {"IF_ACTION": "reboot"},          # ZTE
    {"submit-url": "/reboot.asp", "reboot": "Commit and Reboot"},
    {"submit-url": "/", "reboot": "Reboot"},
    {}
]
LOGIN_CANDIDATES = [
    ("/boaform/admin/formLogin", {"username": "admin", "password": "admin"}),
    ("/boaform/admin/formLogin", {"user": "admin", "psw": "admin"}),
    ("/boaform/admin/formLogin", {"admuser": "admin", "admpass": "admin"}),
    ("/boaform/admin/formLogin_en", {"username": "admin", "password": "admin"}),
]
STATE_FILE = Path.home() / ".tenda_hg7_last_ip"
# ----------------------------

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def term_width():
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80

def banner(title: str):
    w = term_width()
    line = "─" * max(10, min(w - 2, 80))
    print(f"┌{line}┐")
    title = f"  {title}  "
    pad = max(0, len(line) - len(title))
    print(f"│{title}{' ' * pad}│")
    print(f"└{line}┘")

def section(title: str):
    print(f"\n▶ {title}")

def info(msg: str):
    print(f"   • {msg}")

def ok(msg: str):
    print(f"   ✅ {msg}")

def warn(msg: str):
    print(f"   ⚠️  {msg}")

def err(msg: str):
    print(f"   ❌ {msg}")

def sleep_progress(seconds: int, label="waiting"):
    for i in range(seconds):
        print(f"      {label}… {seconds - i:>2}s", end="\r", flush=True)
        time.sleep(1)
    print(" " * 40, end="\r")

# ---------- Public IP helpers ----------
def get_public_ip(timeout=4):
    endpoints = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, timeout=timeout)
            if r.ok:
                ip = r.text.strip()
                if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) or ":" in ip:
                    return ip
        except Exception:
            pass
    return None

def read_last_ip():
    try:
        return STATE_FILE.read_text(encoding="utf-8").strip() or None
    except Exception:
        return None

def save_last_ip(ip: str):
    try:
        STATE_FILE.write_text(ip + "\n", encoding="utf-8")
    except Exception:
        pass

# ---------- Networking waiters ----------
def wait_until_down(host="192.168.1.1", port=80, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                time.sleep(1)
        except OSError:
            return True
    return False

def wait_until_up(host="192.168.1.1", port=80, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(2)
    return False

# ---------- HTML form helpers ----------
def first_ok(session, base, urls):
    for p in urls:
        url = urljoin(base, p)
        try:
            r = session.get(url, headers={"User-Agent": UA, "Connection": "close"}, timeout=6, allow_redirects=True)
            if r.status_code in (200, 302, 303):
                return r
        except requests.RequestException:
            pass
    return None

def find_form(html_text, action_contains=None, name_contains=None):
    if not html_text:
        return None
    for form_m in re.finditer(r"(?is)<form\b[^>]*>.*?</form>", html_text):
        form_html = form_m.group(0)
        act_m = re.search(r'(?is)\baction\s*=\s*["\']?([^"\'>\s]+)', form_html)
        action = act_m.group(1).strip() if act_m else ""
        if action_contains and action_contains.lower() not in action.lower():
            continue
        if name_contains and name_contains.lower() not in form_html.lower():
            continue
        fields = {}
        for inp in re.finditer(r'(?is)<input\b[^>]*>', form_html):
            name_m = re.search(r'(?is)\bname\s*=\s*["\']?([^"\'>\s]+)', inp.group(0))
            val_m = re.search(r'(?is)\bvalue\s*=\s*["\']?([^"\'>]*)', inp.group(0))
            val = html.unescape(val_m.group(1)) if val_m else ""
            if name_m:
                name = html.unescape(name_m.group(1))
                fields[name] = val
            else:
                inp_lower = inp.group(0).lower()
                if "submit" in inp_lower or "inner_btn" in inp_lower:
                    fields["reboot"] = val or "Commit and Reboot"
        return action, fields
    return None

def smart_login(session, base, user, pwd):
    _ = first_ok(session, base, CANDIDATE_ROOTS)
    pages_to_scan = CANDIDATE_ROOTS
    scanned = set()
    for p in pages_to_scan:
        if p in scanned: 
            continue
        scanned.add(p)
        try:
            r = session.get(urljoin(base, p), headers={"User-Agent": UA, "Connection": "close"}, timeout=6)
        except requests.RequestException:
            continue
        if r.status_code != 200 or not r.text:
            continue
        hit = find_form(r.text, action_contains="login")
        if hit:
            action, fields = hit
            pwd_key = next((k for k in fields if ("pwd" in k.lower() or "pass" in k.lower())), "password")
            user_key = next((k for k in fields if ("user" in k.lower() or "name" in k.lower()) or k.lower() in ("username", "login")), "username")
            fields[user_key] = user
            fields[pwd_key] = pwd
            login_url = urljoin(base, action)
            try:
                lr = session.post(login_url, data=fields, headers={
                    "User-Agent": UA, "Origin": base, "Referer": urljoin(base, p),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Connection": "close",
                }, timeout=6, allow_redirects=True)
                if lr.status_code in (200, 302, 303) and "login" not in (lr.text or "").lower():
                    return True
            except requests.RequestException:
                pass
    try:
        r = session.get(urljoin(base, "/reboot.asp"), auth=HTTPBasicAuth(user, pwd),
                        headers={"User-Agent": UA, "Connection": "close"}, timeout=6)
        if r.status_code in (200, 302, 303):
            return True
    except requests.RequestException:
        pass
    return False

def find_and_post_reboot(session, base):
    for p in CANDIDATE_REBOOT_PAGES:
        try:
            r = session.get(urljoin(base, p), headers={"User-Agent": UA, "Connection": "close"}, timeout=6)
        except requests.RequestException:
            continue
        if r.status_code != 200 or not (r.text or ""):
            continue
        hit = find_form(r.text)
        if hit:
            action, fields = hit
            reboot_url = urljoin(base, action) if action else urljoin(base, p)
            if not fields:
                fields = {"reboot": "Commit and Reboot"}
            else:
                for k in list(fields.keys()):
                    if any(x in k.lower() for x in ("reboot", "submit", "sys")) and not fields[k]:
                        fields[k] = "Commit and Reboot"
            try:
                rr = session.post(reboot_url, data=fields, headers={
                    "User-Agent": UA, "Origin": base, "Referer": urljoin(base, p),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Connection": "close",
                }, timeout=8, allow_redirects=True)
                if rr.status_code in (200, 204, 302, 303):
                    return True
            except requests.RequestException:
                pass

    endpoints = ["/reboot.asp", "/boaform/admin/formReboot", "/boaform/getform/formReboot", "/sysReboot.asp"]
    for ep in endpoints:
        for payload in CANDIDATE_REBOOT_PAYLOADS:
            try:
                rr = session.post(urljoin(base, ep), data=payload, headers={
                    "User-Agent": UA, "Origin": base, "Referer": urljoin(base, "/reboot.asp"),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Connection": "close",
                }, timeout=8, allow_redirects=True)
                if rr.status_code in (200, 204, 302, 303):
                    return True
            except requests.RequestException:
                continue
    return False

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="Tenda HG7 Router Rebooter (TUI)")
    parser.add_argument("--host", default="192.168.1.1", help="Router IP/host (default: 192.168.1.1)")
    parser.add_argument("--port", type=int, default=80, help="HTTP port (default: 80)")
    parser.add_argument("--user", default="admin", help="Username (default: admin)")
    parser.add_argument("--password", default="admin", help="Password (default: admin)")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear terminal at start")
    parser.add_argument("--down-timeout", type=int, default=90, help="Seconds to wait for router to go DOWN")
    parser.add_argument("--up-timeout", type=int, default=240, help="Seconds to wait for router to come BACK UP")
    parser.add_argument("--skip-ip", action="store_true", help="Skip public IP check/compare")
    args = parser.parse_args()

    if not args.no_clear:
        clear_screen()

    base = f"http://{args.host}:{args.port}" if args.port != 80 else f"http://{args.host}"
    banner("Tenda HG7  •  Router Rebooter")

    # --- Pre-flight: IPs ---
    prev_saved = read_last_ip()
    before_ip = None
    if not args.skip_ip:
        section("Detecting Public IP (before reboot)")
        info("Querying public IP services…")
        before_ip = get_public_ip()
        if before_ip:
            ok(f"Current public IP: {before_ip}")
            if prev_saved:
                info(f"Last saved IP: {prev_saved}")
        else:
            warn("Could not determine public IP (will try again after reboot).")

    # --- Login & Reboot ---
    section("Logging into Router UI (Tenda HG7)")
    session = requests.Session()
    session.auth = HTTPBasicAuth(args.user, args.password)
    session.cookies.set("userLanguage", "en")
    first_touch = first_ok(session, base, ["/reboot.asp", "/"])
    if first_touch:
        info("Session established.")

    logged = smart_login(session, base, args.user, args.password)
    if logged:
        ok("Login OK.")
    else:
        warn("Login not explicitly confirmed (HTTP Basic Auth set, continuing).")

    section("Submitting Reboot Request")
    ok_path = find_and_post_reboot(session, base)
    if ok_path:
        ok("Reboot request likely accepted.")
    else:
        warn("Could not confirm reboot submission (some devices accept silently).")

    section("Watching Router State")
    info("Waiting for router to go DOWN…")
    went_down = wait_until_down(args.host, args.port, args.down_timeout)
    if went_down:
        ok("Down detected.")
    else:
        warn("Did not observe it going down within timeout (it may still reboot).")

    info("Waiting for router to come BACK UP…")
    came_up = wait_until_up(args.host, args.port, args.up_timeout)
    if came_up:
        ok("Router reachable again.")
    else:
        warn("Router not reachable within expected time (still booting or IP changed).")

    # --- Post-flight: IPs ---
    if not args.skip_ip:
        section("Detecting Public IP (after reboot)")
        if came_up:
            sleep_progress(5, label="settling")
        after_ip = get_public_ip()
        if after_ip:
            ok(f"Public IP now: {after_ip}")
            if before_ip and after_ip != before_ip:
                info("Result: Public IP changed after reboot.")
            elif before_ip:
                info("Result: Public IP is unchanged.")
            else:
                info("Result: Public IP obtained post-reboot.")
            save_last_ip(after_ip)
        else:
            warn("Could not determine public IP after reboot.")

    section("Done")
    ok("All steps complete. You can re-run this script anytime.")

if __name__ == "__main__":
    main()
