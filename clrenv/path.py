import os.path
from os import environ


CLRENV_PATH = environ.get('CLRENV_PATH')
CLRENV_OVERLAY_PATH = environ.get('CLRENV_OVERLAY_PATH')

def find_environment_path(name='environment.yaml'):
    if CLRENV_PATH:
        return CLRENV_PATH
    path = _recursively_find_file_path(name)
    if not path:
        raise Exception("%s could not be located." % name)
    return path

def find_user_environment_paths(name='environment.user.yaml'):
    if CLRENV_OVERLAY_PATH:
        return CLRENV_OVERLAY_PATH.split(':')
    path = _recursively_find_file_path(name)
    return [path] if path else []

def _recursively_find_file_path(name):
    path = '.'
    while os.path.split(os.path.abspath(path))[1]:
        dir_path = os.path.join(path, name)
        if os.path.exists(dir_path):
            return os.path.abspath(dir_path)
        path = os.path.join('..', path)
    return None
