import os

# Set required environment variables before any backend module imports.
# These are dummy values used only for test-time imports; no real DB connection is made.
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_DB", "tradingcopilot")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
