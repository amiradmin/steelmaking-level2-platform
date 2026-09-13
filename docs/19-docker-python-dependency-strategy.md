# Docker Python dependency strategy

The PLC/OPC UA images use Debian's packaged cryptography stack instead of downloading `cryptography` from PyPI during every build.

Reason: in some networks, access to `https://pypi.org/simple/cryptography/` is unreliable even when other PyPI packages are reachable. This caused long build retries and `No matching distribution found` errors that were actually network/index failures.

## Design

The Python images are pinned to `python:3.13-slim-trixie`.

Debian packages provide the native/security dependencies used by `asyncua`:

- `python3-cryptography`
- `python3-openssl`
- `python3-aiofiles`
- `python3-aiosqlite`
- `python3-dateutil`
- `python3-pytz`
- `python3-sortedcontainers`
- `python3-typing-extensions`

`PYTHONPATH=/usr/lib/python3/dist-packages` makes those Debian packages available to the `/usr/local` Python interpreter from the official Python image.

`asyncua==1.1.8` is installed from its official wheel with `--no-deps`, so pip does not attempt to resolve or download `cryptography` from PyPI.

The Level 2 API and Heat Management services also use Debian's `python3-cryptography` for signed-license verification.

## Normal command

```bash
git pull origin feature/plc-simulators
make full-heat
```

After a successful build, daily simulation can use:

```bash
make full-heat-fast
```

## Build verification

Each OPC UA image runs an import check during build. A successful image build verifies imports for `asyncua`, `cryptography`, and `OpenSSL` before the image is accepted.
