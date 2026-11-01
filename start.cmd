@echo off
where py >nul 2>&1
if not errorlevel 1 goto run_py
where python >nul 2>&1
if not errorlevel 1 goto run_python
echo Task Tower requires Python 3.11+. Install it and retry. 1>&2
exit /b 2
:run_py
py -3 "%~dp0bootstrap.py" %*
exit /b %errorlevel%
:run_python
python "%~dp0bootstrap.py" %*
exit /b %errorlevel%
