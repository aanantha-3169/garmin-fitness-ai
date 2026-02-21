"""
garmin_client.py — Garmin Connect session manager.

Handles authentication with token persistence so that subsequent runs
bypass 2FA and avoid triggering Garmin's rate limits.

Usage:
    from garmin_client import get_garmin_client

    client = get_garmin_client()
    if client:
        print(client.get_user_summary(date.today().isoformat()))
"""

import logging
import os
import sys
from getpass import getpass
from pathlib import Path

from dotenv import load_dotenv
from garth.exc import GarthHTTPError

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# ── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logging.getLogger("garminconnect").setLevel(logging.CRITICAL)

# ── Load .env ────────────────────────────────────────────────────────────────
load_dotenv()


def _get_tokenstore_path() -> Path:
    """Return the resolved token-store directory path."""
    raw = os.getenv("GARMIN_TOKENSTORE", "~/.garminconnect")
    return Path(raw).expanduser()


def _login_with_tokens(tokenstore: Path) :
    """Attempt to resume a session from previously saved tokens.

    Returns a fully authenticated Garmin client, or None if tokens are
    missing, expired, or otherwise unusable.
    """
    if not tokenstore.exists():
        logger.info("No token directory found at %s — skipping token login.", tokenstore)
        return None

    token_files = list(tokenstore.glob("*.json"))
    if not token_files:
        logger.info("Token directory exists but contains no .json files.")
        return None

    try:
        garmin = Garmin()
        garmin.login(str(tokenstore))
        logger.info("✅ Session resumed from saved tokens.")
        return garmin
    except FileNotFoundError:
        logger.warning("Token files not found during login — will re-authenticate.")
    except GarthHTTPError as exc:
        logger.warning("Token refresh failed (%s) — will re-authenticate.", exc)
    except GarminConnectAuthenticationError:
        logger.warning("Saved tokens are invalid/expired — will re-authenticate.")
    except GarminConnectConnectionError as exc:
        logger.error("Connection error while resuming session: %s", exc)

    return None


def _login_with_credentials(tokenstore: Path):
    """Authenticate with email/password (and MFA if required).

    On success the OAuth tokens are persisted to *tokenstore* so that
    future runs can call `_login_with_tokens` instead.
    """
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if not email:
        email = input("Garmin email: ")
    if not password:
        password = getpass("Garmin password: ")

    if not email or not password:
        logger.error("Email and password are required. Set GARMIN_EMAIL / GARMIN_PASSWORD in .env")
        return None

    try:
        garmin = Garmin(email=email, password=password, is_cn=False)
        garmin.login()

        # ── Persist tokens ───────────────────────────────────────────────
        tokenstore.mkdir(parents=True, exist_ok=True)
        garmin.garth.dump(str(tokenstore))
        logger.info("✅ Logged in successfully. Tokens saved to %s", tokenstore)
        return garmin

    except GarminConnectAuthenticationError as exc:
        logger.error("Authentication failed — check your email/password. (%s)", exc)
    except GarminConnectConnectionError as exc:
        logger.error("Connection error: %s", exc)
    except GarminConnectTooManyRequestsError as exc:
        logger.error("Too many requests — please wait before retrying. (%s)", exc)
    except GarthHTTPError as exc:
        logger.error("HTTP error during login: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error during login: %s", exc)

    return None


# ── Public API ───────────────────────────────────────────────────────────────

def get_garmin_client():
    """Return an authenticated Garmin client.

    1. Try to resume from saved tokens (fast, no 2FA).
    2. Fall back to email/password login (prompts for MFA if enabled).
    3. Return ``None`` if all attempts fail.
    """
    tokenstore = _get_tokenstore_path()

    # Attempt 1 — saved tokens
    client = _login_with_tokens(tokenstore)
    if client is not None:
        return client

    # Attempt 2 — credential-based login
    logger.info("Falling back to credential-based login …")
    return _login_with_credentials(tokenstore)
