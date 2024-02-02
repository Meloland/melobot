@echo off
rd /s /q build dist melobot.egg-info
python setup.py sdist bdist_wheel
