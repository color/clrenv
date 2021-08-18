"""
This module exists to provide a faster, yet equally secure version of `safe_load`
"""
import yaml

try:
    # If available, use the C bindings for far, far faster loading
    # See: https://pyyaml.org/wiki/PyYAMLDocumentation
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    # If the C bindings aren't available, fall back to the "much slower" Python bindings
    from yaml import SafeLoader


def safe_load(str_content):
    """Safely load YAML, doing so quickly with C bindings if available.

    By default, `yaml.safe_load()` uses the (slower) Python bindings.
    This method is a stand-in replacement that can be considerably faster.
    """
    return yaml.load(str_content, Loader=SafeLoader)
