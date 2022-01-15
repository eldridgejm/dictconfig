from setuptools import setup, find_packages


setup(
    name="dictconfig",
    version="0.0.0",
    packages=find_packages(),
    install_requires=["jinja2"],
    tests_require=["pytest"],
)
