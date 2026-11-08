"""Validate frozen JSON bytes while allowing Git's LF/CRLF conversion only."""

import hashlib


def frozen_text_matches(raw, expected):
    lf = raw.replace(b'\r\n', b'\n')
    return any(hashlib.sha256(value).hexdigest() == expected for value in (raw, lf, lf.replace(b'\n', b'\r\n')))
