@echo off
rem Marcille's dependencies (Pillow, etc.) live in Python 3.14.
rem Bare "pythonw" now resolves to Python 3.10 (the RVC voice env) which lacks them,
rem so we pin the 3.14 interpreter explicitly.
set "PYW=%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe"
if exist "%PYW%" (
    start "" "%PYW%" "%~dp0marcille.py"
) else (
    rem Fallback: let the py launcher pick Python 3.14
    start "" pyw -3.14 "%~dp0marcille.py"
)
