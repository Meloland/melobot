#!/bin/bash
rm -rf build dist melobot.egg-info
python3 setup.py sdist bdist_wheel
