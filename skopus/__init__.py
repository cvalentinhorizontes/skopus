"""Skopus — persistent context for AI coding assistants.

Install it, run it, your agent remembers you.
"""

# This MUST stay in lockstep with pyproject.toml's [project].version.
# tests/test_version_sync.py fails the build if they drift. Bumping pyproject
# without bumping this line is the bug pattern that broke v0.8.0 release prep.
__version__ = "0.8.0"
