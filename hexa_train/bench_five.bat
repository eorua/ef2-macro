@echo off
rem patch249: 5+ merge bonus benchmark (big brain). LOW priority. Stage 1 about 10 min, stage 2 (only if promising) about 35 min. Auto-applies if better.
cd /d "%~dp0"
echo Comparing 5+ merge bonus. You can minimize this window.
start "" /low /b /wait py bench_five.py %1
echo Done. See bench_five_result.txt
type bench_five_result.txt
pause
