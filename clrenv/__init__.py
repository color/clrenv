import yaml

from .lazy_env import get_env, LazyEnv
from .load import safe_load
from .path import environment_paths


def mapping():
    """Returns the 'mapping' map from the base enviroment file.

    This contains key names which should be turned into true enviroment
    variables.

    # TODO(michael.cusack): Refactor this so we don't need to read the yaml
    twice.
    """
    with open(environment_paths()[-1]) as f:
        return safe_load(f.read())["mapping"]


env = LazyEnv()
