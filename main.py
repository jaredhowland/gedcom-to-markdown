"""
Top-level shim to expose the CLI functions for tests.
This module delegates to src/main.py so `import main` resolves to the
implementation expected by the test suite.
"""

# Import and re-export selected symbols from src/main.py
try:
    from src.main import setup_logging, extract_gedzip, convert_gedcom_to_markdown, main as cli_main
except Exception:
    # Provide minimal placeholders to avoid import errors in unusual environments
    def setup_logging(*args, **kwargs):
        pass

    def extract_gedzip(*args, **kwargs):
        raise RuntimeError("extract_gedzip is unavailable")

    def convert_gedcom_to_markdown(*args, **kwargs):
        raise RuntimeError("convert_gedcom_to_markdown is unavailable")

    def cli_main(*args, **kwargs):
        raise RuntimeError("CLI main is unavailable")


def main():
    """Invoke CLI entrypoint."""
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
