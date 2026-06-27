#!/usr/bin/env python3
"""Launcher: kill old processes, start HTTP server, start bot, verify."""

import os, sys, subprocess, time, json, urllib.request

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = r"C:\Python314\python.exe"
LOG_DIR = os.path.join(BOT_DIR, "logs")
SERVER_PORT = 8765
HEALTH_URL = f"http://localhost:{SERVER_PORT}/health"
EXCLUDE = ["hermes", "AppData", "LightRAG", "launcher.py"]

os.makedirs(LOG_DIR, exist_ok=True)


def log(msg):
    print(f"  {msg}")
    sys.stdout.flush()


def kill_old_pythons():
    """Kill python.exe processes except excluded ones."""
    killed = 0
    try:
        out = subprocess.check_output(
            'wmic process where "name like \'%python%\'" get processid,commandline /format:csv',
            shell=True, timeout=15, stderr=subprocess.DEVNULL
        )
        for line in out.decode("utf-8", errors="replace").splitlines():
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            cmd = parts[-1] if len(parts) > 1 else ""
            pid_str = parts[-2] if len(parts) > 2 else ""
            if not pid_str.strip().isdigit():
                continue
            pid = int(pid_str.strip())
            if any(excl.lower() in cmd.lower() for excl in EXCLUDE):
                continue
            if not cmd.strip() or pid <= 0:
                continue
            subprocess.run(f'wmic process where "processid={pid}" delete',
                           shell=True, timeout=5, capture_output=True)
            killed += 1
            log(f"[KILL] PID {pid}")
    except subprocess.TimeoutExpired:
        log("[WARN] wmic timeout, skipping kill phase")
    except Exception as e:
        log(f"[WARN] kill error: {e}")
    return killed


def start_process(name, script, wait=4):
    """Start a background Python process. Captures output to a log file."""
    log_file = os.path.join(LOG_DIR, f"{name.lower().replace('/', '_')}.log")
    with open(log_file, "w") as lf:
        proc = subprocess.Popen(
            [PYTHON, os.path.join(BOT_DIR, script)],
            cwd=BOT_DIR,
            stdout=lf,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    log(f"[START] {name} (PID {proc.pid})")
    time.sleep(wait)
    return proc.pid, log_file


def health_check():
    """Verify HTTP server responds."""
    try:
        resp = urllib.request.urlopen(HEALTH_URL, timeout=5)
        data = json.loads(resp.read().decode())
        return data.get("status") == "ok"
    except Exception:
        return False


def product_count():
    """Get product count from API."""
    try:
        resp = urllib.request.urlopen(
            f"http://localhost:{SERVER_PORT}/api/products", timeout=5
        )
        return len(json.loads(resp.read().decode()))
    except Exception:
        return 0


def main():
    print("=" * 48)
    print("  3D MODELLIST CONSTRUCTOR — LAUNCHER")
    print("=" * 48)
    print()

    # Step 1: Kill old python.exe processes
    log("[1/4] Cleaning old processes...")
    killed = kill_old_pythons()
    log(f"Killed {killed} old process(es)")
    print()

    # Step 2: Start HTTP server
    log("[2/4] Starting HTTP server (port 8765)...")
    server_pid, server_log = start_process("HTTP-Server", "serve_webapp.py", wait=4)

    # Step 3: Verify server
    log("[3/4] Verifying server...")
    if health_check():
        count = product_count()
        log(f"[HEALTH OK] http://localhost:8765")
        log(f"[PRODUCTS] {count} items in catalog")
    else:
        log(f"[FAIL] Server not responding!")
        log(f"Check {server_log} for errors:")
        try:
            with open(server_log) as f:
                for line in f:
                    log(f"  {line.rstrip()}")
        except Exception:
            log("  (log file unreadable)")
        log("")
        log("Trying once more...")
        time.sleep(2)
        server_pid, server_log = start_process("HTTP-Server", "serve_webapp.py", wait=4)
        if health_check():
            count = product_count()
            log(f"[HEALTH OK] http://localhost:8765")
            log(f"[PRODUCTS] {count} items in catalog")
        else:
            log("[FATAL] Server won't start. Exiting.")
            sys.exit(1)
    print()

    # Step 4: Start bot
    log("[4/4] Starting Telegram bot @Jarvisvetogorbot...")
    bot_pid, bot_log = start_process("Jarvis-Bot", "main.py", wait=5)

    # Check bot log for errors
    try:
        with open(bot_log) as f:
            bot_out = f.read()
        if "Traceback" in bot_out or "Error" in bot_out:
            log("[WARN] Bot may have errors, check " + bot_log)
    except Exception:
        pass

    print()
    print("=" * 48)
    print("  READY! Open @Jarvisvetogorbot")
    print("  Type /shop to open the store")
    print("=" * 48)
    print()
    print("  Commands:")
    print("  /start  — main menu")
    print("  /shop   — online store")
    print("  /help   — help")
    print()
    print("  Logs: " + LOG_DIR)
    print("  To stop: close this window")
    print()

    # Keep running with periodic health check
    retries = 0
    try:
        while True:
            time.sleep(15)
            if health_check():
                retries = 0
            else:
                retries += 1
                if retries >= 4:
                    log("[WARN] Server unreachable for 1 min. Restarting...")
                    server_pid, server_log = start_process("HTTP-Server", "serve_webapp.py", wait=4)
                    if health_check():
                        log("[OK] Server recovered")
                        retries = 0
                    else:
                        log("[FAIL] Server still down")
    except KeyboardInterrupt:
        log("\nShutting down...")


if __name__ == "__main__":
    main()
