@echo off
chcp 65001 > nul
title 오환2 & 표키2 통합 웹 대시보드
cd /d C:\macro
echo ==================================================
echo   오환2 & 표키2 통합 웹 대시보드를 실행합니다...
echo   브라우저 주소: http://localhost:5000
echo   종료하려면 이 창을 닫거나 Ctrl + C 를 누르세요.
echo ==================================================
py web_panel.py
pause
