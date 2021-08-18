import yaml

from .lazy_env import get_env, LazyEnv
from .load import safe_load
from .path import find_environment_path


def mapping():
    with open(find_environment_path()) as f:
        return safe_load(f.read())["mapping"]


env = LazyEnv()
get_env = get_env
