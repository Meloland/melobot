import datetime
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath("../../src/"))
import melobot

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "melobot"
author = "contributors of this doc"
copyright = f"{datetime.date.today().year}, {author}"
release = melobot.__version__

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
    "special-members": "__init__, __call__, __await__",
    "show-inheritance": True,
    "undoc-members": True,
}

templates_path = ["_templates"]
exclude_patterns = []
pygments_style = "default"
pygments_dark_style = "monokai"
language = "zh_CN"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_title = f"{project} {release}"
html_baseurl = "/melobot/"
html_logo = "_static/logo.png"
html_theme = "furo"
html_theme_options = {
    "source_edit_link": "https://github.com/Meloland/melobot/tree/main/docs/source/{filename}",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/Meloland/melobot",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
}
html_static_path = ["_static"]


# def fix_type_annotation(app, what, name, obj, options, signature, return_annotation):
#     if name == "melobot.utils.CmdArgFormatter.__init__":
#         return (
#             signature.replace("<class 'melobot.base.typing.Void'>", "Void"),
#             return_annotation,
#         )

#     if (
#         inspect.isfunction(obj)
#         and obj.__name__ in _need_ret_fix_funcs
#         and return_annotation == "~melobot.base.abc.BotAction"
#     ):
#         return signature, "~melobot.context.ActionHandle"
#     else:
#         return signature, return_annotation


# def setup(app):
#     app.connect("autodoc-process-signature", fix_type_annotation)
