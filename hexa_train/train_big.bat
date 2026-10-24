@echo off
rem patch233: big brain training (survive reward, 16 tuples incl. 8-cell). Runs at LOW priority.
cd /d "%~dp0"
set RMODE=1
set PRESTART=0.5
set RMIN=80
set MAXMV=5000
set TUP=tupA.txt
set TH=14
echo [%date% %time%] start >> train_big.log
echo Training big brain. You can minimize this window. Closing it stops training (progress is saved every chunk).
start "" /low /b /wait nt2.exe train big.bin 6000000 500000 0.1 %TH% >> train_big.log
start "" /low /b /wait nt2.exe train big.bin 6000000 500000 0.03 %TH% >> train_big.log
start "" /low /b /wait nt2.exe train big.bin 8000000 500000 0.01 %TH% >> train_big.log
start "" /low /b /wait nt2.exe train big.bin 4000000 500000 0.003 %TH% >> train_big.log
echo [%date% %time%] train done >> train_big.log
py install_big.py 300
echo Done. See result.txt
pause
