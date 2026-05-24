"""Minimal pure-stdlib reader for SAS Transport (XPT) v5 files.

Extracts variable names from the NAMESTR records — enough to cross-check dataset variables against
define.xml metadata (RFC-0001). No third-party deps (avoids the pandas build chain).

XPT v5 layout: an 80-byte NAMESTR header record encodes the variable count; each NAMESTR record is
140 bytes with the variable name at offset 8 (8 chars). The block is padded to an 80-byte boundary
before the OBS header.
"""

from __future__ import annotations

import os
from pathlib import Path


def read_xpt_columns(path: str | os.PathLike[str]) -> list[str]:
    data = Path(path).read_bytes()
    marker = data.find(b"NAMESTR HEADER RECORD")
    if marker < 0:
        raise ValueError("not an XPT v5 file: no NAMESTR header record")
    rec_start = marker - 20  # back up over "HEADER RECORD*******"
    header = data[rec_start : rec_start + 80]
    count = int(header[54:58].decode("ascii"))
    ns_start = rec_start + 80

    for size in (140, 136):  # v5 is 140; tolerate 136 variants
        block = count * size
        pad = (-block) % 80
        obs_pos = ns_start + block + pad
        if b"OBS" in data[obs_pos : obs_pos + 80] or obs_pos >= len(data):
            return [
                data[ns_start + k * size + 8 : ns_start + k * size + 16].decode("ascii", "replace").strip()
                for k in range(count)
            ]
    raise ValueError("could not locate OBS header after NAMESTR block")
