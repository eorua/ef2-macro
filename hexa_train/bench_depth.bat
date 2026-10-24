@echo off
rem patch242: search depth benchmark (3/4/5 moves). LOW priority. Auto-applies best setting to hexa_cfg.json.
cd /d "%~dp0"
echo Comparing search depth (about 5-6 hours - good to run overnight). You can minimize this window. Do not run the hexa bot at the same time.
start "" /low /b /wait py bench_depth.py %1
echo Done. See bench_result.txt
type bench_result.txt
pause
