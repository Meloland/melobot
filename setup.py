import sys
from setuptools import setup


unixlike_uniques = (
    'uvloop>=0.17.0'
)

with open('requirements.txt') as fp:
    required = fp.read().splitlines()

if sys.platform != 'win32':
    required.extend(unixlike_uniques)

setup(
    name='melobot',
    version='2.0.0',
    description='A qbot module to help build your own qbot fastly.',
    author='AiCorein',
    author_email='melodyecho@glowmem.com',
    packages=['melobot', 'melobot.core', 'melobot.interface', 'melobot.models', 'melobot.utils'],
    install_requires=required,
)