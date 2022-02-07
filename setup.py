from setuptools import setup

requirements = ["PyYAML>=4.2", "boto3>=1.15.18"]


setup(
    name="clrenv",
    version="0.2.2",
    description="A tool to give easy access to environment yaml file to python.",
    author="Color",
    author_email="dev@getcolor.com",
    url="https://github.com/color/clrenv",
    packages=["clrenv"],
    install_requires=requirements,
    setup_requires=["pytest-runner"],
    tests_require=requirements + ["pytest", "pytest-cov"],
    license="MIT",
)
