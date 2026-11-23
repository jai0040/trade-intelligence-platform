"""Interactive AngelOne SmartAPI session generator.

Prompts for your live 6-digit Authenticator OTP once, logs in,
and automatically writes the active ANGELONE_JWT_TOKEN to your .env file.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def main() -> int:
    env_vals = dotenv_values(ENV_PATH)
    api_key = (env_vals.get("ANGELONE_API_KEY") or "").strip()
    client_code = (env_vals.get("ANGELONE_CLIENT_CODE") or "").strip()
    pin = (env_vals.get("ANGELONE_PIN") or "").strip()
    totp_secret = (env_vals.get("ANGELONE_TOTP_SECRET") or "").strip()

    if not (api_key and client_code and pin):
        print("ERROR: Please make sure ANGELONE_API_KEY, ANGELONE_CLIENT_CODE, and ANGELONE_PIN are filled in .env")
        return 1

    otp = ""
    # Check if a 6-digit OTP or a TOTP secret is provided
    if len(totp_secret) == 6 and totp_secret.isdigit():
        otp = totp_secret
    elif len(totp_secret) > 6:
        # Generate dynamically via RFC 6238 TOTP
        try:
            sys.path.insert(0, str(ROOT / "trading-engine"))
            from data_providers.angelone_provider import generate_totp_code
            otp = generate_totp_code(totp_secret)
            print(f"Generated dynamic TOTP from secret: {otp}")
        except Exception as e:
            print(f"Could not generate TOTP from secret: {e}")

    if not otp:
        if len(sys.argv) > 1 and len(sys.argv[1].strip()) == 6:
            otp = sys.argv[1].strip()
        else:
            try:
                otp = input(f"Enter the 6-digit OTP from your Authenticator app for {client_code}: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nLogin cancelled.")
                return 1

    if len(otp) != 6 or not otp.isdigit():
        print(f"ERROR: Expected 6-digit numeric OTP, got '{otp}'")
        return 1

    print(f"Authenticating with AngelOne SmartAPI for client: {client_code} ...")
    url = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
    payload = {
        "clientcode": client_code,
        "password": pin,
        "totp": otp,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1",
        "X-ClientPublicIP": "152.58.35.168",
        "X-MACAddress": "fe80::216e:6507:4b9c:9045",
        "X-PrivateKey": api_key,
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Network error connecting to AngelOne: {e}")
        return 1

    if not data.get("status"):
        msg = data.get("message", "Unknown error")
        err_code = data.get("errorcode", "")
        print(f"LOGIN FAILED from AngelOne [{err_code}]: {msg}")
        return 1

    jwt = data.get("data", {}).get("jwtToken")
    if not jwt:
        print("Login succeeded but no jwtToken returned by AngelOne.")
        return 1

    print("\nLOGIN SUCCESSFUL!")
    print(f"Active Session JWT Token received (length {len(jwt)}).")
    
    # Save to .env
    set_key(str(ENV_PATH), "ANGELONE_JWT_TOKEN", jwt)
    print(f"Saved active ANGELONE_JWT_TOKEN to {ENV_PATH.name}!")
    print("Your backend will now use this active session to stream live quotes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
