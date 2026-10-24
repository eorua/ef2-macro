@echo off
rem patch244: low-grade (1-3 star) cell penalty benchmark. LOW priority. Auto-applies best setting to hexa_cfg.json.
cd /d "%~dp0"
echo Comparing low-grade penalty (about 15-30 min). Run AFTER bench_depth is finished. You can minimize this window.
start "" /low /b /wait py bench_dead.py %1
echo Done. See bench_dead_result.txt
type bench_dead_result.txt
pause
