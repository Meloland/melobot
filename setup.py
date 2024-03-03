from setuptools import setup

from melobot.meta import META_INFO

with open("requirements.txt", encoding="utf-8") as fp:
    required = fp.read().splitlines()
with open("README.md", encoding="utf-8") as fp:
    readme = fp.read()

setup(
    name="melobot",
    version=META_INFO.VER,
    author=META_INFO.AUTHOR,
    author_email=META_INFO.AUTHOR_EMAIL,
    description=META_INFO.PROJ_DESC,
    long_description=readme,
    long_description_content_type="text/markdown",
    python_requires=">=3.8",
    packages=[
        "melobot",
        "melobot.core",
        "melobot.types",
        "melobot.models",
        "melobot.utils",
    ],
    package_dir={
        "melobot": "melobot",
        "melobot.core": "melobot/core",
        "melobot.types": "melobot/types",
        "melobot.models": "melobot/models",
        "melobot.utils": "melobot/utils",
    },
    install_requires=required,
)
