@echo off
setlocal
python "%~dp0..\tools\backup_seed_vault.py" %*
endlocal
