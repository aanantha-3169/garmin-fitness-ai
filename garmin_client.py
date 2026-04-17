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

import base64
import json
import logging
import os
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

# ── Singleton cache ───────────────────────────────────────────────────────────
_garmin_client = None

# ── Load .env ────────────────────────────────────────────────────────────────
load_dotenv()


def _get_tokenstore_path() -> Path:
    """Return the resolved token-store directory path."""
    raw = os.getenv("GARMIN_TOKENSTORE", "~/.garminconnect")
    return Path(raw).expanduser()


def _bootstrap_tokens_from_env(tokenstore: Path) -> bool:
    """Write token files from GARMIN_OAUTH1_TOKEN / GARMIN_OAUTH2_TOKEN env vars.

    On hosted environments (e.g. Render) there is no persistent filesystem.
    Store the token file contents as base64-encoded env vars and this function
    will decode and write them before the first login attempt.

    Returns True if at least one token file was written.
    """
    written = False
    for env_var, filename in (
        ("GARMIN_OAUTH1_TOKEN", "oauth1_token.json"),
        ("GARMIN_OAUTH2_TOKEN", "oauth2_token.json"),
    ):
        value = os.getenv(env_var)
        if not value:
            continue
        try:
            decoded = base64.b64decode(value + "==").decode("utf-8")
            json.loads(decoded)  # validate it's proper JSON before writing
            tokenstore.mkdir(parents=True, exist_ok=True)
            (tokenstore / filename).write_text(decoded)
            logger.info("📥 Wrote %s from env var %s.", filename, env_var)
            written = True
        except Exception as exc:
            logger.warning("Failed to decode %s: %s", env_var, exc)
    return written


def _bootstrap_tokens_from_supabase(tokenstore: Path) -> bool:
    """Write token files from Supabase (primary persistent store on Render).

    Checked before env vars — Supabase always holds the most recently
    refreshed tokens, while env vars may hold stale originals.

    Returns True if both token files were written successfully.
    """
    try:
        from db_manager import load_garmin_tokens
        tokens = load_garmin_tokens()
        if not tokens:
            logger.info("No Garmin tokens found in Supabase.")
            return False

        written = False
        for key, filename in (
            ("oauth1_token", "oauth1_token.json"),
            ("oauth2_token", "oauth2_token.json"),
        ):
            value = tokens.get(key)
            if not value:
                continue
            try:
                json.loads(value)  # validate JSON
                tokenstore.mkdir(parents=True, exist_ok=True)
                (tokenstore / filename).write_text(value)
                logger.info("📥 Wrote %s from Supabase.", filename)
                written = True
            except Exception as exc:
                logger.warning("Failed to write %s from Supabase: %s", filename, exc)

        return written
    except Exception as exc:
        logger.warning("Could not bootstrap tokens from Supabase: %s", exc)
        return False


def _persist_tokens_to_supabase(tokenstore: Path) -> None:
    """Read the current token files and save them to Supabase.

    Called after every successful login so that any tokens refreshed by
    garth (e.g. new OAuth2 access token) are immediately persisted.
    On Render the filesystem is wiped on restart — Supabase is the source
    of truth that survives across deployments.
    """
    try:
        from db_manager import save_garmin_tokens
        oauth1_path = tokenstore / "oauth1_token.json"
        oauth2_path = tokenstore / "oauth2_token.json"

        if not oauth1_path.exists() or not oauth2_path.exists():
            logger.warning("Token files missing — cannot persist to Supabase.")
            return

        oauth1_json = oauth1_path.read_text()
        oauth2_json = oauth2_path.read_text()

        # Validate before saving
        json.loads(oauth1_json)
        json.loads(oauth2_json)

        save_garmin_tokens(oauth1_json, oauth2_json)
    except Exception as exc:
        logger.warning("Could not persist tokens to Supabase: %s", exc)


def _dump_tokens(garmin, tokenstore: Path) -> None:
    """Write garth's current (possibly refreshed) tokens back to *tokenstore*.

    Handles API differences across garminconnect / garth versions:
      - newer garth: garmin.garth.dump(path)
      - fallback:    garmin.garth.save(path)
    Silently skips if neither is available so callers are never blocked.
    """
    try:
        if hasattr(garmin, "garth"):
            if hasattr(garmin.garth, "dump"):
                garmin.garth.dump(str(tokenstore))
            elif hasattr(garmin.garth, "save"):
                garmin.garth.save(str(tokenstore))
        else:
            logger.warning("garmin.garth not found — skipping token dump.")
    except Exception as exc:
        logger.warning("Could not dump refreshed tokens to disk: %s", exc)


def _login_with_tokens(tokenstore: Path):
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
        # Write any refreshed OAuth2 token back to disk so
        # _persist_tokens_to_supabase() reads the latest version.
        _dump_tokens(garmin, tokenstore)
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
        _dump_tokens(garmin, tokenstore)
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

    The client is cached for the lifetime of the process — Garmin rate-limits
    repeated credential logins, so we only authenticate once.

    Auth priority:
    1. Return cached client (already authenticated this process).
    2. Supabase token store  — most recently refreshed tokens (best for Render).
    3. Env var tokens        — base64-encoded fallback (GARMIN_OAUTH1/2_TOKEN).
    4. Local token files     — ~/.garminconnect (local dev only).
    5. Email/password login  — last resort (blocked by Garmin on cloud IPs).

    After every successful token-based login the tokens are written back to
    Supabase so that any auto-refresh by garth is immediately persisted.
    """
    global _garmin_client
    if _garmin_client is not None:
        return _garmin_client

    tokenstore = _get_tokenstore_path()

    # Attempt 1 — Supabase (persistent across Render restarts, always freshest)
    if _bootstrap_tokens_from_supabase(tokenstore):
        client = _login_with_tokens(tokenstore)
        if client is not None:
            _persist_tokens_to_supabase(tokenstore)
            _garmin_client = client
            return _garmin_client
        logger.warning("Supabase tokens failed — falling through to env vars.")

    # Attempt 2 — env vars (GARMIN_OAUTH1_TOKEN / GARMIN_OAUTH2_TOKEN)
    if _bootstrap_tokens_from_env(tokenstore):
        client = _login_with_tokens(tokenstore)
        if client is not None:
            _persist_tokens_to_supabase(tokenstore)  # promote env tokens to Supabase
            _garmin_client = client
            return _garmin_client
        logger.warning("Env var tokens failed — falling through to local files.")

    # Attempt 3 — local token files (dev machine only)
    client = _login_with_tokens(tokenstore)
    if client is not None:
        _persist_tokens_to_supabase(tokenstore)  # seed Supabase from local files
        _garmin_client = client
        return _garmin_client

    # Attempt 4 — credential login (last resort; blocked on Render by Garmin 429)
    logger.info("Falling back to credential-based login …")
    _garmin_client = _login_with_credentials(tokenstore)
    if _garmin_client is not None:
        _persist_tokens_to_supabase(tokenstore)
    return _garmin_client
