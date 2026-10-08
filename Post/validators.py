# SPDX-License-Identifier: MIT
#
# error-reporting-tool - link-back URL validation
#
# Licensed under the MIT license, see COPYING.MIT for details

import re
from urllib.parse import urlparse

# Only absolute http(s) URLs are allowed as a "link back". Everything else
# (javascript:, data:, vbscript:, scheme-relative "//host" or schemeless
# values) is rejected so it can never be rendered verbatim into an href.
ALLOWED_LINK_BACK_SCHEMES = ("http", "https")

# Control characters are used to obfuscate schemes, e.g. "java\tscript:".
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def clean_link_back(value):
    """Return a safe link-back URL, or None if the value is not acceptable."""
    if not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    if _CONTROL_CHARS.search(value):
        return None

    try:
        parsed = urlparse(value)
    except ValueError:
        return None

    if parsed.scheme.lower() not in ALLOWED_LINK_BACK_SCHEMES:
        return None

    if not parsed.netloc:
        return None

    return value
