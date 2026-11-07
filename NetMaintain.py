"""
NetMaintain.py  —  Run via LAUNCH.bat (as Administrator)
"""

import os, sys, re, time, ctypes, socket, subprocess, threading, getpass
import urllib.request, json, shutil, glob

# ── requests ────────────────────────────────────────────────────────────
try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"], check=False)
    import requests
    from requests.auth import HTTPBasicAuth

import html as html_mod
from urllib.parse import urljoin

# ════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════
# Router connection (Fixes #1). No credentials are hardcoded here.
# Username/password come from TENDA_ROUTER_USER / TENDA_ROUTER_PASS, or an
# interactive prompt -- never from a built-in default. The host may be set
# with TENDA_ROUTER_HOST (default 192.168.1.1).
ROUTER_HOST = os.environ.get("TENDA_ROUTER_HOST", "192.168.1.1")

def get_router_credentials():
    user = os.environ.get("TENDA_ROUTER_USER")
    password = os.environ.get("TENDA_ROUTER_PASS")
    if not user:
        user = input("Router username: ").strip()
    if not user:
        print("ERROR: No router username given (TENDA_ROUTER_USER or prompt).")
        sys.exit(1)
    if not password:
        password = getpass.getpass("Router password: ")
    if not password:
        print("ERROR: No router password given (TENDA_ROUTER_PASS or prompt).")
        sys.exit(1)
    return user, password

def resolve_router_base(host):
    """Prefer HTTPS; fall back to plain HTTP only with an explicit warning.

    Most Tenda HG7 firmware serves HTTP only, so the HTTPS probe will
    usually fail -- but credentials must never silently go over HTTP when
    the router does offer HTTPS. verify=False is used because these
    devices use self-signed certificates; the connection is still
    encrypted, and this stays on the LAN.
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    for scheme in ("https", "http"):
        url = f"{scheme}://{host}"
        try:
            requests.get(url, timeout=3, verify=False)
            if scheme == "http":
                warn("Router did not answer over HTTPS; using plain HTTP on the LAN -- the password will be sent unencrypted.")
            return url
        except Exception:
            continue
    warn("Router did not answer over HTTPS or HTTP; continuing with plain HTTP.")
    return f"http://{host}"

DNS_GOOGLE = {
    "name": "Google",
    "ipv4": ["8.8.8.8", "8.8.4.4"],
    "ipv6": ["2001:4860:4860::8888", "2001:4860:4860::8844"],
}
DNS_CLOUDFLARE = {
    "name": "Cloudflare",
    "ipv4": ["1.1.1.1", "1.0.0.1"],
    "ipv6": ["2606:4700:4700::1111", "2606:4700:4700::1001"],
}

STATE_FILE = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "NM_dns_state.txt")
DIR = os.path.dirname(os.path.abspath(__file__))

# ════════════════════════════════════════════════════════════════════════
# ANSI / OhMyPosh-style colours
# ════════════════════════════════════════════════════════════════════════
os.system("")  # enable ANSI on Windows 10+

# Nord palette
N0  = "\033[38;2;46;52;64m"      # nord0  dark bg text
N1  = "\033[38;2;59;66;82m"
N3  = "\033[38;2;76;86;106m"     # nord3
N4  = "\033[38;2;216;222;233m"   # nord4  light
N6  = "\033[38;2;236;239;244m"   # nord6  bright white
N7  = "\033[38;2;143;188;187m"   # nord7  teal
N8  = "\033[38;2;136;192;208m"   # nord8  light blue
N9  = "\033[38;2;129;161;193m"   # nord9  blue
N10 = "\033[38;2;94;129;172m"    # nord10 dark blue
N11 = "\033[38;2;191;97;106m"    # nord11 red
N12 = "\033[38;2;208;135;112m"   # nord12 orange
N13 = "\033[38;2;235;203;139m"   # nord13 yellow
N14 = "\033[38;2;163;190;140m"   # nord14 green
N15 = "\033[38;2;180;142;173m"   # nord15 purple

BG_N0  = "\033[48;2;46;52;64m"
BG_N1  = "\033[48;2;59;66;82m"
BG_N2  = "\033[48;2;67;76;94m"
BG_N3  = "\033[48;2;76;86;106m"
BG_N7  = "\033[48;2;143;188;187m"
BG_N9  = "\033[48;2;129;161;193m"
BG_N10 = "\033[48;2;94;129;172m"
BG_N11 = "\033[48;2;191;97;106m"
BG_N12 = "\033[48;2;208;135;112m"
BG_N13 = "\033[48;2;235;203;139m"
BG_N14 = "\033[48;2;163;190;140m"
BG_N15 = "\033[48;2;180;142;173m"

BOLD  = "\033[1m"
RS    = "\033[0m"

# Powerline chars
PL_R  = "\ue0b0"   # solid right arrow  
PL_RL = "\ue0b2"   # solid right arrow (left-pointing, for right segments)
PL_TR = "\ue0b4"   # thin right arrow
SEP   = "\ue0b1"   # thin separator

# Nerd Font icons
ICO_NET    = "\uf6ff"   # network
ICO_DNS    = "\uf233"   # server
ICO_IP     = "\uf0ac"   # globe
ICO_CLEAN  = "\uf1f8"   # trash
ICO_ROUTER = "\uf233"   # server (fallback for router)
ICO_OK     = "\uf058"   # check circle
ICO_WARN   = "\uf071"   # warning
ICO_INFO   = "\uf05a"   # info
ICO_PC     = "\uf108"   # desktop
ICO_REBOOT = "\uf021"   # refresh
ICO_TIME   = "\uf017"   # clock
ICO_STAR   = "\uf005"   # star
ICO_ARROW  = "\uf0a9"   # arrow right

W = 78

def cls():
    os.system("cls")

def println(s=""):
    print(s)

def pad(s, width):
    # strip ANSI for length calc
    clean = re.sub(r'\033\[[^m]*m', '', s)
    clean = re.sub(r'[\ue0b0\ue0b1\ue0b2\ue0b4\uf6ff\uf233\uf0ac\uf1f8\uf6d1\uf058\uf071\uf05a\uf108\uf021\uf017\uf005\uf0a9]', ' ', clean)
    pad_needed = max(0, width - len(clean))
    return s + " " * pad_needed

# ── OhMyPosh-style header ───────────────────────────────────────────────
def print_header():
    t = time.strftime("%H:%M:%S")
    d = time.strftime("%a %d %b %Y")

    # Top row — powerline segments
    seg1 = f"{BG_N10}{BOLD}{N6}  {ICO_STAR} NetMaintain {RS}"
    seg2 = f"{BG_N3}{N10}{PL_R}{RS}{BG_N3}{N6}  Network Maintenance Tool {RS}"
    seg3 = f"{BG_N1}{N3}{PL_R}{RS}{BG_N1}{N8}  {ICO_TIME} {d}  {t} {RS}"
    seg4 = f"{N1}{PL_R}{RS}"
    print(f"\n{seg1}{seg2}{seg3}{seg4}")

    # Divider
    print(f"{N3}  {'─'*74}{RS}")
    print()

# ── Step banner (OhMyPosh segment style) ───────────────────────────────
def step_banner(n, icon, title, color_bg, color_fg):
    num_seg  = f"{color_bg}{BOLD}{N6}  {icon} [{n}] {RS}"
    title_seg= f"{BG_N1}{color_fg}{PL_R}{RS}{BG_N1}{N4}  {title} {RS}"
    end_seg  = f"{N1}{PL_R}{RS}"
    print(f"\n{num_seg}{title_seg}{end_seg}")
    print(f"{N3}  {'·'*70}{RS}")

def ok(msg):
    print(f"  {N14}{ICO_OK}{RS}  {N6}{msg}{RS}")

def warn(msg):
    print(f"  {N13}{ICO_WARN}{RS}  {N13}{msg}{RS}")

def info(msg):
    print(f"  {N8}{ICO_INFO}{RS}  {N4}{msg}{RS}")

def step_end():
    print(f"{N3}  {'─'*74}{RS}")

def result_row(label, val, color=None):
    color = color or N4
    label_s = f"{N8}{label:<18}{RS}"
    print(f"  {N3}│{RS}  {label_s}  {color}{val}{RS}")

def result_divider():
    print(f"  {N3}├{'─'*68}┤{RS}")

def result_top():
    print(f"\n  {N3}╭{'─'*68}╮{RS}")

def result_bot():
    print(f"  {N3}╰{'─'*68}╯{RS}")

def result_section(title, icon):
    print(f"  {N3}│{RS}  {N10}{BOLD}{icon}  {title}{RS}")
    print(f"  {N3}│{RS}")

# ════════════════════════════════════════════════════════════════════════
# ADMIN CHECK
# ════════════════════════════════════════════════════════════════════════
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# ════════════════════════════════════════════════════════════════════════
# STEP 1 — TEMP CLEAN
# ════════════════════════════════════════════════════════════════════════
CLEAN_PATHS = [
    os.environ.get("TEMP", ""),
    os.environ.get("TMP", ""),
    "C:\\Windows\\Temp",
    "C:\\Windows\\Prefetch",
    os.path.expanduser("~\\AppData\\Local\\Temp"),
    os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\INetCache"),
    os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\Temporary Internet Files"),

    os.path.expanduser("~\\AppData\\Local\\CrashDumps"),
    "C:\\Windows\\SoftwareDistribution\\Download",
    "C:\\$Recycle.Bin",
]

def folder_size_mb(path):
    total = 0
    try:
        for dirpath, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except:
                    pass
    except:
        pass
    return round(total / (1024 * 1024), 1)

def clean_folder(path):
    freed = 0
    if not path or not os.path.exists(path):
        return 0
    try:
        items = os.listdir(path)
    except PermissionError:
        return 0
    for item in items:
        fp = os.path.join(path, item)
        try:
            size = folder_size_mb(fp) if os.path.isdir(fp) else os.path.getsize(fp) / (1024*1024)
            if os.path.isfile(fp) or os.path.islink(fp):
                os.remove(fp)
                freed += size
            elif os.path.isdir(fp):
                shutil.rmtree(fp, ignore_errors=True)
                freed += size
        except:
            pass
    return round(freed, 1)

def pc_clean():
    step_banner(1, ICO_CLEAN, "Deep Temp Clean & IP Reset", BG_N15, N15)

    total_freed = 0
    seen = set()
    for p in CLEAN_PATHS:
        p = os.path.normpath(p) if p else ""
        if not p or p in seen or not os.path.exists(p):
            continue
        seen.add(p)
        before = folder_size_mb(p)
        freed  = clean_folder(p)
        total_freed += freed
        short = p if len(p) < 48 else "..." + p[-45:]
        ok(f"{short}  {N13}freed {freed} MB{RS}")

    print()
    info(f"Total freed: {N14}{BOLD}{total_freed} MB{RS}")
    print()

    info("Resetting network stack...")
    for cmd in ["ipconfig /release", "ipconfig /flushdns",
                "netsh winsock reset", "netsh int ip reset", "ipconfig /renew"]:
        subprocess.run(cmd, shell=True, capture_output=True)
    ok("Network stack reset.")

    info("Closing browsers...")
    closed = []
    for proc in ["chrome.exe","msedge.exe","firefox.exe","brave.exe","opera.exe"]:
        r = subprocess.run(f"taskkill /f /im {proc}", shell=True, capture_output=True)
        if r.returncode == 0:
            closed.append(proc.replace(".exe",""))
    ok(f"Browsers closed: {', '.join(closed) if closed else 'none running'}")
    step_end()
    return total_freed

# ════════════════════════════════════════════════════════════════════════
# PUBLIC IP
# ════════════════════════════════════════════════════════════════════════
def get_public_ip():
    for url in ["https://api.ipify.org?format=json", "https://checkip.amazonaws.com"]:
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                data = r.read().decode().strip()
                try:
                    return json.loads(data)["ip"]
                except:
                    return data
        except:
            pass
    return "unavailable"

# ════════════════════════════════════════════════════════════════════════
# ROUTER REBOOT (inline)
# ════════════════════════════════════════════════════════════════════════
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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

def find_form(html_text, action_contains=None):
    if not html_text:
        return None
    for form_m in re.finditer(r"(?is)<form\b[^>]*>.*?</form>", html_text):
        form_html = form_m.group(0)
        act_m = re.search(r'(?is)\baction\s*=\s*["\']?([^"\'>\s]+)', form_html)
        action = act_m.group(1).strip() if act_m else ""
        if action_contains and action_contains.lower() not in action.lower():
            continue
        fields = {}
        for inp in re.finditer(r'(?is)<input\b[^>]*>', form_html):
            nm = re.search(r'(?is)\bname\s*=\s*["\']?([^"\'>\s]+)', inp.group(0))
            vm = re.search(r'(?is)\bvalue\s*=\s*["\']?([^"\'>]*)', inp.group(0))
            val = html_mod.unescape(vm.group(1)) if vm else ""
            if nm:
                name = html_mod.unescape(nm.group(1))
                fields[name] = val
            else:
                # Capture submit inputs without a name attribute (e.g. Tenda HG7 Commit and Reboot button)
                inp_lower = inp.group(0).lower()
                if "submit" in inp_lower or "inner_btn" in inp_lower:
                    fields["reboot"] = val or "Commit and Reboot"
        return action, fields
    return None

def router_reboot():
    router_user, router_pass = get_router_credentials()
    router_host = resolve_router_base(ROUTER_HOST)
    step_banner(3, ICO_ROUTER, f"Router Reboot  {ROUTER_HOST} (Tenda HG7)", BG_N12, N12)
    session = requests.Session()
    # Support HTTP Basic Auth (used by Tenda HG7 and many router web UIs)
    session.auth = HTTPBasicAuth(router_user, router_pass)
    session.cookies.set("userLanguage", "en")

    info("Attempting authentication (HTTP Basic & Form Login)...")
    for p in CANDIDATE_ROOTS:
        try:
            r = session.get(urljoin(router_host, p), headers={"User-Agent": UA}, timeout=6, allow_redirects=True)
            hit = find_form(r.text, action_contains="login")
            if hit:
                action, fields = hit
                for k in list(fields):
                    if "user" in k.lower() or "name" in k.lower(): fields[k] = router_user
                    if "pwd"  in k.lower() or "pass" in k.lower(): fields[k] = router_pass
                session.post(urljoin(router_host, action), data=fields,
                    headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
                    timeout=6, allow_redirects=True)
                break
        except: pass

    ok("Authentication session initialized.")
    info("Sending reboot command to Tenda HG7...")

    rebooted = False
    for p in CANDIDATE_REBOOT_PAGES:
        try:
            r = session.get(urljoin(router_host, p), headers={"User-Agent": UA}, timeout=6)
            if r.status_code != 200 or not r.text: continue
            hit = find_form(r.text)
            if hit:
                action, fields = hit
                target_url = urljoin(router_host, action) if action else urljoin(router_host, p)
                if not fields:
                    fields = {"reboot": "Commit and Reboot"}
                rr = session.post(target_url, data=fields,
                    headers={"User-Agent": UA, "Referer": urljoin(router_host, p), "Content-Type": "application/x-www-form-urlencoded"},
                    timeout=8, allow_redirects=True)
                if rr.status_code in (200, 204, 302, 303):
                    rebooted = True
                    break
        except: pass

    if not rebooted:
        # Fallback direct POST to common Tenda reboot endpoints
        endpoints = ["/reboot.asp", "/boaform/admin/formReboot", "/boaform/getform/formReboot", "/sysReboot.asp"]
        for ep in endpoints:
            for payload in CANDIDATE_REBOOT_PAYLOADS:
                try:
                    rr = session.post(urljoin(router_host, ep), data=payload,
                        headers={"User-Agent": UA, "Referer": urljoin(router_host, "/reboot.asp"), "Content-Type": "application/x-www-form-urlencoded"},
                        timeout=8, allow_redirects=True)
                    if rr.status_code in (200, 204, 302, 303):
                        rebooted = True
                        break
                except: pass
            if rebooted: break

    if rebooted:
        ok("Reboot request accepted.")
    else:
        warn("Could not confirm response — monitoring connection state...")

    info("Waiting for router to go DOWN...")
    if wait_until_down():
        ok("Router is DOWN.")
    else:
        warn("Router didn't go down within 90s.")

    info("Waiting for router to come back UP...")
    if wait_until_up():
        ok("Router is back ONLINE.")
    else:
        warn("Router didn't respond within 4 min.")

    step_end()

# ════════════════════════════════════════════════════════════════════════
# DNS
# ════════════════════════════════════════════════════════════════════════
def get_current_dns():
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {$_.ServerAddresses} | Select-Object -First 1).ServerAddresses -join ' / '"],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "unknown"
    except:
        return "unknown"

def set_dns(ipv4, ipv6):
    v4 = "','".join(ipv4)
    v6 = "','".join(ipv6)
    script = f"""
$adapters = Get-NetAdapter | Where-Object {{ $_.Status -eq 'Up' }}
foreach ($a in $adapters) {{
    try {{
        Set-DnsClientServerAddress -InterfaceAlias $a.Name -ServerAddresses ('{v4}')
        Write-Host "  OK  IPv4 on $($a.Name)"
    }} catch {{ Write-Host "  WARN IPv4 failed $($a.Name)" }}
    try {{
        Set-DnsClientServerAddress -InterfaceAlias $a.Name -ServerAddresses ('{v6}')
        Write-Host "  OK  IPv6 on $($a.Name)"
    }} catch {{ Write-Host "  WARN IPv6 skipped $($a.Name)" }}
}}
"""
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True, timeout=30)
    for line in r.stdout.strip().splitlines():
        if line.strip():
            if "OK" in line:
                ok(line.replace("  OK  ", ""))
            else:
                warn(line.replace("  WARN ", ""))

def get_adapter_dns():
    script = """
$adapters = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' }
foreach ($a in $adapters) {
    $dns = (Get-DnsClientServerAddress -InterfaceAlias $a.Name -ErrorAction SilentlyContinue).ServerAddresses -join ' / '
    Write-Host "$($a.Name)|$dns"
}
"""
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True, timeout=15)
    results = []
    for line in r.stdout.strip().splitlines():
        if "|" in line:
            name, dns = line.split("|", 1)
            results.append((name.strip(), dns.strip()))
    return results

# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════
def main():
    if not is_admin():
        print("ERROR: Please run as Administrator!")
        input("Press Enter to exit...")
        sys.exit(1)

    cls()
    print_header()

    # DNS toggle
    last = "cloudflare"
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            last = f.read().strip().lower()
    new_dns      = DNS_CLOUDFLARE if last == "google" else DNS_GOOGLE
    old_dns_name = "Google"       if last == "google" else "Cloudflare"
    with open(STATE_FILE, "w") as f:
        f.write(new_dns["name"].lower())

    # ── 1. Deep clean ───────────────────────────────────────────────────
    total_freed = pc_clean()

    # ── 2. Old public IP ────────────────────────────────────────────────
    step_banner(2, ICO_IP, "Public IP  (before reboot)", BG_N9, N9)
    info("Fetching current public IP...")
    old_public_ip = get_public_ip()
    ok(f"Old IP  →  {N13}{BOLD}{old_public_ip}{RS}")
    step_end()

    # ── Capture old DNS ─────────────────────────────────────────────────
    old_dns_val = get_current_dns()

    # ── 3. Router reboot ────────────────────────────────────────────────
    router_reboot()

    # ── 4. New public IP ────────────────────────────────────────────────
    step_banner(4, ICO_IP, "Public IP  (after reboot)", BG_N9, N9)
    info("Fetching new public IP...")
    new_public_ip = get_public_ip()
    ok(f"New IP  →  {N14}{BOLD}{new_public_ip}{RS}")
    step_end()

    # ── 5. DNS switch ───────────────────────────────────────────────────
    step_banner(5, ICO_DNS, f"DNS Switch  →  {new_dns['name']}", BG_N7, N7)
    info(f"IPv4: {new_dns['ipv4'][0]}  /  {new_dns['ipv4'][1]}")
    info(f"IPv6: {new_dns['ipv6'][0]}")
    print()
    set_dns(new_dns["ipv4"], new_dns["ipv6"])
    subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)
    ok("DNS cache flushed.")
    step_end()

    # ── Adapter info ────────────────────────────────────────────────────
    adapters = get_adapter_dns()

    # ════════════════════════════════════════════════════════════════════
    # FINAL RESULT — OhMyPosh box
    # ════════════════════════════════════════════════════════════════════
    ip_changed = old_public_ip != new_public_ip and "unavailable" not in new_public_ip

    println()

    # Result header segment
    h1 = f"{BG_N10}{BOLD}{N6}  {ICO_STAR} FINAL RESULT SUMMARY {RS}"
    h2 = f"{N10}{PL_R}{RS}"
    print(f"\n{h1}{h2}\n")

    result_top()

    # PUBLIC IP
    result_section("PUBLIC IP", ICO_IP)
    ip_tag = f"{N14}CHANGED {ICO_OK}{RS}" if ip_changed else f"{N13}SAME{RS}"
    result_row("Before", old_public_ip, N13)
    result_row("After",  new_public_ip,  N14)
    result_row("Status", ip_tag if ip_changed else f"{N13}No change{RS}")
    result_divider()

    # DNS
    result_section("DNS SERVERS", ICO_DNS)
    result_row("Before (IPv4)", f"{old_dns_val}  [{old_dns_name}]", N13)
    result_row("After  (IPv4)", f"{new_dns['ipv4'][0]} / {new_dns['ipv4'][1]}  [{new_dns['name']}]", N14)
    result_row("After  (IPv6)", new_dns['ipv6'][0], N14)
    result_divider()

    # TEMP CLEAN
    result_section("TEMP CLEAN", ICO_CLEAN)
    result_row("Total Freed", f"{N14}{BOLD}{total_freed} MB{RS}")
    result_divider()

    # ADAPTERS
    result_section("ADAPTER DNS", ICO_NET)
    for name, dns in adapters:
        result_row(name, dns, N8)

    result_bot()

    # ── Reboot prompt ───────────────────────────────────────────────────
    step_banner(6, ICO_REBOOT, "Reboot PC", BG_N11, N11)
    print(f"  {N13}Restart recommended to apply all network changes.{RS}\n")

    answered = [None]

    def countdown():
        for i in range(30, 0, -1):
            if answered[0] is not None:
                break
            print(f"\r  {N8}{ICO_ARROW}  Reboot now? {N6}[Y]{RS} Yes  {N6}[N]{RS} Skip  "
                  f"{N3}(auto-skip in {i}s)  {RS}", end="", flush=True)
            time.sleep(1)
        if answered[0] is None:
            answered[0] = "n"

    t = threading.Thread(target=countdown, daemon=True)
    t.start()

    import msvcrt
    while answered[0] is None:
        if msvcrt.kbhit():
            key = msvcrt.getwch().lower()
            if key in ("y", "n"):
                answered[0] = key
                break
        time.sleep(0.05)

    print("\n")
    if answered[0] == "y":
        print(f"  {N11}{BOLD}Rebooting in 3 seconds...{RS}")
        step_end()
        time.sleep(3)
        subprocess.run("shutdown /r /t 0", shell=True)
    else:
        print(f"  {N14}Skipped. Restart manually when ready.{RS}")
        step_end()
        println()

        # Final goodbye powerline
        bye1 = f"{BG_N14}{BOLD}{N0}  {ICO_OK} All done!  {RS}"
        bye2 = f"{BG_N1}{N14}{PL_R}{RS}{BG_N1}{N4}  NetMaintain  {RS}"
        bye3 = f"{N1}{PL_R}{RS}"
        print(f"{bye1}{bye2}{bye3}\n")
        input("  Press Enter to exit...")

if __name__ == "__main__":
    main()