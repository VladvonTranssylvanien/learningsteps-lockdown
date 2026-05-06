#!/usr/bin/env python3
"""
LearningSteps — deploy and test
Requires: Python 3.8+, Terraform >= 1.5, Azure CLI
Works on macOS, Linux, and Windows.

Usage:
  python3 deploy.py                         # interactive
  python3 deploy.py --password MyPass1      # skip password prompt
  python3 deploy.py --password MyPass1 --prefix myenv --location northeurope
"""

import argparse
import getpass
import json
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── colours ───────────────────────────────────────────────────────────────────

def _ansi_enabled():
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7
            )
        except Exception:
            return False
    return True

_USE_COLOUR = _ansi_enabled()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def info(msg):   print(f"\n{_c('1;33', '▶')} {msg}", flush=True)
def ok(msg):     print(f"  {_c('0;32', '✓')} {msg}", flush=True)
def warn(msg):   print(f"  {_c('1;33', '!')} {msg}", flush=True)
def error(msg):  print(f"  {_c('0;31', '✗')} {msg}", flush=True)
def header(msg): print(f"\n{_c('1;36', '═' * 60)}\n  {_c('1;36', msg)}\n{_c('1;36', '═' * 60)}", flush=True)

FAILURES = []

def fail(msg):
    error(msg)
    FAILURES.append(msg)

SCRIPT_DIR = Path(__file__).parent.resolve()

def _resolve_cmd(cmd):
    if isinstance(cmd, (list, tuple)) and cmd:
        binary = cmd[0]
        if isinstance(binary, str) and not Path(binary).is_absolute():
            resolved = shutil.which(binary)
            if resolved:
                return [resolved, *cmd[1:]]
    return cmd

def run(cmd, cwd=SCRIPT_DIR, **kwargs):
    cmd = _resolve_cmd(cmd)
    try:
        return subprocess.run(cmd, check=True, cwd=cwd, **kwargs)
    except FileNotFoundError as exc:
        error(f"Command not found: {cmd[0]}")
        raise SystemExit(1) from exc

def run_out(cmd, cwd=None):
    cmd = _resolve_cmd(cmd)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=cwd)
    except FileNotFoundError as exc:
        error(f"Command not found: {cmd[0]}")
        raise SystemExit(1) from exc
    except subprocess.CalledProcessError as exc:
        error(f"Command failed with exit code {exc.returncode}")
        if exc.stderr:
            print(f"  stderr: {exc.stderr}", file=sys.stderr)
        if exc.stdout:
            print(f"  stdout: {exc.stdout}", file=sys.stderr)
        raise SystemExit(1) from exc
    return r.stdout.strip()

def tf(cmd):
    """Run a terraform command with output, always from SCRIPT_DIR."""
    return run_out(cmd, cwd=SCRIPT_DIR)

def need(binary, install_hint):
    if not shutil.which(binary):
        error(f"'{binary}' not found. {install_hint}")
        sys.exit(1)

# ── step 1 — prerequisites ────────────────────────────────────────────────────

def check_prerequisites():
    info("Checking prerequisites")
    need("terraform", "Install from https://developer.hashicorp.com/terraform/install")
    ok("terraform found")
    need("az", "Install from https://learn.microsoft.com/en-us/cli/azure/install-azure-cli")
    ok("az CLI found")
    need("ssh-keygen", "Install OpenSSH (built-in on macOS/Linux; enable via Windows Optional Features)")
    ok("ssh-keygen found")

    try:
        account = run_out(["az", "account", "show", "--query", "{name:name}", "-o", "json"])
        parsed = json.loads(account)
        ok(f"Logged in — subscription: {parsed['name']}")
    except subprocess.CalledProcessError:
        warn("Not logged in to Azure — launching az login")
        run(["az", "login"])
        account = run_out(["az", "account", "show", "--query", "{name:name}", "-o", "json"])
        ok(f"Logged in — subscription: {json.loads(account)['name']}")

# ── step 2 — ssh key ──────────────────────────────────────────────────────────

def ensure_ssh_key():
    info("SSH key")
    key_path     = SCRIPT_DIR / ".learningsteps_key"
    pub_key_path = SCRIPT_DIR / ".learningsteps_key.pub"

    if pub_key_path.exists():
        ok(f"Using existing key: {pub_key_path.name}")
    else:
        run(["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", str(key_path), "-N", "", "-C", "learningsteps"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ok(f"Generated new key: {pub_key_path.name}")

    return pub_key_path.read_text().strip()

# ── step 3 — config ───────────────────────────────────────────────────────────

_URL_UNSAFE = set('@#$%&+=?/ \\\'\"')

def _validate_db_password(pw):
    if len(pw) < 8:
        return "must be at least 8 characters"
    if not any(c.isupper() for c in pw):
        return "must contain at least one uppercase letter"
    if not any(c.islower() for c in pw):
        return "must contain at least one lowercase letter"
    if not any(c.isdigit() for c in pw):
        return "must contain at least one digit"
    bad = [c for c in pw if c in _URL_UNSAFE]
    if bad:
        return f"must not contain {' '.join(set(bad))} (breaks the database connection URL)"
    return None

def collect_config(public_key, args):
    info("Configuration")

    tfvars = SCRIPT_DIR / "terraform.tfvars"
    if tfvars.exists() and args.password is None:
        reuse = input("  terraform.tfvars already exists. Reuse it? [Y/n]: ").strip().lower()
        if reuse in ("", "y", "yes"):
            ok("Reusing existing terraform.tfvars")
            return
    elif tfvars.exists() and args.password is not None:
        ok("Overwriting terraform.tfvars with provided flags")

    prefix   = args.prefix
    location = args.location

    if args.password is not None:
        pw = args.password
        err_msg = _validate_db_password(pw)
        if err_msg:
            error(f"--password rejected: {err_msg}")
            sys.exit(1)
    else:
        print()
        print("  Press Enter to accept the default shown in [brackets].")
        print()
        prefix   = input(f"  Resource name prefix [{prefix}]: ").strip() or prefix
        location = input(f"  Azure region         [{location}]: ").strip() or location
        while True:
            pw = getpass.getpass("  PostgreSQL password  (required): ")
            err_msg = _validate_db_password(pw)
            if err_msg:
                warn(f"Password rejected — {err_msg}")
                continue
            pw2 = getpass.getpass("  Confirm password:                ")
            if pw != pw2:
                warn("Passwords do not match, try again")
            else:
                break

    tfvars.write_text(
        f'prefix            = "{prefix}"\n'
        f'location          = "{location}"\n'
        f'vm_admin_username = "azureuser"\n'
        f'vm_admin_ssh_key  = "{public_key}"\n'
        f'db_admin_username = "psqladmin"\n'
        f'db_admin_password = "{pw}"\n'
        f'db_name           = "learning_journal"\n'
    )
    ok(f"terraform.tfvars written  (prefix={prefix}, location={location})")

# ── step 4 — deploy ───────────────────────────────────────────────────────────

def deploy():
    info("Terraform init")
    run(["terraform", "init", "-upgrade"])

    info("Terraform apply")
    try:
        run(["terraform", "apply", "-auto-approve"])
    except subprocess.CalledProcessError:
        error("terraform apply failed — see errors above")
        sys.exit(1)
    ok("Infrastructure deployed")

# ── step 5 — outputs ──────────────────────────────────────────────────────────

def read_outputs():
    info("Deployment summary")
    raw = tf(["terraform", "output", "-json"])
    out = json.loads(raw)

    vm_ip   = out["vm_public_ip"]["value"]
    rg      = out["resource_group_name"]["value"]
    db_fqdn = out["postgresql_fqdn"]["value"]
    ssh_cmd = out["ssh_command"]["value"]

    print(f"  VM IP   : {vm_ip}")
    print(f"  API     : http://{vm_ip}:8000/docs")
    print(f"  DB      : {db_fqdn}")
    print(f"  SSH     : {ssh_cmd} -i {SCRIPT_DIR / '.learningsteps_key'}")

    return vm_ip, rg, db_fqdn

# ── step 6 — azure checks ─────────────────────────────────────────────────────

def check_azure_resources(rg, db_fqdn):
    info("Azure resource checks")

    state = run_out(["az", "group", "show", "--name", rg,
                     "--query", "properties.provisioningState", "-o", "tsv"])
    if state == "Succeeded":
        ok(f"Resource group '{rg}'")
    else:
        fail(f"Resource group state: {state}")

    vm_name = run_out(["az", "vm", "list", "--resource-group", rg,
                       "--query", "[0].name", "-o", "tsv"])
    vm_state = run_out(["az", "vm", "show", "--resource-group", rg, "--name", vm_name,
                        "--query", "provisioningState", "-o", "tsv"])
    if vm_state == "Succeeded":
        ok(f"VM '{vm_name}' provisioned")
    else:
        fail(f"VM provisioning state: {vm_state}")

    power = run_out(["az", "vm", "get-instance-view",
                     "--resource-group", rg, "--name", vm_name,
                     "--query", "instanceView.statuses[?contains(code, 'PowerState')].displayStatus | [0]",
                     "-o", "tsv"])
    if power == "VM running":
        ok("VM is running")
    else:
        fail(f"VM power state: {power}")

    db_server = db_fqdn.split(".")[0]
    try:
        db_state = run_out(["az", "postgres", "flexible-server", "show",
                            "--resource-group", rg, "--name", db_server,
                            "--query", "state", "-o", "tsv"])
    except subprocess.CalledProcessError as exc:
        stderr = getattr(exc, "stderr", "") or ""
        if "ServerStoppedError" in stderr or "Stopped" in stderr:
            warn(f"PostgreSQL '{db_server}' is stopped. Start the server and retry checks.")
            return
        fail(f"Failed to query PostgreSQL server state: {stderr.strip() or exc}")
        return

    if db_state == "Ready":
        ok(f"PostgreSQL '{db_server}' ready")
    elif db_state == "Stopped":
        warn(f"PostgreSQL '{db_server}' is stopped. Start the server and retry checks.")
    else:
        fail(f"PostgreSQL state: {db_state}")

# ── step 7 — wait for api ─────────────────────────────────────────────────────

def wait_for_api(vm_ip):
    info("Waiting for API (cloud-init takes ~20 min)")
    api = f"http://{vm_ip}:8000"
    for _ in range(300):
        try:
            urllib.request.urlopen(f"{api}/docs", timeout=3)
            print()
            ok(f"API reachable at {api}")
            return api
        except Exception:
            print(".", end="", flush=True)
            time.sleep(5)
    print()
    fail("API did not respond after 25 min — SSH in and run: sudo journalctl -u learningsteps -f")
    return None

# ── step 8 — api tests ────────────────────────────────────────────────────────

def _request(method, url, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}

def run_api_tests(api):
    info("API tests")

    status, _ = _request("GET", f"{api}/entries")
    if status == 200:
        ok("GET /entries → 200")
    else:
        fail(f"GET /entries → {status}")

    status, body = _request("POST", f"{api}/entries",
                             {"work": "deploy test", "struggle": "none", "intention": "verify"})
    entry_id = body.get("entry", {}).get("id", "")
    if status == 200 and entry_id:
        ok(f"POST /entries → created id={entry_id}")
    else:
        fail(f"POST /entries → {status} {body}")

    status, body = _request("GET", f"{api}/entries")
    count = body.get("count", 0) if isinstance(body, dict) else 0
    if status == 200 and count >= 1:
        ok(f"GET /entries → {count} entry found")
    else:
        fail(f"GET /entries → empty after insert")

    if entry_id:
        status, _ = _request("PATCH", f"{api}/entries/{entry_id}", {"intention": "verified"})
        if status == 200:
            ok(f"PATCH /entries/{entry_id} → 200")
        else:
            fail(f"PATCH /entries/{entry_id} → {status}")

    status, _ = _request("DELETE", f"{api}/entries")
    if status == 200:
        ok("DELETE /entries (cleanup) → 200")
    else:
        fail(f"DELETE /entries → {status}")

# ── main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Deploy and test LearningSteps on Azure")
    p.add_argument("--password", help="PostgreSQL admin password (skips interactive prompt)")
    p.add_argument("--prefix",   default="learningsteps", help="Resource name prefix (default: learningsteps)")
    p.add_argument("--location", default="westeurope",    help="Azure region (default: westeurope)")
    return p.parse_args()

def main():
    args = parse_args()
    header("LearningSteps — Deploy and Test")

    check_prerequisites()
    public_key = ensure_ssh_key()
    collect_config(public_key, args)
    deploy()
    vm_ip, rg, db_fqdn = read_outputs()
    check_azure_resources(rg, db_fqdn)
    api = wait_for_api(vm_ip)
    if api:
        run_api_tests(api)

    print()
    if not FAILURES:
        print(_c("0;32", "  All checks passed. Deployment is working."))
    else:
        print(_c("0;31", f"  {len(FAILURES)} check(s) failed:"))
        for f in FAILURES:
            print(f"    - {f}")
        sys.exit(1)

if __name__ == "__main__":
    main()
