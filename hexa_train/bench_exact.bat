@echo off
rem patch246: exact chance-node benchmark. LOW priority. Waits for other benchmarks, then auto-applies if better.
cd /d "%~dp0"
echo Comparing exact piece averaging (about 15-30 min after other benchmarks finish). You can minimize this window.
start "" /low /b /wait py bench_exact.py %1
echo Done. See bench_exact_result.txt
type bench_exact_result.txt
echo.
rem patch247: then run the low-grade penalty benchmark (bench_dead)
echo Now running bench_dead (low-grade penalty, about 10-15 min)...
start "" /low /b /wait py bench_dead.py
echo Done. See bench_dead_result.txt
type bench_dead_result.txt
pause
