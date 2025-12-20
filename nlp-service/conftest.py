"""
Pytest configuration for appointment testing.
"""

import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    """Configure event loop policy for Windows."""
    import asyncio
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    return asyncio.get_event_loop_policy()
