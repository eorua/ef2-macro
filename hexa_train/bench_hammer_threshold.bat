@echo off
chcp 65001 > nul
cd /d "%~dp0.."
echo ======================================================================
echo  [유물 공방] 망치 발동 임계 빈칸 수 튜닝 벤치마크 (25판 동일 시드)
echo  A: zero     - 둘 곳이 전혀 없을 때만
echo  B: free_1   - 빈칸 1개 이하일 때
echo  C: free_2   - 빈칸 2개 이하일 때
echo  D: free_3   - 빈칸 3개 이하일 때
echo  E: hub_zero - 8성 허브 우선 + 둘 곳 없을 때
echo  F: hub_free2- 8성 허브 우선 + 빈칸 2개 이하일 때
echo ======================================================================
echo.
py hexa_train\bench_hammer_threshold.py 25
if errorlevel 1 (
    python hexa_train\bench_hammer_threshold.py 25
)
pause
