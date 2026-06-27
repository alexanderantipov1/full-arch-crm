"""RFC 5322 message builder for the outreach send pipeline.

Per ADR-0004 §"Templates language" + §"Tracking" decision #4. The
build_rfc822 entry point produces a fully formed RFC 5322 message that
either Gmail's ``users.messages.send`` (base64url-encoded raw) or
Microsoft Graph's ``/me/sendMail`` (after JSON conversion) can consume.

What the builder owns:

- multipart/alternative envelope with HTML + plaintext parts (RFC 2046)
- correct UTF-8 encoding of Subject + addresses (quoted-printable /
  base64 as needed)
- the two ``List-Unsubscribe`` headers (RFC 5322 + RFC 8058
  ``List-Unsubscribe-Post: List-Unsubscribe=One-Click``)
- ``Message-ID`` generation (so the send pipeline has a stable id to
  store on the send row even when Graph does not return one)
- optional ``In-Reply-To`` for thread continuation
- ENG-134: optional tracking-pixel injection into ``body_html`` when
  the caller passes ``tracking_pixel_url``. The caller (the send
  pipeline / dispatcher) consults ``template.tracking_enabled``
  before passing the URL; the builder itself does not look up the
  flag — it only encodes what it is given.

What it deliberately does NOT do:

- DKIM signing (Gmail / Graph sign on the way out, on the mailbox
  domain's key)
- click-tracking link rewriting (ADR-0004 §"Tracking" decision #4 —
  no click redirector)
- decide whether tracking is enabled (the send service / dispatcher
  consults ``template.tracking_enabled`` and the category gate)

Stdlib only — no extra dependencies. Uses ``email.message.EmailMessage``
+ ``email.headerregistry`` so header encoding is RFC-correct.
"""

from __future__ import annotations

import html as _html
import uuid
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


def build_rfc822(
    *,
    from_address: str,
    from_display_name: str | None,
    to: str,
    subject: str,
    body_html: str,
    body_text: str,
    list_unsubscribe_url: str,
    list_unsubscribe_mailto: str,
    in_reply_to: str | None = None,
    message_id: str | None = None,
    extra_headers: dict[str, str] | None = None,
    tracking_pixel_url: str | None = None,
) -> bytes:
    """Build a single RFC 5322 message as raw bytes.

    ``from_display_name`` is optional; when present the resulting From
    header is encoded as ``"Display Name" <addr@host>`` with RFC 2047
    encoded-word treatment for non-ASCII names.

    ``list_unsubscribe_url`` is the HTTPS one-click endpoint (with the
    HMAC token already embedded by the send service).
    ``list_unsubscribe_mailto`` is the ``mailto:`` form for clients that
    cannot perform a POST.

    Both ``List-Unsubscribe`` and ``List-Unsubscribe-Post:
    List-Unsubscribe=One-Click`` are written (RFC 8058) — the one-click
    POST endpoint accepts an empty body and records the unsubscribe.

    ``tracking_pixel_url`` (ENG-134) — when supplied, a 1x1 transparent
    ``<img>`` tag is appended to ``body_html``. The caller is the send
    pipeline, which consults the template's ``tracking_enabled`` flag
    before passing this. ``None`` means no pixel — the legacy ENG-132
    behaviour. The URL is HTML-escaped before substitution to defend
    against any caller smuggling a quote into the attribute value.
    """
    if not from_address:
        raise ValueError("build_rfc822 requires a non-empty from_address")
    if not to:
        raise ValueError("build_rfc822 requires a non-empty to")
    if not list_unsubscribe_url or not list_unsubscribe_mailto:
        raise ValueError(
            "build_rfc822 requires both list_unsubscribe_url and "
            "list_unsubscribe_mailto"
        )

    final_html = body_html or ""
    if tracking_pixel_url:
        # HTML-escape the URL value so a maliciously-formed URL cannot
        # break out of the attribute. We do NOT URL-encode here — the
        # caller produces URL-safe base64 tokens that are already safe.
        safe_url = _html.escape(tracking_pixel_url, quote=True)
        final_html = (
            f"{final_html}"
            f'<img src="{safe_url}" alt="" width="1" height="1" '
            f'border="0" style="display:block;width:1px;height:1px;'
            f'border:0;outline:none;text-decoration:none;'
            f'mso-line-height-rule:exactly;line-height:1px;" />'
        )

    msg = EmailMessage()

    # From: encode the display name as a UTF-8 phrase if present.
    if from_display_name:
        msg["From"] = f'"{_escape_quoted(from_display_name)}" <{from_address}>'
    else:
        msg["From"] = from_address

    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = message_id or make_msgid(
        idstring=uuid.uuid4().hex,
        domain=_extract_domain(from_address),
    )
    msg["MIME-Version"] = "1.0"

    # RFC 8058 one-click headers. The order matters less than the fact
    # that both are present and that the POST endpoint accepts the
    # canonical body ``List-Unsubscribe=One-Click``.
    msg["List-Unsubscribe"] = (
        f"<{list_unsubscribe_url}>, <{list_unsubscribe_mailto}>"
    )
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        # When threading, References mirrors the parent message id so
        # clients group consecutive replies in the same thread.
        msg["References"] = in_reply_to

    if extra_headers:
        for key, value in extra_headers.items():
            # Defensive: never let a caller smuggle a header that
            # collides with one we already set above. Domain code
            # passes pre-rendered values; we do not interpolate.
            if key.lower() in {
                "from",
                "to",
                "subject",
                "date",
                "message-id",
                "mime-version",
                "list-unsubscribe",
                "list-unsubscribe-post",
                "in-reply-to",
                "references",
                "content-type",
                "content-transfer-encoding",
            }:
                continue
            msg[key] = value

    # multipart/alternative: plaintext FIRST (RFC 2046 — clients pick
    # the LAST acceptable part, so HTML at the end means HTML wins for
    # capable clients while text-only readers see the plain version).
    msg.set_content(body_text or "", subtype="plain", charset="utf-8")
    msg.add_alternative(final_html, subtype="html", charset="utf-8")

    return msg.as_bytes()


def _escape_quoted(value: str) -> str:
    """Escape backslashes + quotes for a quoted-string header phrase.

    EmailMessage's policy will further encode non-ASCII via RFC 2047
    on serialisation; this only protects the quoting structure.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _extract_domain(address: str) -> str:
    """Extract the domain from ``user@domain`` — used for Message-ID.

    Defaults to ``localhost.invalid`` when the address has no ``@``;
    we still produce a valid Message-ID rather than raising, because
    addresses are validated by the caller before they reach the
    builder.
    """
    if "@" not in address:
        return "localhost.invalid"
    return address.rsplit("@", 1)[1]


__all__ = ["build_rfc822"]
