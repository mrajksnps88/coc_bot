"""Quick ADB diagnostic script."""
import subprocess
import sys

print("=" * 50)
print("ADB DIAGNOSTIC")
print("=" * 50)

# 1. Check adb version
print("\n[1] ADB Version:")
try:
    r = subprocess.run(["adb", "version"], capture_output=True, text=True)
    print(r.stdout.strip())
except Exception as e:
    print(f"  ERROR: {e}")

# 2. Check device list
print("\n[2] ADB Devices:")
try:
    r = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
    print(r.stdout.strip())
except Exception as e:
    print(f"  ERROR: {e}")

# 3. Try screencap directly via adb command line
print("\n[3] Testing screencap via ADB command line:")
try:
    r = subprocess.run(
        ["adb", "-s", "localhost:6520", "shell", "screencap", "-p"],
        capture_output=True, timeout=10
    )
    if r.returncode == 0 and len(r.stdout) > 100:
        print(f"  SUCCESS! Got {len(r.stdout)} bytes of image data.")
    else:
        print(f"  FAILED. Return code: {r.returncode}")
        print(f"  stdout bytes: {len(r.stdout)}")
        print(f"  stderr: {r.stderr.decode('utf-8', errors='replace')[:500]}")
except subprocess.TimeoutExpired:
    print("  TIMEOUT after 10 seconds.")
except Exception as e:
    print(f"  ERROR: {e}")

# 4. Try via ppadb
print("\n[4] Testing via ppadb library:")
try:
    from ppadb.client import Client as AdbClient
    client = AdbClient(host="127.0.0.1", port=5037)
    devices = client.devices()
    print(f"  Found {len(devices)} device(s):")
    for d in devices:
        print(f"    - Serial: {d.serial}")
        try:
            out = d.shell("echo hello")
            print(f"      Shell test: {out.strip()}")
        except Exception as e:
            print(f"      Shell test FAILED: {e}")
except Exception as e:
    print(f"  ERROR: {e}")

# 5. Try alternate ports
print("\n[5] Scanning common emulator ports:")
for port in [5555, 5554, 6520, 6521, 58526]:
    try:
        r = subprocess.run(
            ["adb", "connect", f"localhost:{port}"],
            capture_output=True, text=True, timeout=3
        )
        status = r.stdout.strip()
        if "refused" not in status and "unable" not in status:
            print(f"  Port {port}: {status}")
    except:
        pass

print("\n" + "=" * 50)
print("DONE")
print("=" * 50)
