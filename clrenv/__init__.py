"""To use simply import the env variable:

from clrenv import env
celery_backend = env.clinical.celery.backend
"""
from .evaluate import RootClrEnv
import clrenv.evaluate as evaluate

env = RootClrEnv()
