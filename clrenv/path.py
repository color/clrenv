import os.path
from  os import environ


CLRENV_PATH = environ.get('CLRENV_PATH', None)
CLRENV_OVERLAY_PATH = environ.get('CLRENV_OVERLAY_PATH', None)

def find_environment_path(name='environment.yaml'):
    if CLRENV_PATH:
        return CLRENV_PATH
    return _recursively_find_file_path(name)

def find_user_environment_path(name='environment.user.yaml'):
    if CLRENV_OVERLAY_PATH:
        return CLRENV_OVERLAY_PATH
    return _recursively_find_file_path(name)

def _recursively_find_file_path(name):
    path = '.'
    while os.path.split(os.path.abspath(path))[1]:
        dir_path = os.path.join(path, name)
        if os.path.exists(dir_path):
            return os.path.abspath(dir_path)
        path = os.path.join('..', path)
    raise Exception("%s could not be located." % name)
