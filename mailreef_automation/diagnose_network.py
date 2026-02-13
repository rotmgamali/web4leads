import os
import socket
import sys
import requests

def check_connection(host, port, timeout=10):
    """Try to open a TCP connection to host:port."""
    target_desc = f"{host}:{port}"
    print(f"   Testing connectivity to {target_desc}...", end='', flush=True)
        
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        print(" ✅ SUCCESS")
        return True
    except (socket.timeout, TimeoutError):
        print(" ❌ TIMEOUT")
    except ConnectionRefusedError:
        print(" ❌ REFUSED")
    except OSError as e:
        print(f" ❌ UNREACHABLE ({e})")
    except Exception as e:
        print(f" ❌ ERROR: {e}")
    return False

def run_diagnostics():
    print("\n" + "="*50)
    print("🩺 MAILREEF API DIAGNOSTICS (API-FIRST)")
    print("="*50)
    
    api_host = "api.mailreef.com"
    
    # 1. Environment Check
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"📍 Container Hostname: {hostname}")
        print(f"📍 Container IP: {local_ip}")
    except Exception as e:
        print(f"⚠️ Could not get local env details: {e}")

    # 2. DNS Resolution
    print(f"\n🔍 DNS Resolution: {api_host}")
    try:
        ip = socket.gethostbyname(api_host)
        print(f"   ✅ RESOLVED: {api_host} -> {ip}")
    except socket.gaierror as e:
        print(f"   ❌ DNS FAILURE: Could not resolve {api_host} ({e})")
        return

    # 3. Direct API Reachability (Port 443)
    print("\n🔌 Connectivity Check (HTTPS):")
    check_connection(api_host, 443)
    
    # 4. Functional API Check
    print("\n🧪 Functional API Check:")
    try:
        api_key = os.getenv("MAILREEF_API_KEY")
        if not api_key:
            print("   ⚠️ MAILREEF_API_KEY not set, skipping functional check.")
        else:
            # Mask key for logs
            masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
            print(f"   Using API Key: {masked_key}")
            
            # Using the same auth as MailreefClient
            # Endpoint requires both 'page' and 'display' parameters
            r = requests.get(f"https://{api_host}/domains", params={"page": 1, "display": 1}, auth=(api_key, ''), timeout=15)
            if r.status_code == 200:
                print("   ✅ API AUTH SUCCESS: Successfully fetched domains.")
            else:
                print(f"   ❌ API AUTH FAILURE: HTTP {r.status_code} - {r.text[:100]}")
    except Exception as e:
        print(f"   ❌ API ERROR: {e}")

    # 5. SMTP Baseline (Historical context)
    print("\n🚿 SMTP Baseline (Expected to fail/block in cloud):")
    check_connection(api_host, 465, timeout=5)
    
    print("="*50 + "\n")

if __name__ == "__main__":
    run_diagnostics()
