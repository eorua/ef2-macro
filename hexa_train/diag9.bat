@echo off
rem patch251: stage-0 diagnosis - brain calibration by stage (u). LOW priority, about 20 min. No auto-apply.
cd /d "%~dp0"
echo Measuring brain calibration by stage (about 20 min). You can minimize this window.
start "" /low /b /wait py diag9.py %1
echo Done. See diag9_result.txt
