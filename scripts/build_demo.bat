@echo off
rem ===========================================================================
rem AssetsLab 交互式构建并测试 Godot Demo (Windows)
rem
rem 流程:
rem   1) 选择工作流实例 (run\workflows\<id>)
rem   2) 确保制品存在 (dist\<id>) —— 缺失时可自动运行 export.artifacts 生成
rem   3) 用 Godot 运行测试 demo:
rem        [1] 窗口模式运行   godot --path prototype -- --artifacts dist\<id>
rem        [2] Headless 冒烟   godot --path prototype --headless -- --artifacts dist\<id>
rem
rem 运行: scripts\build_demo.bat
rem 环境变量: GODOT_BIN / GODOT_PATH, PYTHON_BIN
rem ===========================================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul
title AssetsLab Demo 构建与测试
cd /d "%~dp0.."
set "ROOT=%CD%"

echo.
echo ==================================================
echo   AssetsLab - Godot Demo 构建与测试（交互式）
echo ==================================================

rem ---- 探测 Python ----
set "PY="
if defined PYTHON_BIN if exist "%PYTHON_BIN%" set "PY=%PYTHON_BIN%"
if not defined PY if exist "%ROOT%\.venv\Scripts\python.exe" set "PY=%ROOT%\.venv\Scripts\python.exe"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [x] 未找到 Python。请设置 PYTHON_BIN 或使用项目 .venv。
  exit /b 1
)
echo [ok] Python: %PY%

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

rem ---- 列出实例 ----
set "COUNT=0"
for /d %%d in ("%ROOT%\run\workflows\*") do (
  if exist "%%d\state.json" set /a COUNT+=1
)
if %COUNT% equ 0 (
  echo [x] run\workflows\ 下没有实例。先创建：%PY% -m workflow new --definition default --id ^<名字^>
  exit /b 1
)

:menu
echo.
echo [i] 可用工作流实例：
set /a i=0
for /d %%d in ("%ROOT%\run\workflows\*") do (
  if exist "%%d\state.json" (
    set /a i+=1
    if exist "%ROOT%\dist\%%~nxd\runtime_manifest.json" (
      echo   !i!^) %%~nxd    制品: dist\%%~nxd [有]
    ) else (
      echo   !i!^) %%~nxd    制品: [无]
    )
  )
)
echo   0^) 退出
set /p "N=请选择实例编号: "
if "%N%"=="0" (
  echo 再见。
  exit /b 0
)

rem ---- 定位所选实例 ----
set "SEL="
set /a i=0
for /d %%d in ("%ROOT%\run\workflows\*") do (
  if exist "%%d\state.json" (
    set /a i+=1
    if !i! equ %N% set "SEL=%%~nxd"
  )
)
if not defined SEL (
  echo [x] 无效编号。
  goto menu
)
echo.
echo [ok] 已选实例: !SEL!

rem ---- 确保制品 ----
set "HAS_ARTIFACTS=0"
if exist "%ROOT%\dist\!SEL!\runtime_manifest.json" set "HAS_ARTIFACTS=1"
if "%HAS_ARTIFACTS%"=="0" (
  echo [!] 实例 !SEL! 还没有导出制品（dist\!SEL!\ 不存在）。
  echo     运行 export.artifacts 需要前 5 步已通过。
  set /p "ANS=是否现在生成? [y/N]: "
  if /i "!ANS!"=="y" (
    call "%PY%" -m workflow run --workflow !SEL! --action export.artifacts
    if exist "%ROOT%\dist\!SEL!\runtime_manifest.json" (
      echo [ok] 制品已生成: dist\!SEL!\
    ) else (
      echo [x] 制品仍未生成（可能依赖步骤未通过）。
    )
  ) else (
    echo [!] 跳过生成；没有制品时 demo 可能无法加载角色。
  )
)

:instance_menu
echo.
echo [i] 实例: !SEL!    制品: %ROOT%\dist\!SEL!
echo   [1] 运行 Demo（Godot 窗口）
echo   [2] Headless 冒烟测试（Ctrl+C 结束）
echo   [3] 重新导出制品（export.artifacts）
echo   [4] 打开制品目录
echo   [0] 返回
set /p "C=请选择: "
if "!C!"=="1" (
  "%GODOT%" --path prototype -- --artifacts "dist\!SEL!"
  goto instance_menu
)
if "!C!"=="2" (
  echo [i] 运行 headless 冒烟: %GODOT% --path prototype --headless -- --artifacts dist\!SEL!
  echo [!] 按 Ctrl+C 结束测试。
  "%GODOT%" --path prototype --headless -- --artifacts "dist\!SEL!"
  goto instance_menu
)
if "!C!"=="3" (
  call "%PY%" -m workflow run --workflow !SEL! --action export.artifacts
  goto instance_menu
)
if "!C!"=="4" (
  if exist "%ROOT%\dist\!SEL!" (
    start "" explorer "%ROOT%\dist\!SEL!"
  ) else (
    echo [!] dist\!SEL! 不存在。
  )
  goto instance_menu
)
if "!C!"=="0" goto menu
echo [x] 无效选择。
goto instance_menu
