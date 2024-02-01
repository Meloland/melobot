import sys
from setuptools import setup

from melobot.meta import META_INFO

with open('requirements.txt') as fp:
    required = fp.read().splitlines()
extend_modules = ['uvloop>=0.17.0']
if sys.platform != 'win32':
    required.extend(extend_modules)

setup(
    name='melobot',
    version=META_INFO.VER,
    description=META_INFO.PROJ_DESC,
    author=META_INFO.AUTHOR,
    author_email=META_INFO.AUTHOR_EMAIL,
    packages=['melobot', 'melobot.core', 'melobot.types', 'melobot.models', 'melobot.utils'],
    package_dir={
        'melobot': 'melobot',
        'melobot.core': 'melobot/core',
        'melobot.types': 'melobot/types',
        'melobot.models': 'melobot/models',
        'melobot.utils': 'melobot/utils'
    },
    install_requires=required
)
