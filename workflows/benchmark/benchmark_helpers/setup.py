from setuptools import setup, find_packages
from benchmark_helpers import __version__

setup(
    name="benchmark_helpers",
    version=__version__,
    description="standalone helper functions for the idseq pipeline",
    url="",
    author="CZID Team @ Chan Zuckerberg Initiative",
    author_email="idseqhelp@chanzuckerberg.com",
    license="MIT",
    packages=find_packages(exclude=["tests.*", "tests"]),
    # boto3 1.23.x pulls botocore that imports the stdlib `cgi` module, removed in
    # Python 3.13 (the scipy-notebook base). Require a cgi-free line.
    install_requires=["boto3>=1.35"],
    tests_require=["coverage", "flake8", "wheel"],
    dependency_links=[],
    entry_points={"console_scripts": []},
    zip_safe=False,
)
