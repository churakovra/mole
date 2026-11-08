"""Bootstrap CLI. No target repository is read or executed."""

import argparse
import json
import sys

from molekit import __version__


class InvalidRequest(Exception):
    """An invalid command line."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidRequest(message)


def emit(payload):
    print(json.dumps(payload, sort_keys=True))


def failure(code, message, action):
    emit({
        "ok": False,
        "error": {"code": code, "message": message,
                  "recoverable": True, "suggestedAction": action},
    })


def main(argv=None):
    parser = Parser(prog="mole", description="MOLE skill bootstrap diagnostics.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Check the bundled Python runtime.")
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable diagnostics.")
    try:
        args = parser.parse_args(argv)
    except InvalidRequest as exc:
        failure("INVALID_REQUEST", str(exc), "Run mole --help.")
        return 2

    if sys.version_info < (3, 11):
        failure("PYTHON_UNSUPPORTED", "MOLE requires Python 3.11 or newer.",
                "Run this entrypoint with Python 3.11+.")
        return 3

    result = {
        "ok": True,
        "engineVersion": __version__,
        "pythonVersion": ".".join(map(str, sys.version_info[:3])),
        "checks": {"pythonSupported": True, "bundledEngine": True},
        "capabilities": ["doctor"],
        "limitations": ["Bootstrap only; repository analysis is not implemented."],
    }
    if args.json:
        emit(result)
    else:
        print("MOLE {}: runtime ready (Python {}).".format(
            __version__, result["pythonVersion"]))
        print(result["limitations"][0])
    return 0
