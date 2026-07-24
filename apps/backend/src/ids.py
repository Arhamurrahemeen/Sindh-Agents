import os
import time
import uuid


def uuid7() -> uuid.UUID:
    # ponytail: Python 3.11 stdlib has no uuid7 (lands in 3.14) and no UUID
    # library is in the locked stack (CLAUDE.md §3) — hand-rolled per RFC 9562,
    # not a full spec implementation, drop this for stdlib uuid.uuid7() on 3.14+.
    unix_ms = int(time.time() * 1000)
    rand = os.urandom(10)
    b = bytearray(16)
    b[0:6] = unix_ms.to_bytes(6, "big")
    b[6] = 0x70 | (rand[0] & 0x0F)
    b[7] = rand[1]
    b[8] = 0x80 | (rand[2] & 0x3F)
    b[9:16] = rand[3:10]
    return uuid.UUID(bytes=bytes(b))
