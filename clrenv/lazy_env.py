import os.path
from os import environ
from glob import glob
from itertools import chain, groupby
import shlex
import sys
import types

from bunch import Bunch, bunchify
import yaml

from .path import find_environment_path, find_user_environment_paths


class LazyEnv(object):
    def __init__(self):
        self.__mode = tuple(shlex.split(environ.get('CLRENV_MODE', '')))
        self.__env = None

    def is_set(self):
        return self.__env is not None

    def set_mode(self, *mode):
        assert not self.is_set()
        self.__mode = mode

    def get_mode(self):
        return self.__mode

    def __getattr__(self, key):
        if self.__env is None:
            self.__env = get_env(*self.__mode)

        try:
            return getattr(self.__env, key)
        except AttributeError:
            return None

    def __getitem__(self, key):
        return self.__getattr__(key)

_env = {}
def get_env(*mode):
    global _env
    if not mode in _env:
        y = (_load_current_environment(),)
        upaths = find_user_environment_paths()
        y = tuple(yaml.load(open(p).read()) for p in upaths if os.path.isfile(p)) + y

        assignments = filter(lambda m: m.find('=') != -1, mode)
        mode = filter(lambda m: m.find('=') == -1, mode)

        overrides = []
        for a in assignments:
            overrides.append(a.split('=', 1))

        allenvs = set(chain(*(x.keys() for x in y)))
        if len(set(mode) - allenvs) != 0:
            raise EnvironmentError, 'Modes %s not defined anywhere' % (set(mode) - allenvs)

        dicts = reduce(lambda it, m: chain((x.get(m, {}) for x in y), it), mode, [])
        dicts = chain(dicts, (x.get('base', {}) for x in y))

        e = _mergedict(*dicts)

        for k, v in overrides:
            for pytype in (yaml.load, eval, int, float, str):
                try:
                    pyval = pytype(v)
                    break
                except:
                    pass
            else:
                print >>sys.stderr, 'Failed to convert %s into anything sensible!' % v
                sys.exit(1)

            e = _setattr_rec(e, k, pyval)

        e = bunchify(e)
        e = _glob_filenames(e)
        e = _apply_functions(e)
        e = _coerce_none_to_string(e)

        _env[mode] = e


    return _env[mode]

def _coerce_none_to_string(d):
    new = Bunch()

    for k, v in d.iteritems():
        if v is None:
            v = ''
        elif isinstance(v, dict):
            v = _coerce_none_to_string(v)

        new[k] = v

    return new

def _glob_filenames(d):
    new = Bunch()

    for k, v in d.iteritems():
        if isinstance(v, dict):
            v = _glob_filenames(v)
        elif isinstance(v, (str, unicode)):
            v = os.path.expandvars(v)
            if len(v) > 0 and v[0] in ('~', '/'):
                v = os.path.expanduser(v)
                globbed = glob(v)
                if len(globbed) > 0:
                    v = globbed[0]

        new[k] = v

    return new

def _setattr_rec(d, k, v):
    new = Bunch(d)

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
        environment = yaml.load(f.read())
    return environment

def _keyfile(path):
    import clrypt

    kf_dict = clrypt.read_file_as_dict('keys', 'keys')
    return kf_dict.get(path, '')

def _apply_functions(d):
    """Apply a set of functions to the given environment. Functions
    are parsed from values of the format:

      ^function rest

    Currently, the only function available is `keyfile', which attempts
    to replace with a value from the currently loaded keyfile."""
    new = Bunch()

    for k, v in d.iteritems():
        if isinstance(v, dict):
            v = _apply_functions(v)
        elif isinstance(v, (str, unicode)):
            if v.startswith('^keyfile '):
                v = v[9:]
                v = _keyfile(v)

        new[k] = v

    return new

def _mergedict(*dicts):
    """Merge dictionaries in *dicts, specified in priority order."""
    if len(dicts) == 1:
        return dicts[0]

    def type_for_key(key):
        types = set([type(d[key]) for d in dicts if key in d])
        if len(types) > 1:
            types.remove(type(None))
        assert len(types) == 1
        return types.pop()

    new = {}

    keys = set(chain(*[d.keys() for d in dicts]))
    for t, keys in _groupby_safe(keys, type_for_key):
        for k in keys:
            d = filter(lambda x: k in x, dicts)
            d = map(lambda x: x[k], d)

            if t == types.DictType:
                new[k] = _mergedict(*d)
            else:
                new[k] = d[0]

    return new

def _groupby_safe(iterable, keyfunc):
    """Dispatching to groupby safely -- that is, we sort the input by
    the same (required) key function before passing it to groupby."""
    return groupby(sorted(iterable, key=keyfunc), keyfunc)
