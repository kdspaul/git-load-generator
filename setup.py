"""Setup script for git-load-tester."""

from setuptools import setup, find_packages

setup(
    name="git-load-tester",
    version="0.1.0",
    description="A Git protocol load testing tool for HTTPS and SSH",
    author="git-load-tester contributors",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "paramiko>=3.4.0",
    ],
    entry_points={
        "console_scripts": [
            "git-load-tester=git_load_tester.main:main",
        ],
    },
    python_requires=">=3.8",
)
