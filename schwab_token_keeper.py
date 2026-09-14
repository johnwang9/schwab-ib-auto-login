#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Schwab 7-day refresh token auto-renewal (Token Keeper).

The only existing file it writes is the runtime data store .schwabdev/tokens.db (automatically
backed up to .schwabdev/keeper_backup/ before writing, and auto-rolled back if the
self-check fails). The app side picks up the new token via schwabdev's
"updated elsewhere" mechanism (tokens.py _update_access_token re-reads the db inside an
exclusive transaction before every refresh): no restart needed while the app is running,
and the switch happens within 30 minutes at the latest.

Subcommands:
  --status           Read-only display of the remaining lifetime of both tokens
  --store-creds      Interactively store username/password/TOTP secret in Windows
                     Credential Manager (keyring)
  --generate-vip     Generate a virtual Symantec VIP credential and guide enrollment
                     (requires pip install vipaccess)
  --login            Headed first-run calibration (human observes, selectors verified live)
  --once             Single automatic decision round (called by the scheduled task, default)
  --force-reauth     Ignore thresholds and re-authorize in the browser immediately
                     (drills/debugging)
  --install-task     Register the scheduled task (daily at 12:00 + a catch-up run 3 minutes
                     after logon; time comes from the task_time config)
  --uninstall-task   Remove the scheduled task

Exit codes: 0 success; 1 manual intervention required (screenshots saved under
.schwabdev/keeper_screens/); 2 retryable network-class failure.
"""

import argparse
import base64
import getpass
import json
import logging
import logging.handlers
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    import keyring
except ImportError:
    keyring = None

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_JSON = BASE_DIR / "user_data" / "user_settings.json"
KEEPER_JSON = BASE_DIR / "schwab_keeper.json"
SCHWABDEV_DIR = BASE_DIR / ".schwabdev"
BACKUP_DIR = SCHWABDEV_DIR / "keeper_backup"
SCREENS_DIR = SCHWABDEV_DIR / "keeper_screens"
PROFILE_DIR = SCHWABDEV_DIR / "keeper_profile"
LOG_FILE = SCHWABDEV_DIR / "keeper.log"
LOCK_FILE = SCHWABDEV_DIR / "keeper.lock"
KEYRING_SERVICE = "schwab_token_keeper"
TASK_NAME = "SchwabTokenKeeper"
OAUTH_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
AUTHORIZE_URL = "https://api.schwabapi.com/v1/oauth/authorize"
ACCOUNTS_URL = "https://api.schwabapi.com/trader/v1/accounts"

# Schema identical to schwabdev tokens.py L80-91
_DDL = """
CREATE TABLE IF NOT EXISTS schwabdev (
    access_token_issued TEXT NOT NULL,
    refresh_token_issued TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    id_token TEXT NOT NULL,
    expires_in INTEGER,
    token_type TEXT,
    scope TEXT
)
"""

DEFAULT_CONFIG = {
    "threshold_days": 5.0,
    "force_days": 6.0,
    "task_time": "12:00",
    "closed_window": ["04:00", "21:20"],
    "engine": "playwright",
    "channel": "chrome",
    "headless": True,
    "flow_timeout_minutes": 6,
    "login_timeout_minutes": 15,
    "credentials": {"username": "", "password": "", "totp_secret": ""},
    # Login/authorization flow steps (in order; selectors matched first-come-first-served;
    # calibrate live with a first run of --login, then edit the JSON)
    "steps": [
        {"name": "username", "action": "fill", "value": "username",
         "selectors": ["#loginId", "input[name='loginId']", "input[name='loginID']",
                       "input[autocomplete='username']"]},
        {"name": "password", "action": "fill", "value": "password",
         "selectors": ["#loginPassword", "input[name='loginPassword']", "input[type='password']"]},
        {"name": "login_submit", "action": "click",
         "selectors": ["#loginSubmit", "//button[normalize-space()='Log In']",
                       "//input[@type='submit']", "button[type='submit']"]},
        {"name": "totp", "action": "fill", "value": "totp",
         "selectors": ["#securityCode", "input[name='securityCode']", "input[name='code']",
                       "input[autocomplete='one-time-code']", "input[inputmode='numeric']"]},
        {"name": "totp_submit", "action": "click",
         "selectors": ["//button[normalize-space()='Continue']",
                       "//button[normalize-space()='Submit']",
                       "//button[normalize-space()='Verify']", "button[type='submit']"]},
        {"name": "consent_checkbox", "action": "check",
         "selectors": ["input[type='checkbox']:not(:checked)"]},
        {"name": "consent_continue", "action": "click",
         "selectors": ["//button[normalize-space()='Continue']",
                       "//button[normalize-space()='Agree']",
                       "//button[normalize-space()='Accept']", "button[type='submit']"]},
        {"name": "accept", "action": "click",
         "selectors": ["//button[normalize-space()='Accept']",
                       "//button[normalize-space()='I Accept']"]},
        {"name": "select_accounts", "action": "check",
         "selectors": ["#checkAll", "input[type='checkbox']:not(:checked)"]},
        {"name": "done", "action": "click",
         "selectors": ["//button[normalize-space()='Done']",
                       "//button[normalize-space()='Continue']"]},
    ],
}


class KeeperError(Exception):
    pass


class BlockedError(Exception):
    """Suspected Akamai anti-bot block (Access Denied)."""


def setup_logging():
    logger = logging.getLogger("keeper")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    SCHWABDEV_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")
    fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3,
                                              encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    if sys.stdout is not None:  # no console under pythonw
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger


def say(msg):
    try:
        if sys.stdout is not None:
            print(msg, flush=True)
    except Exception:
        pass


def log():
    return logging.getLogger("keeper")


def fmt_td(td):
    return str(td).split(".")[0]


def _parse_iso(s):
    if not s:
        return None
    dt = datetime.fromisoformat(str(s))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------- Configuration ----------------

def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if KEEPER_JSON.exists():
        try:
            with open(KEEPER_JSON, encoding="utf-8") as f:
                user_cfg = json.load(f)
            if isinstance(user_cfg, dict):
                for k, v in user_cfg.items():
                    if k.startswith("_") or k == "steps":
                        continue
                    cfg[k] = v
                if isinstance(user_cfg.get("steps"), list):
                    cfg["steps"] = user_cfg["steps"]
        except Exception as e:
            log().warning("failed to parse schwab_keeper.json, using default config: %s", e)
    else:
        with open(KEEPER_JSON, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        say(f"Generated default config {KEEPER_JSON}")
    return cfg


def load_schwab_settings():
    if not SETTINGS_JSON.exists():
        raise KeeperError(f"{SETTINGS_JSON} not found")
    with open(SETTINGS_JSON, encoding="utf-8") as f:
        d = json.load(f)
    s = d.get("schwab") or {}
    app_key = s.get("app_key") or ""
    app_secret = s.get("app_secret") or ""
    if not app_key or not app_secret:
        raise KeeperError("user_settings.json is missing schwab.app_key / app_secret")
    tokens_db = s.get("tokens_db") or ".schwabdev/tokens.db"
    p = Path(tokens_db)
    if not p.is_absolute():
        p = BASE_DIR / p
    return {
        "app_key": app_key,
        "app_secret": app_secret,
        "callback_url": s.get("callback_url") or "https://127.0.0.1",
        "db": p,
    }


# ---------------- tokens.db ----------------

def db_connect(path):
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def db_read(path):
    path = Path(path)
    if not path.exists():
        return None
    conn = db_connect(path)
    try:
        try:
            row = conn.execute(
                "SELECT access_token_issued, refresh_token_issued, access_token, "
                "refresh_token, id_token, expires_in, token_type, scope "
                "FROM schwabdev LIMIT 1"
            ).fetchone()
        except sqlite3.OperationalError:
            return None
    finally:
        conn.close()
    if not row:
        return None
    at_issued_s, rt_issued_s, at, rt, id_token, expires_in, token_type, scope = row
    if str(at).startswith("enc:") or str(rt).startswith("enc:"):
        raise KeeperError(
            "tokens in tokens.db carry the enc: prefix (schwab.encryption is enabled in "
            "user_settings.json); keeper only supports plaintext mode; please clear the "
            "encryption setting and try again"
        )
    return {
        "at_issued": _parse_iso(at_issued_s),
        "rt_issued": _parse_iso(rt_issued_s),
        "access_token": at,
        "refresh_token": rt,
        "id_token": id_token or "",
        "expires_in": expires_in,
        "token_type": token_type,
        "scope": scope,
    }


def _prune_backups(keep=10):
    try:
        baks = sorted(BACKUP_DIR.glob("tokens_*.db"))
        for old in baks[:-keep] if len(baks) > keep else []:
            old.unlink()
    except Exception:
        pass


def db_write(path, at, rt, at_issued, rt_issued, id_token, expires_in, token_type, scope,
             backup=True):
    """Write the db in the same format as schwabdev _set_tokens (DELETE+INSERT all 8
    columns, exclusive transaction)."""
    path = Path(path)
    bak = None
    if backup and path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        bak = BACKUP_DIR / ("tokens_%s.db" % datetime.now().strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(path, bak)
        _prune_backups()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = db_connect(path)
    try:
        conn.execute(_DDL)
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("DELETE FROM schwabdev")
        conn.execute(
            "INSERT INTO schwabdev (access_token_issued, refresh_token_issued, "
            "access_token, refresh_token, id_token, expires_in, token_type, scope) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (at_issued.isoformat(), rt_issued.isoformat(), at, rt, id_token,
             int(expires_in or 1800), token_type or "Bearer", scope or "api"),
        )
        conn.commit()
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()
    return bak


def restore_backup(bak, path):
    if bak and Path(bak).exists():
        shutil.copy2(bak, path)
        log().info("Rolled back tokens.db from backup: %s", bak)


# ---------------- OAuth HTTP (direct connection, no proxy + relaxed SSL, matching the
# all_quantos.py patch convention) ----------------

def http_session():
    s = requests.Session()
    s.trust_env = False
    s.verify = False
    return s


def oauth_post(session, app_key, app_secret, data):
    auth = base64.b64encode(f"{app_key}:{app_secret}".encode()).decode()
    return session.post(
        OAUTH_TOKEN_URL,
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data=data, timeout=30,
    )


def accounts_ok(session, access_token):
    try:
        r = session.get(ACCOUNTS_URL, headers={"Authorization": f"Bearer {access_token}"},
                        timeout=30)
        if r.status_code == 200:
            return True, "HTTP 200"
        return False, f"HTTP {r.status_code} {r.text[:200]}"
    except requests.RequestException as e:
        return False, str(e)


# ---------------- Credentials / TOTP ----------------

def load_creds(cfg):
    out = {"username": "", "password": "", "totp_secret": ""}
    c = cfg.get("credentials") or {}
    for k in out:
        if c.get(k):
            out[k] = str(c[k])
    if keyring is not None:
        for k in list(out):
            try:
                v = keyring.get_password(KEYRING_SERVICE, k)
            except Exception:
                v = None
            if v:
                out[k] = v
    return out


def totp_now(secret):
    if not secret:
        return None
    try:
        import pyotp
        if secret.startswith("otpauth://"):
            return pyotp.parse_uri(secret).now()
        return pyotp.TOTP(secret).now()
    except Exception:
        return None


# ---------------- Browser adapter layer ----------------

class PlaywrightBrowser:
    def __init__(self, cfg, callback_url, headless):
        from playwright.sync_api import sync_playwright
        self._callback = callback_url
        self.code = None
        self._pw = sync_playwright().start()
        kwargs = {
            "user_data_dir": str(PROFILE_DIR),
            "headless": headless,
            "args": ["--disable-blink-features=AutomationControlled",
                     "--no-first-run", "--no-default-browser-check"],
            "viewport": {"width": 1280, "height": 800},
            "locale": "en-US",
        }
        channel = cfg.get("channel")
        try:
            if channel:
                kwargs["channel"] = channel
            self.context = self._pw.chromium.launch_persistent_context(**kwargs)
        except Exception:
            if not channel:
                raise
            kwargs.pop("channel", None)
            log().warning("channel=%s failed to launch, falling back to bundled chromium",
                          channel)
            self.context = self._pw.chromium.launch_persistent_context(**kwargs)
        self.context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.context.route(re.compile("^" + re.escape(callback_url)), self._on_route)

    def _on_route(self, route):
        url = route.request.url
        code = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("code", [None])[0]
        if code:
            self.code = code
        route.fulfill(status=200, content_type="text/html",
                      body="SchwabTokenKeeper: callback intercepted.")

    def poll_code(self):
        return self.code

    def open(self, url):
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

    def current_url(self):
        try:
            return self.page.url or ""
        except Exception:
            return ""

    def text(self):
        try:
            return self.page.content()
        except Exception:
            return ""

    def find(self, selectors):
        # Validate with locator + is_visible: the login page is a React SPA, and when an
        # element is in the DOM but off-viewport/not mounted, query_selector still matches
        # it, causing a later fill to raise ActionabilityError that gets silently swallowed.
        # is_visible is what a human eye actually sees.
        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.count() > 0 and loc.is_visible(timeout=500):
                    return sel
            except Exception:
                continue
        return None

    def fill(self, sel, value):
        # Wait until the element is visible + editable before filling; React SPA rendering
        # has latency.
        loc = self.page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=10000)
            loc.fill(value, timeout=10000)
        except Exception as e:
            log().debug("fill failed selector=%s value_len=%d err=%s", sel, len(value or ""), e)
            raise

    def click(self, sel):
        self.page.click(sel, timeout=10000)

    def submit_form(self):
        # Generic approach: submit the login form by pressing Enter (does not depend on the
        # id/class of the Log In button).
        self.page.keyboard.press("Enter")

    def check(self, sel):
        self.page.check(sel, timeout=10000)

    def screenshot(self, path):
        try:
            self.page.screenshot(path=str(path))
        except Exception:
            pass

    def close(self):
        try:
            self.context.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass


class SeleniumBaseBrowser:
    """UC-mode fallback tier (switch engine to seleniumbase when Playwright is blocked by
    Akamai)."""

    def __init__(self, cfg, callback_url, headless):
        try:
            from seleniumbase import SB
        except ImportError as e:
            raise KeeperError("engine=seleniumbase requires pip install seleniumbase") from e
        self._callback = callback_url
        self._sb = SB(uc=True, headless=headless, undetectable=True)
        self._sb.__enter__()

    def poll_code(self):
        url = self.current_url()
        if url.startswith(self._callback):
            code = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("code", [None])[0]
            if code:
                return code
        return None

    def open(self, url):
        self._sb.open(url)

    def current_url(self):
        try:
            return self._sb.get_current_url() or ""
        except Exception:
            return ""

    def text(self):
        try:
            return self._sb.driver.page_source or ""
        except Exception:
            return ""

    def find(self, selectors):
        for sel in selectors:
            try:
                if self._sb.is_element_present(sel):
                    return sel
            except Exception:
                continue
        return None

    def fill(self, sel, value):
        self._sb.type(sel, value)

    def click(self, sel):
        self._sb.click(sel)

    def check(self, sel):
        self._sb.click(sel)

    def screenshot(self, path):
        try:
            self._sb.driver.save_screenshot(str(path))
        except Exception:
            pass

    def close(self):
        try:
            self._sb.__exit__(None, None, None)
        except Exception:
            pass


def make_adapter(engine, cfg, callback_url, headless):
    if engine == "seleniumbase":
        return SeleniumBaseBrowser(cfg, callback_url, headless)
    if engine != "playwright":
        raise KeeperError(f"unknown engine: {engine} (options: playwright / seleniumbase)")
    return PlaywrightBrowser(cfg, callback_url, headless)


# ---------------- Authorization flow ----------------

def _looks_blocked(adapter):
    text = adapter.text() or ""
    return ("Access Denied" in text) or ("Request unsuccessful" in text)


def _flow_once(adapter, cfg, creds, auth_url, timeout_s):
    steps = cfg.get("steps") or DEFAULT_CONFIG["steps"]
    adapter.open(auth_url)
    # Wait for the login page React mount to complete (domcontentloaded does not mean React
    # has finished rendering).
    try:
        adapter.page.wait_for_selector(
            "#loginId, input[name='loginId'], input[name='loginID']",
            state="visible", timeout=15000)
    except Exception as e:
        log().warning("timed out waiting for login page readiness (continuing): %s", e)
    deadline = time.monotonic() + timeout_s
    done = set()
    last_url = None
    checks = 0
    while time.monotonic() < deadline:
        code = adapter.poll_code()
        if code:
            log().info("intercepted callback authorization code, closing browser immediately")
            try:
                adapter.close()
            except Exception:
                pass
            return code
        checks += 1
        if checks % 10 == 1:
            log().info("waiting for callback... round %d, current URL: %s",
                       checks, adapter.current_url()[:80])
        if checks % 8 == 1 and _looks_blocked(adapter):
            raise BlockedError(adapter.current_url())
        url = adapter.current_url()
        if url != last_url:
            done = set()  # page changed: rescan all steps (same buttons across pages may
            last_url = url  # trigger again)
        progressed = False
        for step in steps:
            name = step.get("name", "")
            if not name or name in done:
                continue
            sel = adapter.find(step.get("selectors", []))
            if not sel:
                log().debug("step %s not currently visible/found, skipping", name)
                continue
            action = step.get("action", "click")
            try:
                if action == "fill":
                    key = step.get("value", "")
                    if key == "totp":
                        value = totp_now(creds.get("totp_secret", "")) or ""
                    else:
                        value = creds.get(key, "") or ""
                    log().info("attempting to fill field %s (key=%s value_len=%d selector=%s)",
                               name, key, len(value or ""), sel)
                    if not value:
                        log().warning("step %s has no credential (keyring %s is empty), "
                                      "waiting for manual input", name, key)
                        continue  # no credential: --login mode waits for manual input;
                        # --once mode eventually times out
                    adapter.fill(sel, value)
                elif action == "check":
                    adapter.check(sel)
                elif action == "submit":
                    adapter.submit_form()
                else:
                    adapter.click(sel)
            except Exception as e:
                log().debug("step %s action failed (%s): %s", name, sel, e)
                continue
            done.add(name)
            progressed = True
            log().info("flow step completed: %s (selector=%s)", name, sel)
            break
        if not progressed:
            time.sleep(1.5)
    return None


def run_auth_flow(cfg, creds, schwab, mode):
    auth_url = (f"{AUTHORIZE_URL}?client_id={schwab['app_key']}"
                f"&redirect_uri={schwab['callback_url']}")
    engine = cfg.get("engine", "playwright")
    if mode == "login":
        timeout_s = float(cfg.get("login_timeout_minutes", 15)) * 60
    else:
        timeout_s = float(cfg.get("flow_timeout_minutes", 6)) * 60
    headless = bool(cfg.get("headless", True)) and mode != "login"
    attempts = [headless, False] if headless else [False]
    for i, hl in enumerate(attempts):
        adapter = make_adapter(engine, cfg, schwab["callback_url"], hl)
        blocked = False
        try:
            code = _flow_once(adapter, cfg, creds, auth_url, timeout_s)
            if code:
                if i > 0:
                    log().warning("headed fallback tier succeeded in obtaining the code")
                return code
            blocked = _looks_blocked(adapter)
            log().error("attempt %d (headless=%s) did not obtain a code, current URL: %s",
                        i + 1, hl, adapter.current_url())
        except BlockedError as e:
            blocked = True
            log().error("attempt %d (headless=%s) appears blocked by Akamai, URL: %s",
                        i + 1, hl, e)
        except Exception as e:
            log().error("attempt %d browser flow raised an exception: %s", i + 1, e)
        try:
            SCREENS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            adapter.screenshot(SCREENS_DIR / (f"{ts}_attempt{i + 1}.png"))
        except Exception:
            pass
        adapter.close()
        if blocked and hl and i + 1 < len(attempts):
            log().warning("headless was blocked; automatically degrading to headed retry once")
            continue
        return None
    return None


def do_reauth(cfg, schwab, mode="once"):
    creds = load_creds(cfg)
    if not (creds.get("username") and creds.get("password")):
        log().warning("no stored login credentials (--store-creds can store them); relying "
                      "only on the profile remembering the device session; if a login page "
                      "appears it will fail, requiring a headed --login fallback run")
    if not creds.get("totp_secret"):
        log().info("no stored TOTP secret (--generate-vip enables fully automatic 2FA); 2FA "
                   "relies on the remembered device to skip it")
    code = run_auth_flow(cfg, creds, schwab, mode)
    if not code:
        log().critical("browser re-authorization did not obtain an authorization code "
                       "(screenshots in keeper_screens/). Please run --login for headed "
                       "calibration, or check the selectors/credentials in schwab_keeper.json")
        return 1
    log().info("obtained authorization code (%d chars), exchanging for a token now", len(code))
    s = http_session()
    try:
        resp = oauth_post(s, schwab["app_key"], schwab["app_secret"], {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": schwab["callback_url"],
        })
    except requests.RequestException as e:
        log().critical("network error exchanging authorization_code for a token: %s", e)
        return 2
    if not resp.ok:
        log().critical("failed to exchange authorization_code for a token: HTTP %s %s",
                       resp.status_code, resp.text[:300])
        return 1
    j = resp.json()
    if not j.get("access_token") or not j.get("refresh_token"):
        log().critical("token response is missing access_token/refresh_token: %s",
                       str(j)[:300])
        return 1
    now = datetime.now(timezone.utc)
    bak = db_write(schwab["db"], j["access_token"], j["refresh_token"], now, now,
                   j.get("id_token", ""), j.get("expires_in", 1800),
                   j.get("token_type", "Bearer"), j.get("scope", "api"))
    ok, detail = accounts_ok(s, j["access_token"])
    if not ok:
        restore_backup(bak, schwab["db"])
        log().critical("new token self-check failed (%s); rolled back from backup %s",
                       detail, bak)
        return 1
    die_local = (now + timedelta(days=7)).astimezone().strftime("%Y-%m-%d %H:%M")
    log().info("re-authorization succeeded: new refresh token expires at %s (7 days); "
               "self-check GET accounts passed; pre-write backup: %s",
               die_local, bak.name if bak else "(original db was empty, no backup)")
    return 0


# ---------------- Health check and decision ----------------

def in_closed_window(cfg):
    # US market closed hours (04:00-21:20 Beijing time, truncated 10 minutes before the
    # 21:30 open): re-authorizing at this moment does not affect the running app's
    # intraday data. The 21:20 right edge exists so the scenario of booting up right
    # before the open (21:20-21:30) does not trigger a browser token swap -- the user is
    # about to start the program then, and deferring to the next run point is harmless
    # (being 5 days old still leaves 2 days of margin).
    w = cfg.get("closed_window") or ["04:00", "21:20"]

    def hm(x):
        h, m = str(x).split(":")
        return int(h) * 60 + int(m)

    try:
        a, b = hm(w[0]), hm(w[1])
    except Exception:
        return True
    now = datetime.now()
    cur = now.hour * 60 + now.minute
    return a <= cur < b


def health_check(cfg, schwab, tokens):
    s = http_session()
    try:
        resp = oauth_post(s, schwab["app_key"], schwab["app_secret"], {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        })
    except requests.RequestException as e:
        log().error("health check network error (%s); skipping this round, waiting for the "
                    "next run", e)
        return 2
    if resp.status_code in (400, 401):
        log().warning("health check HTTP %s: %s -> refresh token judged dead, running "
                      "browser re-authorization", resp.status_code, resp.text[:200])
        return do_reauth(cfg, schwab)
    if not resp.ok:
        log().error("health check HTTP %s (%s); treating as a transient failure, waiting "
                    "for the next run", resp.status_code, resp.text[:200])
        return 2
    j = resp.json()
    if not j.get("access_token"):
        log().error("refresh response is missing access_token: %s", str(j)[:200])
        return 2
    now = datetime.now(timezone.utc)
    db_write(schwab["db"], j["access_token"], tokens["refresh_token"], now,
             tokens["rt_issued"], tokens.get("id_token", ""), j.get("expires_in", 1800),
             j.get("token_type", "Bearer"), j.get("scope", "api"))
    log().info("health check passed: refresh token is alive, access token refreshed and "
               "written back along the way")
    return 0


def cmd_once(cfg, schwab, force=False):
    tokens = db_read(schwab["db"])
    now = datetime.now(timezone.utc)
    if not tokens or not tokens.get("refresh_token") or not tokens.get("rt_issued"):
        log().warning("tokens.db has no valid refresh token; running browser "
                      "re-authorization directly")
        return do_reauth(cfg, schwab)
    rt_age = now - tokens["rt_issued"]
    th = timedelta(days=float(cfg.get("threshold_days", 5.0)))
    fd = timedelta(days=float(cfg.get("force_days", 6.0)))
    log().info("refresh token age %s (threshold %s days / hard threshold %s days)",
               fmt_td(rt_age), cfg.get("threshold_days"), cfg.get("force_days"))
    if force:
        log().info("--force-reauth: ignoring thresholds and re-authorizing immediately")
        return do_reauth(cfg, schwab)
    if rt_age >= fd:
        log().warning("rt age exceeds the hard threshold (less than 24h left); "
                      "re-authorizing immediately without conditions")
        return do_reauth(cfg, schwab)
    if rt_age >= th:
        if in_closed_window(cfg):
            log().info("threshold reached and inside the closed window; running browser "
                       "re-authorization")
            return do_reauth(cfg, schwab)
        log().info("threshold reached but not inside the closed window %s; this round is "
                   "health check only, waiting for the next run point",
                   cfg.get("closed_window"))
    return health_check(cfg, schwab, tokens)


# ---------------- Remaining CLI ----------------

def cmd_status(cfg, schwab):
    tokens = db_read(schwab["db"])
    if not tokens:
        say(f"tokens.db ({schwab['db']}) has no token record")
        return 1
    now = datetime.now(timezone.utc)

    def loc(dt):
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")

    def left_str(td):
        if td.total_seconds() < 0:
            return f"expired (before {fmt_td(-td)})"
        return f"{fmt_td(td)} remaining"

    at_left = timedelta(seconds=tokens.get("expires_in") or 1800) - (now - tokens["at_issued"])
    rt_left = timedelta(days=7) - (now - tokens["rt_issued"])
    say(f"tokens.db    : {schwab['db']}")
    say(f"access token : issued {loc(tokens['at_issued'])} | {left_str(at_left)}"
        f" (expiry is harmless: the app startup/keeper run auto-refreshes with the "
        f"refresh token)")
    say(f"refresh token: issued {loc(tokens['rt_issued'])} | {left_str(rt_left)}"
        f" (expires {loc(tokens['rt_issued'] + timedelta(days=7))})")
    say(f"config       : threshold {cfg.get('threshold_days')} days / hard threshold "
        f"{cfg.get('force_days')} days | engine {cfg.get('engine')} "
        f"(channel={cfg.get('channel')}, headless={cfg.get('headless')})")
    return 0


def cmd_store_creds():
    if keyring is None:
        say("keyring is not installed (pip install keyring); please use the plaintext "
            "schwab_keeper.json config instead")
        return 1
    say(f"Storing credentials in Windows Credential Manager (service name {KEYRING_SERVICE}); "
        f"never goes through chat or logs.")
    username = input("Schwab login username (press Enter to skip): ").strip()
    password = getpass.getpass("Schwab login password (input hidden, Enter to skip): ")
    totp = getpass.getpass("TOTP secret or otpauth:// URI (Enter to skip if none): ")
    stored = []
    for k, v in (("username", username), ("password", password), ("totp_secret", totp)):
        if v:
            keyring.set_password(KEYRING_SERVICE, k, v)
            stored.append(k)
    if not stored:
        say("Nothing was entered; nothing stored.")
        return 1
    say(f"Stored: {', '.join(stored)}")
    say(f"To remove: delete the generic credential entries for {KEYRING_SERVICE} in Windows "
        f"Credential Manager")
    return 0


def cmd_generate_vip():
    say("Generating a virtual Symantec VIP credential (via the official Symantec "
        "provisioning API)...")
    exe = shutil.which("vipaccess")
    cmd = [exe, "provision", "-p", "-t", "SYMC"] if exe else \
        [sys.executable, "-m", "vipaccess", "provision", "-p", "-t", "SYMC"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except FileNotFoundError:
        say("vipaccess command not found: please run pip install vipaccess first and retry")
        return 1
    except subprocess.TimeoutExpired:
        say("provision timed out (network issue); retry later")
        return 1
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    say("--- raw vipaccess output ---")
    say(out)
    say("----------------------------")
    m = re.search(r"otpauth://\S+", out)
    if not m:
        say("Could not parse an otpauth:// URI. Please enter the URI from the output above "
            "via --store-creds (or put it in the credentials.totp_secret field of "
            "schwab_keeper.json)")
        return 1
    uri = m.group(0)
    m2 = re.search(r"Credential\s*ID:?\s*(\S+)", out, re.I)
    cid = m2.group(1) if m2 else "(see the output above)"
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, "totp_secret", uri)
            say("otpauth URI stored in Windows Credential Manager (totp_secret).")
        except Exception as e:
            say(f"keyring storage failed ({e}); please enter it manually in the "
                f"credentials.totp_secret field of schwab_keeper.json")
    say("")
    say("Next steps (one-time, about 2 minutes):")
    say(" 1. Log in to Schwab.com in a browser -> Settings -> Security -> "
        "Two-Step Verification")
    say(" 2. Add a verification method and choose 'Security Token' (VIP Access)")
    say(f" 3. Enter Credential ID: {cid} to complete enrollment")
    say(" 4. Afterwards keeper automatically generates verification codes for 2FA (pyotp), "
        "fully unattended")
    return 0


def _run_ps(script):
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
        capture_output=True, text=True, timeout=120,
    )


def cmd_install_task():
    cfg = load_config()
    task_time = str(cfg.get("task_time") or "12:00")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    script_path = BASE_DIR / "schwab_token_keeper.py"
    ps = f"""
$ErrorActionPreference = 'Stop'
try {{
    $action = New-ScheduledTaskAction -Execute '{pythonw}' -Argument '"{script_path}" --once' -WorkingDirectory '{BASE_DIR}'
    $t1 = New-ScheduledTaskTrigger -Daily -At '{task_time}'
    $t2 = New-ScheduledTaskTrigger -AtLogOn
    $t2.Delay = 'PT3M'
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName '{TASK_NAME}' -TaskPath '\\' -Action $action -Trigger @($t1, $t2) -Settings $settings -Description 'Schwab 7-day refresh token auto-renewal (keeper)' -Force | Out-Null
    Write-Output 'TASK_INSTALLED'
}} catch {{
    Write-Output ('REGISTER_ERR:' + $_.Exception.Message)
    Write-Output ('REGISTER_TYPE:' + $_.Exception.GetType().FullName)
    exit 1
}}
"""
    r = _run_ps(ps)
    if r.returncode == 0 and "TASK_INSTALLED" in (r.stdout or ""):
        say(f"Scheduled task {TASK_NAME} registered: daily at {task_time} + a catch-up run 3 "
            f"minutes after logon (pythonw, no console window)")
        # Verify: check with schtasks whether the task really exists
        v = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME],
                           capture_output=True, text=True)
        if v.returncode != 0:
            say(f"WARNING task is not actually visible: {v.stderr.strip()} (PowerShell may "
                f"report registered but actually wrote to a non-default path, or permission "
                f"was denied by policy)")
            say("Run the following command in an administrator PowerShell to diagnose: "
                "Get-ScheduledTask | Format-Table TaskName, TaskPath, State")
        else:
            say((v.stdout or "").strip())
        return 0
    say("registration failed: %s" % ((r.stdout or "") + (r.stderr or "")).strip())
    say("If it reports insufficient permissions, register manually in an administrator "
        "PowerShell, or tell me to switch to the schtasks approach.")
    return 1


def cmd_uninstall_task():
    ps = (f"try {{ Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false "
          f"-ErrorAction Stop; Write-Output 'TASK_REMOVED' }} "
          f"catch {{ Write-Output ('ERR:' + $_.Exception.Message) }}")
    r = _run_ps(ps)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if "TASK_REMOVED" in (r.stdout or ""):
        say(f"Scheduled task {TASK_NAME} removed")
        return 0
    if "err:" in out.lower() and any(
            k in out.lower() for k in ("not exist", "cannot find", "no msft_scheduledtask",
                                       "no scheduled task", "not found", "does not exist")):
        say("The scheduled task did not exist in the first place")
        return 0
    say(f"removal failed: {out}")
    return 1


# ---------------- Single-instance lock ----------------

def acquire_lock():
    if LOCK_FILE.exists():
        try:
            if time.time() - LOCK_FILE.stat().st_mtime < 3600:
                return False
            LOCK_FILE.unlink()
        except OSError:
            return False
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_lock():
    try:
        LOCK_FILE.unlink()
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="schwab_token_keeper.py",
        description="Schwab 7-day refresh token auto-renewal (non-invasive: does not modify "
                    "all_quantos.py, only writes the runtime data tokens.db, with an "
                    "automatic backup before writing)",
        epilog="Example: python schwab_token_keeper.py --status | --login | --install-task")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--status", action="store_true",
                   help="read-only display of the remaining lifetime of both tokens")
    g.add_argument("--store-creds", action="store_true",
                   help="interactively store username/password/TOTP in Windows Credential "
                        "Manager")
    g.add_argument("--generate-vip", action="store_true",
                   help="generate a virtual Symantec VIP credential (for fully automatic "
                        "2FA, optional)")
    g.add_argument("--login", action="store_true",
                   help="headed first-run calibration (human observes)")
    g.add_argument("--once", action="store_true",
                   help="single automatic decision round (default action)")
    g.add_argument("--force-reauth", action="store_true",
                   help="ignore thresholds and re-authorize in the browser immediately "
                        "(drills/debugging)")
    g.add_argument("--install-task", action="store_true",
                   help="register the scheduled task (daily at task_time (default 12:00) + "
                        "a catch-up run 3 minutes after logon)")
    g.add_argument("--uninstall-task", action="store_true",
                   help="remove the scheduled task")
    args = ap.parse_args(argv)

    setup_logging()
    try:
        if args.status:
            return cmd_status(load_config(), load_schwab_settings())
        if args.store_creds:
            return cmd_store_creds()
        if args.generate_vip:
            return cmd_generate_vip()
        if args.install_task:
            return cmd_install_task()
        if args.uninstall_task:
            return cmd_uninstall_task()

        cfg = load_config()
        schwab = load_schwab_settings()
        if args.login:
            say("Headed calibration mode: the browser is about to open; please observe and "
                "intervene manually if necessary (2FA/remember device);")
            say("if any selector needs fixing after the flow, edit the steps in "
                "schwab_keeper.json.")
            return do_reauth(cfg, schwab, mode="login")
        if not acquire_lock():
            log().info("another instance is running (keeper.lock not timed out); exiting")
            return 0
        try:
            return cmd_once(cfg, schwab, force=args.force_reauth)
        finally:
            release_lock()
    except KeeperError as e:
        log().critical(str(e))
        say(str(e))
        return 1
    except Exception:
        log().critical("unexpected exception", exc_info=True)
        say("Unexpected exception; see .schwabdev/keeper.log for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
