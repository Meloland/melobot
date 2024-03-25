import inspect
import os
import sys

sys.path.insert(0, os.path.abspath("../../src/"))
import melobot

_need_ret_fix_funcs = melobot.context.action.__all__

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "MeloBot"
copyright = "2024, aicorein"
author = "aicorein"
release = "2.5.5"

html_baseurl = "/melobot/"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinx_copybutton",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

autodoc_class_signature = "separated"
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
}

templates_path = ["_templates"]
exclude_patterns = []

language = "zh_CN"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]


def fix_annotation(app, what, name, obj, options, signature, return_annotation):
    if name == "melobot.utils.ArgFormatter.__init__":
        return (
            signature.replace("<class 'melobot.base.typing.Void'>", "Void"),
            return_annotation,
        )

    if (
        inspect.isfunction(obj)
        and obj.__name__ in _need_ret_fix_funcs
        and return_annotation == "~melobot.base.abc.BotAction"
    ):
        _return_annotation = "ResponseEvent | BotAction | None"
        if obj.__name__ == "take_custom_action":
            _return_annotation = "ResponseEvent | None"
        if obj.__name__ == "make_action":
            _return_annotation = "~melobot.base.abc.BotAction"
        return signature, _return_annotation
    else:
        return signature, return_annotation


def setup(app):
    app.connect("autodoc-process-signature", fix_annotation)
