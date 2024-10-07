from sphinx.cmd.build import build_main

build_main(["-b", "html", "-d", "build/doctrees", "source", "build/html"])
