#!/usr/bin/env python3
"""Launch Crypto Price Analyzer. Reusable functions live in the sibling modules."""

from ui import app, run


if __name__ == "__main__":
    from local_config import load_local_config
    load_local_config()
    run()
