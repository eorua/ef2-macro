@echo off
rem patch250: star10 bonus benchmark (big brain). LOW priority, about 10-15 min. Waits for bench_five. No auto-apply.
cd /d "%~dp0"
echo Comparing star10 bonus (waits for bench_five if running). You can minimize this window.
start "" /low /b /wait py bench_ten.py %1
echo Done. See bench_ten_result.txt
type bench_ten_result.txt
pause
