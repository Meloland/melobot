from setuptools import setup

from melobot.meta import MetaInfo

with open("requirements.txt", encoding="utf-8") as fp:
    required = fp.read().splitlines()
with open("README.md", encoding="utf-8") as fp:
    readme = fp.read()

META_INFO = MetaInfo()
setup(
    name="melobot",
    version=META_INFO.VER,
    author=META_INFO.AUTHOR,
    author_email=META_INFO.AUTHOR_EMAIL,
    description=META_INFO.PROJ_DESC,
    long_description=readme,
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    packages=[
        "melobot",
        "melobot.io",
        "melobot.context",
        "melobot.controller",
        "melobot.models",
        "melobot.plugin",
        "melobot.types",
        "melobot.utils",
    ],
    package_dir={
        "melobot": "melobot",
        "melobot.botio" : "melobot/io",
        "melobot.context" : "melobot/context",
        "melobot.controller" : "melobot/controller",
        "melobot.models" : "melobot/models",
        "melobot.plugin" : "melobot/plugin",
        "melobot.types" : "melobot/types",
        "melobot.utils" : "melobot/utils",
    },
    install_requires=required,
)
