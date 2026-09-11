"""Vercel entry point.

Vercel serves every request through this file (see the rewrite in vercel.json)
and looks for a WSGI callable named `app`. Locally nothing imports it - use
`python run.py serve` instead.
"""
import os
import sys

# api/ is its own directory in the bundle; the package lives one level up.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ls_tool.webapp import create_app  # noqa: E402

app = create_app()
