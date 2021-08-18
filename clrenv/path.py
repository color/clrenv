"""
Manages environment yaml file paths.

clrenv expects a base environment file (environment.yaml) and zero or more
overlay files.

Without configuration (via env vars) looks for an environment.yaml in the cwd
or one of its parents. This can be set explicitly by setting CLRENV_PATH.

Overlay files (values will mask those set in the base file) can be specified
with the CLRENV_OVERLAY_PATH env var. Multiple overlays can be specified with a
colon (:) delimiter. Overlay files that do not exist will be ignored.
"""
from pathlib import Path
from os import environ
import logging

logger = logging.getLogger(__name__)

DEBUG_MODE = environ.get("CLRENV_DEBUG", "").lower() in ("true", "1")


def _resolve_path(path):
    """Resolves a user provided path. Returns None for empty string.

    Does not confirm the file exists.
    """
    if not path:
        return
    return Path(path).expanduser().absolute()


def _resolve_paths(paths):
    """Resolves a user provided, colon seperated, list of paths.

    Will drop values that do not exist."""
    result = []
    if not paths:
        return result

    for path in paths.split(":"):
        resolved = _resolve_path(path)
        if resolved.is_file():
            result.append(resolved)
        elif DEBUG_MODE:
            logging.warning(f'Could not find "{path}" {resolved}, ignoring it.')
    return result


def _find_in_cwd_or_parents(name):
    """Finds a file with the given name starting in the cwd and working up to root."""
    for parent in (Path().absolute() / name).parents:
        path = parent / name
        if path.is_file():
            return path


def environment_paths():
    """Returns a list of yaml paths that constitute the current enviroment.

    Files are listed in decreasing order of precedence (overlays first). Will
    not return an empty list. All returned path are guaranteed to exist.

    Raises an exception if the base environment file can not be found.
    """
    result = []
    result.extend(_resolve_paths(environ.get("CLRENV_OVERLAY_PATH")))
    base_path = _resolve_path(environ.get("CLRENV_PATH")) or _find_in_cwd_or_parents(
        "environment.yaml"
    )
    if not base_path or not base_path.is_file():
        raise ValueError(f"Base environment file could not be located. {base_path}")
    result.append(base_path)
    return result
