@echo off
rem ===========================================================================
rem AssetsLab 基于 dist 制品的 Godot Demo 构建/运行 (Windows)
rem
rem 直接依赖 dist\<id>\ 制品包（不再依赖工作流实例 / export.artifacts 流程）：
rem   1) 扫描 dist\ 下的制品包
rem   2) 选择制品
rem   3) 用 Godot 运行测试 demo:
rem        [1] 窗口模式运行   godot --path prototype -- --artifacts dist\<id>
rem        [2] Headless 冒烟   godot --path prototype --headless -- --artifacts dist\<id>
rem
rem 运行: scripts\build_demo.bat
rem 环境变量: GODOT_BIN / GODOT_PATH (Godot 可执行)
rem ===========================================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul
title AssetsLab Demo 构建与测试（制品驱动）
cd /d "%~dp0.."
set "ROOT=%CD%"

echo.
echo ==================================================
echo   AssetsLab - Godot Demo 构建与测试（制品驱动）
echo ==================================================

rem ---- 探测 Godot ----
set "GODOT="
if defined GODOT_BIN (
  where "%GODOT_BIN%" >nul 2>&1 && set "GODOT=%GODOT_BIN%"
)
if not defined GODOT if defined GODOT_PATH (
  if exist "%GODOT_PATH%" set "GODOT=%GODOT_PATH%"
)
if not defined GODOT (
  for %%c in (godot4 godot) do (
    where %%c >nul 2>&1 && set "GODOT=%%c"
  )
)
if not defined GODOT (
  rem 相邻 Godot-4.7\unpacked 目录（Windows console 构建）
  if exist "%ROOT%\..\Godot-4.7\unpacked\Godot_v4.7-stable_win64_console.exe" (
    set "GODOT=%ROOT%\..\Godot-4.7\unpacked\Godot_v4.7-stable_win64_console.exe"
  )
)
if not defined GODOT (
  echo [x] 未找到 Godot。请设置 GODOT_BIN/GODOT_PATH 或把 godot/godot4 加入 PATH。
  exit /b 1
)
echo [ok] Godot : %GODOT%

rem ---- 列出制品 ----
set "COUNT=0"
for /d %%d in ("%ROOT%\dist\*") do set /a COUNT+=1
if %COUNT% equ 0 (
  echo [x] dist\ 下没有制品包。请先导出制品（如工作流实例 export.artifacts），或把制品包放到 dist\。
  exit /b 1
)

:menu
echo.
echo [i] 可用制品包 (dist\)：
set /a i=0
for /d %%d in ("%ROOT%\dist\*") do (
  set /a i+=1
  if exist "%ROOT%\dist\%%~nxd\runtime_manifest.json" (
    echo   !i!^) %%~nxd    runtime_manifest [有]
  ) else (
    echo   !i!^) %%~nxd    [无 manifest]
  )
)
echo   0^) 退出
set /p "N=请选择制品编号: "
if "%N%"=="0" (
  echo 再见。
  exit /b 0
)

rem ---- 定位所选制品 ----
set "SEL="
set /a i=0
for /d %%d in ("%ROOT%\dist\*") do (
  set /a i+=1
  if !i! equ %N% set "SEL=%%~nxd"
)
if not defined SEL (
  echo [x] 无效编号。
  goto menu
)
echo.
echo [ok] 已选制品: !SEL!

:demo_menu
echo.
echo [i] 制品: !SEL!    dist\!SEL!
echo   [1] 运行 Demo（Godot 窗口）
echo   [2] Headless 冒烟测试（Ctrl+C 结束）
echo   [3] 打开制品目录
echo   [0] 返回
set /p "C=请选择: "
if "!C!"=="1" (
  "%GODOT%" --path prototype -- --artifacts "dist\!SEL!"
  goto demo_menu
)
if "!C!"=="2" (
  echo [i] 运行 headless 冒烟: %GODOT% --path prototype --headless -- --artifacts dist\!SEL!
  echo [!] 按 Ctrl+C 结束测试。
  "%GODOT%" --path prototype --headless -- --artifacts "dist\!SEL!"
  goto demo_menu
)
if "!C!"=="3" (
  if exist "%ROOT%\dist\!SEL!" (
    start "" explorer "%ROOT%\dist\!SEL!"
  ) else (
    echo [!] dist\!SEL! 不存在。
  )
  goto demo_menu
)
if "!C!"=="0" goto menu
echo [x] 无效选择。
goto demo_menu
