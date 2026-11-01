@echo off
rem Wake up Claude ojousama without a console window. If she is already running, she notices and does not start twice.
for /f "delims=" %%i in ('where pythonw 2^>nul') do (
  start "" "%%i" "%~dp0ojousama.py"
  exit /b 0
)
start "" pyw "%~dp0ojousama.py"
