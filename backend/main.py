from __future__ import annotations

"""
Entry point for the backend voice gateway.

Recommended usage (from /home/harbi/Work/MAF):

    python -m backend.main
"""

import asyncio

from backend.ws_server import start_server


def main() -> None:
    asyncio.run(start_server())


if __name__ == "__main__":
    main()

