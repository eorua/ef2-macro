@echo off
rem patch253: plan B (search-policy TD training) steps 1-5. Does not change hexa_nt_w.bin or hexa_cfg.json.
rem Re-run to resume: finished steps (b_*.done) are skipped. Results: train_b_result.txt
chcp 65001 >nul
cd /d "%~dp0"
echo Plan B steps 1-5 (about 1-1.5 hours). You can minimize this window. Closing it stops the run.
start "" /low /b /wait py train_b.py %*
echo.
echo Done. See train_b_result.txt
pause
