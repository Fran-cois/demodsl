"""IMAP mailbox helper for register + email-validation flows.

Used by the ``await_email`` step (``demodsl.commands.EmailVerifyCommand``) to
wait for the validation email a SaaS sends after sign-up and pull out either
the confirmation **link** or the verification **code**.

Configuration is resolved from the scenario ``mailbox:`` block with a
``DEMODSL_IMAP_*`` environment-variable fallback, so secrets (the password in
particular) never have to live in the YAML.

No third-party dependencies — built on the stdlib ``imaplib`` + ``email``.
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
import re
import time
from email.message import Message
from email.utils import parseaddr

logger = logging.getLogger(__name__)

# A confirmation link or a numeric code rarely lives in noise; these defaults
# cover the overwhelming majority of SaaS validation emails.
_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+", re.IGNORECASE)
_DEFAULT_CODE_RE = r"\b(\d{4,8})\b"

# Bound how much we pull from the server so a huge inbox can't blow up memory.
_MAX_SCAN = 25


def resolve_mailbox_config(cfg: dict | None) -> dict:
    """Merge a scenario ``mailbox`` dict with ``DEMODSL_IMAP_*`` env fallbacks.

    Returns a dict with keys: imap_host, imap_port, username, password,
    use_ssl, folder. Raises ``RuntimeError`` when a required secret is missing.
    """
    cfg = dict(cfg or {})

    def pick(key: str, env: str, default=None):
        val = cfg.get(key)
        if val is None or val == "":
            val = os.environ.get(env)
        return val if (val is not None and val != "") else default

    host = pick("imap_host", "DEMODSL_IMAP_HOST")
    username = pick("username", "DEMODSL_IMAP_USER")
    password = pick("password", "DEMODSL_IMAP_PASSWORD")
    port_raw = pick("imap_port", "DEMODSL_IMAP_PORT", 993)
    folder = pick("folder", "DEMODSL_IMAP_FOLDER", "INBOX")

    use_ssl = cfg.get("use_ssl")
    if use_ssl is None:
        env_ssl = os.environ.get("DEMODSL_IMAP_SSL")
        use_ssl = (env_ssl.strip().lower() not in {"0", "false", "no"}) if env_ssl else True

    missing = [
        name
        for name, val in (("imap_host", host), ("username", username), ("password", password))
        if not val
    ]
    if missing:
        raise RuntimeError(
            "await_email: missing mailbox credentials "
            f"{missing}. Set them in the scenario 'mailbox:' block or via "
            "DEMODSL_IMAP_HOST / DEMODSL_IMAP_USER / DEMODSL_IMAP_PASSWORD "
            "(password is best provided as an env var, not in YAML)."
        )

    try:
        port = int(port_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"await_email: invalid IMAP port {port_raw!r}") from exc

    return {
        "imap_host": host,
        "imap_port": port,
        "username": username,
        "password": password,
        "use_ssl": bool(use_ssl),
        "folder": folder,
    }


def message_text(msg: Message) -> str:
    """Return the message body as text, concatenating plain + HTML parts.

    HTML is kept raw (not stripped) so that ``href="..."`` confirmation links
    remain matchable by the URL regex.
    """
    chunks: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                chunks.append(_decode_part(part))
    else:
        chunks.append(_decode_part(msg))
    return "\n".join(c for c in chunks if c)


def _decode_part(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:  # pragma: no cover - defensive
        payload = None
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, AttributeError):
        return payload.decode("utf-8", errors="replace")


def extract_link(text: str, contains: str | None = None) -> str | None:
    """Return the first http(s) link in *text* (optionally filtered)."""
    for url in _URL_RE.findall(text):
        url = url.rstrip(".,);'\"")
        if contains is None or contains.lower() in url.lower():
            return url
    return None


def extract_code(text: str, pattern: str | None = None) -> str | None:
    """Return the first capture-group match of *pattern* (default 4–8 digits)."""
    rx = re.compile(pattern or _DEFAULT_CODE_RE)
    m = rx.search(text)
    if not m:
        return None
    return m.group(1) if m.groups() else m.group(0)


def _matches(msg: Message, subject_contains: str | None, from_contains: str | None) -> bool:
    if subject_contains:
        subject = str(msg.get("Subject", ""))
        if subject_contains.lower() not in subject.lower():
            return False
    if from_contains:
        raw_from = str(msg.get("From", ""))
        name, addr = parseaddr(raw_from)
        haystack = f"{name} {addr} {raw_from}".lower()
        if from_contains.lower() not in haystack:
            return False
    return True


class MailboxClient:
    """Minimal IMAP client that waits for a NEW matching message.

    Use as a context manager::

        with MailboxClient(**resolve_mailbox_config(cfg)) as mb:
            msg = mb.wait_for_message(subject_contains="Confirm", timeout=60)
    """

    def __init__(
        self,
        imap_host: str,
        imap_port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
        folder: str = "INBOX",
    ) -> None:
        self._host = imap_host
        self._port = imap_port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._folder = folder
        self._imap: imaplib.IMAP4 | None = None
        self._baseline: set[bytes] = set()

    def __enter__(self) -> MailboxClient:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def connect(self) -> None:
        if self._use_ssl:
            self._imap = imaplib.IMAP4_SSL(self._host, self._port)
        else:
            self._imap = imaplib.IMAP4(self._host, self._port)
        self._imap.login(self._username, self._password)
        self._imap.select(self._folder)
        # Snapshot existing UIDs so we only react to mail that arrives AFTER
        # this point — i.e. the registration email we're about to trigger.
        self._baseline = self._all_uids()

    def close(self) -> None:
        if self._imap is None:
            return
        try:
            self._imap.close()
        except Exception:  # pragma: no cover - already closed/aborted
            pass
        try:
            self._imap.logout()
        except Exception:  # pragma: no cover
            pass
        self._imap = None

    def _all_uids(self) -> set[bytes]:
        assert self._imap is not None
        typ, data = self._imap.uid("search", None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return set()
        return set(data[0].split())

    def _fetch(self, uid: bytes) -> Message | None:
        assert self._imap is not None
        typ, data = self._imap.uid("fetch", uid, "(RFC822)")
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            return None
        return email.message_from_bytes(data[0][1])

    def wait_for_message(
        self,
        *,
        subject_contains: str | None = None,
        from_contains: str | None = None,
        timeout: float = 60.0,
        poll: float = 3.0,
    ) -> Message:
        """Block until a NEW message matching the filters arrives.

        Raises ``TimeoutError`` if none appears within *timeout* seconds.
        """
        assert self._imap is not None
        deadline = time.monotonic() + timeout
        while True:
            # Re-select to refresh the view (some servers cache otherwise).
            self._imap.select(self._folder)
            new_uids = sorted(self._all_uids() - self._baseline, key=lambda u: int(u))
            for uid in new_uids[-_MAX_SCAN:][::-1]:  # newest first
                msg = self._fetch(uid)
                if msg is None:
                    continue
                if _matches(msg, subject_contains, from_contains):
                    return msg
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "await_email: no matching email arrived within "
                    f"{timeout:.0f}s (subject~{subject_contains!r}, from~{from_contains!r})."
                )
            time.sleep(poll)
