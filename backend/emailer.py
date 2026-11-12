import os
import re
import ipaddress
import logging
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from core import FRONTEND_URL

logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> str | None:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if EMAIL_REPLY_TO:
        payload["contact_email"] = EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                   headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        try:
            code = e.response.json().get("code", "")
        except ValueError:
            code = ""
        if code in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning(f"Email paused: {code} ({e.response.status_code})")
            raise HTTPException(status_code=503, detail="Email is temporarily unavailable")
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail="Failed to send email")
    except Exception as e:
        logger.error(f"Email send error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


def _template(name: str, intro: str, cta: str, link: str, note: str) -> str:
    brand = escape(EMAIL_FROM_NAME)
    return (
        '<table role="presentation" width="100%" style="background:#05040A;padding:32px 0">'
        '<tr><td align="center"><table role="presentation" width="520" style="background:#120E24;'
        'border:1px solid #2e2458;border-radius:16px;padding:32px;font-family:Arial,sans-serif;color:#F8FAFC">'
        f'<tr><td style="font-size:20px;font-weight:bold;color:#C084FC;padding-bottom:16px">{brand}</td></tr>'
        f'<tr><td style="font-size:15px;line-height:1.6;color:#cbd5e1">Hi {escape(name)},<br><br>{intro}</td></tr>'
        f'<tr><td style="padding:24px 0"><a href="{escape(link)}" style="background:#8B5CF6;color:#ffffff;'
        f'padding:12px 24px;border-radius:999px;text-decoration:none;font-weight:bold">{cta}</a></td></tr>'
        f'<tr><td style="font-size:12px;color:#94A3B8">{note}</td></tr>'
        f'<tr><td style="font-size:11px;color:#64748B;padding-top:20px">Sent by {brand}. '
        'We never ask for your password or payment details by email.</td></tr>'
        '</table></td></tr></table>'
    )


async def send_verification_email(user: dict, token: str) -> None:
    link = f"{FRONTEND_URL}/verify-email?token={token}"
    html = _template(user["name"], "Confirm your email address to activate deposits and credit packages on your account.",
                     "Verify email", link, "This link expires in 24 hours. If you did not create an account, ignore this email.")
    await send_email(to=user["email"], subject=f"Verify your {EMAIL_FROM_NAME} account", html=html)


async def send_reset_email(user: dict, token: str) -> None:
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    html = _template(user["name"], "We received a request to reset the password on your account.",
                     "Choose a new password", link, "This link expires in 1 hour. If you did not request this, ignore this email.")
    await send_email(to=user["email"], subject=f"Reset your {EMAIL_FROM_NAME} password", html=html)


async def send_otp_email(user: dict, code: str) -> None:
    brand = escape(EMAIL_FROM_NAME)
    html = (
        '<table role="presentation" width="100%" style="background:#05040A;padding:32px 0">'
        '<tr><td align="center"><table role="presentation" width="520" style="background:#120E24;'
        'border:1px solid #2e2458;border-radius:16px;padding:32px;font-family:Arial,sans-serif;color:#F8FAFC">'
        f'<tr><td style="font-size:20px;font-weight:bold;color:#C084FC;padding-bottom:16px">{brand}</td></tr>'
        f'<tr><td style="font-size:15px;line-height:1.6;color:#cbd5e1">Hi {escape(user["name"])},<br><br>'
        'Use this one-time code to sign in. It expires in 10 minutes.</td></tr>'
        f'<tr><td style="padding:24px 0;font-size:34px;letter-spacing:10px;font-weight:bold;color:#ffffff">{code}</td></tr>'
        '<tr><td style="font-size:12px;color:#94A3B8">If you did not try to sign in, you can ignore this email.</td></tr>'
        f'<tr><td style="font-size:11px;color:#64748B;padding-top:20px">Sent by {brand}. '
        'Our team will never ask you for this code.</td></tr>'
        '</table></td></tr></table>'
    )
    await send_email(to=user["email"], subject=f"{code} is your {EMAIL_FROM_NAME} sign-in code", html=html)
