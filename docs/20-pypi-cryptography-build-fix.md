# PyPI cryptography build fix

When `pypi.org/simple/cryptography/` is unreachable or very slow from Docker, the PLC build must not depend on that index page.

The project therefore uses:

- `python:3.13-slim-trixie`
- Debian `python3-cryptography` and `python3-openssl`
- Debian packages for the pure-Python dependencies required by asyncua
- the official `asyncua 1.1.8` wheel from `files.pythonhosted.org`, installed with `--no-deps` and a pinned SHA-256 hash

This means pip no longer resolves or downloads cryptography for the PLC/OPC UA images.

The signed-license services (`level2-api` and `heat-management`) also use Debian's `python3-cryptography` package instead of PyPI.
