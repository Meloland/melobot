@echo off
set "DIR=%~dp0"
cd /d "%DIR%"
pip install .
rd /s /q build
rd /s /q melobot.egg-info
