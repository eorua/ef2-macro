@echo off
rem patch251: multi-stage step0 diagnosis (value calibration by u). LOW priority, about 20 min. No setting change.
cd /d "%~dp0"
echo Running calibration diagnosis... You can minimize this window.
start "" /low /b /wait py bench_calib.py %1
echo Done. See bench_calib_result.txt
type bench_calib_result.txt
