@echo off
rem 유물 공방 미래 조각 N개(1, 3, 5) 사전 인지 상한 실험 (LOW 우선순위)
cd /d "%~dp0"
echo Running oracle lookahead upper-bound benchmark... You can minimize this window.
start "" /low /b /wait py bench_oracle.py %1
echo Done. See bench_oracle_result.txt
type bench_oracle_result.txt
pause
