"""Curated MJML block library for outreach templates (ADR-0004 decision #2).

This module is INTERNAL to ``packages.outreach``. Operators do not
edit MJML directly in Stage 1; the renderer wraps the operator's
Mustache-substituted body inside a vetted MJML envelope so the final
HTML is consistent across templates and across mailbox vendors.

Adding a block: open a PR with the new partial here AND a unit test
that renders it cleanly through ``mjml-python``. No runtime additions.

Stage 1 ships ONE envelope (``DEFAULT_ENVELOPE``) plus a fallback
inline-CSS HTML body wrapper used when ``mjml-python`` is not
available. Future stages add hero / cta_button / footer named blocks
once the operator UI exposes a block picker.
"""

from __future__ import annotations

from typing import Final

# Default MJML envelope. ``{{ body }}`` is the substitution slot; the
# render engine fills it with the Mustache-resolved Markdown-rendered
# HTML AFTER all merge fields have been resolved (so the body never
# contains live Mustache by the time MJML compiles).
DEFAULT_ENVELOPE: Final[str] = """\
<mjml>
  <mj-head>
    <mj-attributes>
      <mj-all font-family="Helvetica, Arial, sans-serif" />
      <mj-text font-size="14px" line-height="1.5" color="#222222" />
    </mj-attributes>
  </mj-head>
  <mj-body background-color="#ffffff">
    <mj-section padding="20px">
      <mj-column>
        <mj-text>
          {{ body }}
        </mj-text>
      </mj-column>
    </mj-section>
    <mj-section padding="0 20px 20px">
      <mj-column>
        <mj-text font-size="12px" color="#888888">
          {{ unsubscribe_block }}
        </mj-text>
      </mj-column>
    </mj-section>
  </mj-body>
</mjml>
"""

# Inline-CSS plain HTML wrapper used when the MJML compiler is absent.
# Keeps the visible shape similar to the MJML envelope without pulling a
# CSS framework.
FALLBACK_HTML_ENVELOPE: Final[str] = """\
<!DOCTYPE html>
<html>
  <head><meta charset="utf-8" /></head>
  <body style="margin:0;padding:0;background:#fff;
               font-family:Helvetica,Arial,sans-serif;color:#222;
               font-size:14px;line-height:1.5;">
    <div style="max-width:600px;margin:0 auto;padding:20px;">
      {{ body }}
      <hr style="border:none;border-top:1px solid #eee;margin:20px 0;" />
      <p style="font-size:12px;color:#888;margin:0;">{{ unsubscribe_block }}</p>
    </div>
  </body>
</html>
"""

# The unsubscribe block placeholder text. The render engine replaces
# this with a real one-click unsubscribe link AT SEND TIME (the renderer
# does not know the ``send_id`` yet); during preview the block shows
# the placeholder so the operator sees that the unsubscribe row will
# render.
UNSUBSCRIBE_PLACEHOLDER: Final[str] = (
    "If you'd rather not receive these emails, you can "
    "<a href=\"{{ unsubscribe_url }}\">unsubscribe here</a>."
)
