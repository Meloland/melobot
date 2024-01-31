import sys
from setuptools import setup


linux_modules = (
    'uvloop>=0.17.0'
)

with open('requirements.txt') as fp:
    required = fp.read().splitlines()

if sys.platform != 'win32':
    if isinstance(linux_modules, tuple):
        required.extend(linux_modules)
    else:
        required.append(linux_modules)


setup(
    name='melobot',
    version='2.0.0-pre1',
    description='A qbot module to help build your own qbot fastly.',
    author='AiCorein',
    author_email='melodyecho@glowmem.com',
    packages=['melobot', 'melobot.core', 'melobot.interface', 'melobot.models', 'melobot.utils'],
    package_dir={
        'melobot': 'melobot',
        'melobot.core': 'melobot/core',
        'melobot.interface': 'melobot/interface',
        'melobot.models': 'melobot/models',
        'melobot.utils': 'melobot/utils'
    },
    install_requires=required
)
