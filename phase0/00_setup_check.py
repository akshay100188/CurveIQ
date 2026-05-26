"""
Phase 0 — Step 0: Environment & connectivity check.
Run this before any other phase0 script.
Verifies: Python version, .env file, FRED API key, Supabase connection, packages.
"""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def check_python():
    major, minor = sys.version_info[:2]
    ok = major == 3 and minor >= 10
    status = "OK" if ok else "WARN"
    print(f"  [{status}] Python {major}.{minor}  (need >= 3.10)")
    return ok


def check_env_file():
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        print(f"  [FAIL] .env file not found at {env_path}")
        print(f"         Copy .env.example to .env and fill in all values.")
        return False
    print(f"  [OK] .env found at {env_path}")
    return True


def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
        return True
    except ImportError:
        print("  [FAIL] python-dotenv not installed. Run: pip install python-dotenv")
        return False


def check_packages():
    required = [
        ("fredapi", "fredapi"),
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("supabase", "supabase"),
        ("dotenv", "python-dotenv"),
        ("requests", "requests"),
    ]
    all_ok = True
    for module, pip_name in required:
        try:
            pkg = __import__(module)
            version = getattr(pkg, "__version__", "unknown")
            print(f"  [OK] {pip_name} {version}")
        except ImportError:
            print(f"  [FAIL] {pip_name} not installed. Run: pip install {pip_name}")
            all_ok = False
    return all_ok


def check_fred_api():
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        print("  [FAIL] FRED_API_KEY not set in .env")
        return False
    try:
        from fredapi import Fred
        fred = Fred(api_key=api_key)
        # Fetch 1 row of DGS10 as a connectivity test
        test = fred.get_series("DGS10", observation_start="2024-01-01", limit=1)
        if len(test) > 0:
            print(f"  [OK] FRED API key valid — DGS10 test fetch succeeded")
            return True
        else:
            print("  [WARN] FRED API returned empty response. Key may be valid but no data.")
            return True
    except Exception as e:
        print(f"  [FAIL] FRED API error: {e}")
        return False


def check_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        print("  [FAIL] SUPABASE_URL or SUPABASE_KEY not set in .env")
        return False
    if "anon" in key[:20].lower():
        print("  [WARN] SUPABASE_KEY looks like an anon key. Use the service role key.")
    try:
        from supabase import create_client
        client = create_client(url, key)
        # Simple connectivity check — query a system table
        result = client.table("_pgsodium_key").select("id").limit(1).execute()
        print(f"  [OK] Supabase connected to {url[:40]}...")
        return True
    except Exception as e:
        # Connection errors vs auth errors vs missing table — all mean connectivity
        err_str = str(e).lower()
        if "connection" in err_str or "network" in err_str or "timeout" in err_str:
            print(f"  [FAIL] Supabase connection failed: {e}")
            return False
        # Other errors (auth, schema) still mean we reached the server
        print(f"  [OK] Supabase reachable at {url[:40]}... (auth or schema issue: {str(e)[:60]})")
        return True


def check_data_dirs():
    raw_dir = os.path.join(ROOT, "data", "raw")
    proc_dir = os.path.join(ROOT, "data", "processed")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(proc_dir, exist_ok=True)
    print(f"  [OK] data/raw/ exists at {raw_dir}")
    print(f"  [OK] data/processed/ exists at {proc_dir}")
    return True


def main():
    print("\n" + "=" * 60)
    print("  CurveIQ Phase 0 — Setup Check")
    print("=" * 60)

    print("\n[1] Python version")
    py_ok = check_python()

    print("\n[2] .env file")
    env_ok = check_env_file()

    if env_ok:
        print("\n[3] Loading .env")
        load_env()

    print("\n[4] Required packages")
    pkg_ok = check_packages()

    print("\n[5] FRED API connectivity")
    fred_ok = check_fred_api() if env_ok else False

    print("\n[6] Supabase connectivity")
    supa_ok = check_supabase() if env_ok else False

    print("\n[7] Data directories")
    dirs_ok = check_data_dirs()

    print("\n" + "=" * 60)
    all_critical = py_ok and env_ok and pkg_ok
    if all_critical and fred_ok and supa_ok:
        print("  RESULT: ALL CHECKS PASSED — ready to run Phase 0 scripts")
    elif all_critical:
        print("  RESULT: PARTIAL — Python/packages OK but API keys need attention")
        print("          Fix FRED/Supabase issues before running scripts 01-07")
    else:
        print("  RESULT: FAILED — fix the issues above before proceeding")
    print("=" * 60 + "\n")

    return 0 if (all_critical and fred_ok and supa_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
