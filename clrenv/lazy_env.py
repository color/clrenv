from __future__ import print_function
from builtins import object
from glob import glob
from itertools import chain
import logging
import os.path
from os import environ
import shlex
import socket
import sys
import traceback

from botocore.exceptions import EndpointConnectionError

from munch import Munch, munchify

from .load import safe_load
from .path import find_environment_path, find_user_environment_paths
from functools import reduce

logger = logging.getLogger(__name__)

# Flag to prevent clrenv from throwing errors
#  if it cannot connect to the Parameter Store API.
OFFLINE_FLAG = 'CLRENV_OFFLINE_DEV'
OFFLINE_VALUE = 'CLRENV_OFFLINE_PLACEHOLDER'

DEBUG_MODE = environ.get('CLRENV_DEBUG', '').lower() in ('true', '1')

class LazyEnv(object):
    def __init__(self):
        self.__mode = tuple(shlex.split(environ.get('CLRENV_MODE', '')))
        self.__env = None
        self.__runtime_overrides = {}

    def is_set(self):
        return self.__env is not None

    def set_mode(self, *mode):
        assert not self.is_set()
        self.__mode = mode

    def get_mode(self):
        return self.__mode

    def clear_runtime_overrides(self):
        self.__runtime_overrides.clear()

    def __getattr__(self, key):
        if self.__env is None:
            self.__env = get_env(*self.__mode)

        if key in self.__runtime_overrides:
            return self.__runtime_overrides[key]
        return getattr(self.__env, key, None)

    def __getitem__(self, key):
        return self.__getattr__(key)

    def __setattr__(self, key, value):
        # Internal fields are prefixed with a _
        if key.startswith('_'):
            return object.__setattr__(self, key, value)

        # Ideally we wouldn't be overriding global state like this at all, but at least
        # make it loud.
        logger.warning(f'Manually overriding env.{key} to {value}.')
        if DEBUG_MODE:
            # Get stack and remove this frame.
            tb = traceback.extract_stack()[:-1]
            logger.warning("".join(traceback.format_list(tb)))

        self.__runtime_overrides[key] = value

_env = {}
def get_env(*mode):
    global _env

    if not mode in _env:
        y = (_load_current_environment(),)
        upaths = find_user_environment_paths()
        y = tuple(safe_load(open(p).read()) for p in upaths if os.path.isfile(p)) + y

        assignments = tuple(m for m in mode if m.find('=') != -1)
        mode = tuple(m for m in mode if m.find('=') == -1)

        overrides = []
        for a in assignments:
            overrides.append(a.split('=', 1))

        allenvs = set(chain(*(list(x.keys()) for x in y)))
        if len(set(mode) - allenvs) != 0:
            raise EnvironmentError('Modes %s not defined anywhere' % (set(mode) - allenvs))

        dicts = reduce(lambda it, m: chain((x.get(m, {}) for x in y), it), mode, [])
        dicts = chain(dicts, (x.get('base', {}) for x in y))

        e = _merged(*dicts)

        for k, v in overrides:
            for pytype in (safe_load, eval, int, float, str):
                try:
                    pyval = pytype(v)
                    break
                except:
                    pass
            else:
                print('Failed to convert %s into anything sensible!' % v, file=sys.stderr)
                sys.exit(1)

            e = _setattr_rec(e, k, pyval)

        e = munchify(e)
        e = _glob_filenames(e)
        e = _apply_functions(e)
        e = _coerce_none_to_string(e)

        _env[mode] = e

    return _env[mode]

def _coerce_none_to_string(d):
    new = Munch()

    for k, v in list(d.items()):
        if v is None:
            v = ''
        elif isinstance(v, dict):
            v = _coerce_none_to_string(v)

        new[k] = v

    return new

def _glob_filenames(d):
    new = Munch()

    for k, v in list(d.items()):
        if isinstance(v, dict):
            v = _glob_filenames(v)
        elif isinstance(v, str):
            v = os.path.expandvars(v)
            if len(v) > 0 and v[0] in ('~', '/'):
                v = os.path.expanduser(v)
                globbed = glob(v)
                if len(globbed) > 0:
                    v = globbed[0]

        new[k] = v

    return new

def _setattr_rec(d, k, v):
    new = Munch(d)

    if k.find('.') == -1:
        new[k] = v
    else:
        this, rest = k.split('.', 1)
        if hasattr(new, this):
            new[this] = _setattr_rec(new, rest, v)
        else:
            setattr(new, k, v)

    return new

def _load_current_environment():
    with open(find_environment_path()) as f:
        environment = safe_load(f.read())
    return environment

_kf_dict_cache = {}
def _get_keyfile_cache():
    """
    To avoid loading the encrypted file for each key, cache it.
    Make sure to call _clear_keyfile_cache() once the cache is no longer needed.
    """
    import clrypt
    global _kf_dict_cache
    if not _kf_dict_cache:
        _kf_dict_cache = clrypt.read_file_as_dict('keys', 'keys')
    return _kf_dict_cache

_ssm_client = None
def _get_ssm_client():
    import boto3
    global _ssm_client
    if not _ssm_client:
        _ssm_client = boto3.client('ssm')
    return _ssm_client

def _clear_keyfile_cache():
    global _kf_dict_cache
    _kf_dict_cache = {}

def _apply_functions(d, recursive=False):
    """Apply a set of functions to the given environment. Functions
    are parsed from values of the format:

      ^function rest

    Available functions:
      ^keyfile: Looks up the given value in the current environment's clrypt keyfile.
      ^parameter: Looks up the given value in AWS Parameter store.
    """
    new = Munch()

    for key, value in list(d.items()):
        if isinstance(value, dict):
            value = _apply_functions(value, recursive=True)
        elif isinstance(value, str):
            if value.startswith('^keyfile '):
                value = value[9:]
                value = _get_keyfile_cache().get(value, '')
            elif value.startswith("^parameter "):
                parameter_name = value.split(' ', 1)[1]
                if os.environ.get(OFFLINE_FLAG):
                    logger.warning(f"[{socket.gethostname()}] Offline, using placeholder value for {parameter_name}.")
                    value = OFFLINE_VALUE
                else:
                    try:
                        value = _get_ssm_client().get_parameter(
                            Name=parameter_name,
                            WithDecryption=True
                        )['Parameter']['Value']
                    except EndpointConnectionError as e:
                        raise RuntimeError(
                            "clrenv could not connect to AWS to fetch parameters. If you're developing locally, try setting the offline environment variable (CLRENV_OFFLINE_DEV) to use placeholder values.")
                    except _get_ssm_client().exceptions.ParameterNotFound as e:
                        raise RuntimeError(
                            f"Could not find {parameter_name} in Parameter Store.")
        new[key] = value

    if not recursive:
        # Cache no longer needed, clear encrypted data.
        _clear_keyfile_cache()
    return new

def _merge(dst, src):
    """Merges src into dst, overwriting values if necessary."""
    for key in src:
        if key in dst and isinstance(dst[key], dict) and isinstance(src[key], dict):
            _merge(dst[key], src[key])
        else:
            dst[key] = src[key]
    return dst

def _merged(*dicts):
    """Merge dictionaries in *dicts, specified in priority order."""
    return reduce(_merge, reversed(dicts))
