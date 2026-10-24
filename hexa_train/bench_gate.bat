@echo off
rem patch248: dead-cell gate measurement (big brain). LOW priority, about 5-10 min. No auto-apply.
cd /d "%~dp0"
echo Measuring dead cells at stage changes (about 5-10 min). You can minimize this window.
start "" /low /b /wait py bench_gate.py %1
echo Done. See bench_gate_result.txt
pause
