"""Bootstrap CLI. No target repository is read or executed."""

import argparse
import json
import sys

from molekit import __version__
from molekit.errors import MoleError
from molekit import pipeline


class InvalidRequest(Exception):
    """An invalid command line."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidRequest(message)


def emit(payload):
    print(json.dumps(payload, sort_keys=True))


def failure(code, message, action):
    emit({
        "protocolVersion": "1.0", "status": "FAILED", "nextAction": action,
        "ok": False,
        "error": {"code": code, "message": message,
                  "recoverable": True, "suggestedAction": action},
    })


def main(argv=None):
    parser = Parser(prog="mole", description="MOLE local evidence engine.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Check the bundled Python runtime.")
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable diagnostics.")
    for name in ("start", "next", "inspect", "submit", "status", "finish"):
        command = commands.add_parser(name, help=name + " a persistent analysis session.")
        command.add_argument("--workspace", required=True)
        command.add_argument("--json", action="store_true")
        if name == "start":
            command.add_argument("--repo", required=True)
            command.add_argument("--mode", choices=("quick", "standard", "deep"), default="standard")
            command.add_argument("--scope", default="repository")
        if name == "inspect":
            command.add_argument("--task", required=True)
            command.add_argument("--budget-chars", type=int, default=12000)
            command.add_argument("--cursor", default="0:0")
        if name == "submit":
            command.add_argument("--input", required=True)
        if name == "finish":
            command.add_argument("--output", required=True)
            command.add_argument("--allow-partial", action="store_true")
    try:
        args = parser.parse_args(argv)
    except InvalidRequest as exc:
        failure("INVALID_REQUEST", str(exc), "Run mole --help.")
        return 2

    if sys.version_info < (3, 11):
        failure("PYTHON_UNSUPPORTED", "MOLE requires Python 3.11 or newer.",
                "Run this entrypoint with Python 3.11+.")
        return 3

    if args.command != "doctor":
        try:
            options = vars(args).copy()
            command = options.pop("command")
            options.pop("json")
            if command == "start":
                result = pipeline.start(**options)
            else:
                result = pipeline.operate(command, **options)
            emit({"protocolVersion": "1.0", "ok": True, **result})
            return 0
        except MoleError as exc:
            failure(exc.code, str(exc), exc.action)
            return exc.exit_code
        except PermissionError:
            failure("OUTPUT_PERMISSION_DENIED", "Permission denied.", "Use an accessible workspace/output.")
            return 4
        except FileNotFoundError:
            failure("FILE_MISSING", "Required file does not exist.", "Check workspace and input paths.")
            return 2
        except OSError:
            failure("IO_ERROR", "Filesystem operation failed.", "Check paths, disk space, and permissions.")
            return 4
        except Exception:
            failure("INTERNAL_ERROR", "Unexpected engine failure.", "Preserve the workspace and report this error.")
            return 10

    result = {
        "protocolVersion": "1.0", "status": "READY", "nextAction": "start",
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
