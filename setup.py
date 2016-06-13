import os

try:
  from setuptools import setup
except:
  from distutils.core import setup


setup(name = "clrenv",
      version = "0.1.4",
      description = "A tool to give easy access to environment yaml file to python.",
      author = "Color Genomics",
      author_email = "dev@getcolor.com",
      url = "https://github.com/ColorGenomics/clrenv",
      packages = ["clrenv"],
      install_requires=[
        'PyYAML>=3.10',
        'bunch>=1.0.1',
      ],
      license = "MIT",
      )
