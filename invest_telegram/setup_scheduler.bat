@echo off
REM 매일 오후 6시 자동 실행 작업 등록
REM 관리자 권한으로 실행하세요

set SCRIPT_DIR=%~dp0
set PYTHON_SCRIPT=%SCRIPT_DIR%main.py

REM Python 경로 자동 감지
for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i

echo Python 경로: %PYTHON_PATH%
echo 스크립트 경로: %PYTHON_SCRIPT%

schtasks /Create /TN "YeouidoStory_Daily_Summary" ^
  /TR "\"%PYTHON_PATH%\" \"%PYTHON_SCRIPT%\"" ^
  /SC DAILY ^
  /ST 18:00 ^
  /RL HIGHEST ^
  /F

echo.
echo [완료] 매일 오후 6시 자동 실행이 등록되었습니다.
echo 작업 이름: YeouidoStory_Daily_Summary
echo.
echo 작업 확인: schtasks /Query /TN "YeouidoStory_Daily_Summary"
echo 작업 삭제: schtasks /Delete /TN "YeouidoStory_Daily_Summary" /F
pause
