@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo     Termux自动架构检测安装脚本
echo ========================================
echo.

:: 检查adb是否可用
echo 正在检查ADB连接...
adb version >nul 2>&1
if errorlevel 1 (
    echo [错误] ADB未找到或未添加到系统PATH中
    echo 请确保Android SDK已安装并配置环境变量
    echo.
    pause
    exit /b 1
)

:: 获取连接的设备
echo 检查连接的设备...
set DEVICE_COUNT=0
for /f "skip=1 tokens=1,2" %%a in ('adb devices 2^>nul') do (
    if "%%b"=="device" (
        set /a DEVICE_COUNT+=1
        set DEVICE_ID=%%a
    )
)

if !DEVICE_COUNT! equ 0 (
    echo [错误] 未找到已连接的设备
    echo 请确保设备已连接并开启USB调试
    echo.
    pause
    exit /b 1
)

echo [成功] 找到 !DEVICE_COUNT! 个设备连接正常
echo 设备ID: !DEVICE_ID!
echo.

:: 获取设备架构
echo 正在获取设备架构信息...
for /f "delims=" %%i in ('adb shell getprop ro.product.cpu.abi 2^>nul') do (
    set ARCH_RAW=%%i
)

:: 清理架构字符串
set ARCH_RAW=!ARCH_RAW: =!
set ARCH_RAW=!ARCH_RAW:~0,-1!

if "!ARCH_RAW!"=="" (
    echo [错误] 无法获取设备架构信息
    echo.
    pause
    exit /b 1
)

echo [信息] 原始架构信息: !ARCH_RAW!

:: 架构标准化处理
set ARCH=!ARCH_RAW!

:: 处理各种可能的架构变体
if "!ARCH_RAW!"=="arm64-v8" set ARCH=arm64-v8a
if "!ARCH_RAW!"=="arm64-v8a" set ARCH=arm64-v8a
if "!ARCH_RAW!"=="aarch64" set ARCH=arm64-v8a

if "!ARCH_RAW!"=="armeabi-v7" set ARCH=armeabi-v7a
if "!ARCH_RAW!"=="armeabi-v7a" set ARCH=armeabi-v7a
if "!ARCH_RAW!"=="arm" set ARCH=armeabi-v7a

if "!ARCH_RAW!"=="x86" set ARCH=x86
if "!ARCH_RAW!"=="x86_64" set ARCH=x86_64
if "!ARCH_RAW!"=="x64" set ARCH=x86_64

echo [信息] 标准化架构: !ARCH!

:: 获取设备信息
for /f "delims=" %%i in ('adb shell getprop ro.product.model 2^>nul') do set DEVICE_MODEL=%%i
for /f "delims=" %%i in ('adb shell getprop ro.build.version.release 2^>nul') do set ANDROID_VERSION=%%i
set DEVICE_MODEL=!DEVICE_MODEL:~0,-1!
set ANDROID_VERSION=!ANDROID_VERSION:~0,-1!

echo [信息] 设备型号: !DEVICE_MODEL!
echo [信息] Android版本: !ANDROID_VERSION!
echo.

:: 设置Termux信息
set VERSION=v0.118.3
set BASE_URL=https://gh.llkk.cc/https://github.com/termux/termux-app/releases/latest/download

:: 根据标准化架构设置文件信息
if "!ARCH!"=="arm64-v8a" (
    set APK_FILE=termux-app_!VERSION!+github-debug_arm64-v8a.apk
    set FILE_SIZE_INFO=33.5 MB
    echo [匹配] 64位ARM架构 - 现代Android设备
    goto :arch_supported
)

if "!ARCH!"=="armeabi-v7a" (
    set APK_FILE=termux-app_!VERSION!+github-debug_armeabi-v7a.apk
    set FILE_SIZE_INFO=30.8 MB
    echo [匹配] 32位ARM架构 - 较老Android设备
    goto :arch_supported
)

if "!ARCH!"=="x86" (
    set APK_FILE=termux-app_!VERSION!+github-debug_x86.apk
    set FILE_SIZE_INFO=32.8 MB
    echo [匹配] 32位x86架构 - 模拟器
    goto :arch_supported
)

if "!ARCH!"=="x86_64" (
    set APK_FILE=termux-app_!VERSION!+github-debug_x86_64.apk
    set FILE_SIZE_INFO=33.6 MB
    echo [匹配] 64位x86架构 - 模拟器
    goto :arch_supported
)

:: 不支持的架构
echo [警告] 无法识别的架构: !ARCH_RAW! (标准化后: !ARCH!)
echo.
echo 原始架构信息: !ARCH_RAW!
echo 常见架构映射:
echo   arm64-v8, arm64-v8a, aarch64  -^> arm64-v8a   (64位ARM)
echo   armeabi-v7, armeabi-v7a, arm  -^> armeabi-v7a (32位ARM)
echo   x86                           -^> x86         (32位x86)
echo   x86_64, x64                   -^> x86_64      (64位x86)
echo.
echo 支持的架构版本:
echo   arm64-v8a    (64位ARM, 现代设备) - 33.5 MB
echo   armeabi-v7a  (32位ARM, 旧设备)   - 30.8 MB
echo   x86          (32位x86, 模拟器)   - 32.8 MB
echo   x86_64       (64位x86, 模拟器)   - 33.6 MB
echo.
set /p "choice=是否下载通用版本 (支持所有架构, 112 MB)? [y/N]: "
if /i "!choice!"=="y" (
    set APK_FILE=termux-app_!VERSION!+github-debug_universal.apk
    set FILE_SIZE_INFO=112 MB
    echo [选择] 通用版本: !APK_FILE!
) else (
    echo.
    echo 请手动下载：https://github.com/termux/termux-app/releases/latest
    echo 查找适合 "!ARCH_RAW!" 架构的版本
    pause
    exit /b 1
)

:arch_supported
set DOWNLOAD_URL=!BASE_URL!/!APK_FILE!

echo [目标] 文件: !APK_FILE!
echo [大小] 预计: !FILE_SIZE_INFO!
echo [地址] !DOWNLOAD_URL!
echo.

:: 检查文件是否存在
if exist "!APK_FILE!" (
    echo [信息] 本地文件已存在，跳过下载
    goto :install_check
)

:: 开始下载
echo ========================================
echo 开始下载 Termux APK
echo ========================================
echo.

:: 使用curl下载（Windows 10 1803+自带）
where curl >nul 2>&1
if not errorlevel 1 (
    echo 使用 curl 下载，显示进度...
    curl -L --progress-bar -o "!APK_FILE!" "!DOWNLOAD_URL!"
    if errorlevel 1 (
        echo [错误] curl下载失败
        goto :download_fallback
    )
    goto :download_success
)

:download_fallback
echo curl不可用，尝试使用PowerShell下载...
echo 正在下载，请稍候...

:: 创建PowerShell下载脚本，显示进度
echo $url = "!DOWNLOAD_URL!" > download.ps1
echo $output = "!APK_FILE!" >> download.ps1
echo try { >> download.ps1
echo     $wc = New-Object System.Net.WebClient >> download.ps1
echo     $wc.DownloadProgressChanged = { >> download.ps1
echo         param($sender, $e) >> download.ps1
echo         $percent = [math]::Round(($e.BytesReceived / $e.TotalBytesToReceive) * 100, 1) >> download.ps1
echo         $received = [math]::Round($e.BytesReceived / 1MB, 1) >> download.ps1
echo         $total = [math]::Round($e.TotalBytesToReceive / 1MB, 1) >> download.ps1
echo         Write-Host "`r下载进度: $percent%% ($received MB / $total MB)" -NoNewline >> download.ps1
echo     } >> download.ps1
echo     $wc.DownloadFileCompleted = { >> download.ps1
echo         param($sender, $e) >> download.ps1
echo         Write-Host "`n[成功] 下载完成" >> download.ps1
echo     } >> download.ps1
echo     $wc.DownloadFileAsync($url, $output) >> download.ps1
echo     while ($wc.IsBusy) { Start-Sleep -Milliseconds 100 } >> download.ps1
echo     $wc.Dispose() >> download.ps1
echo } catch { >> download.ps1
echo     Write-Host "`n[错误] 下载失败: $($_.Exception.Message)" >> download.ps1
echo     exit 1 >> download.ps1
echo } >> download.ps1

powershell -ExecutionPolicy Bypass -File download.ps1
set DOWNLOAD_RESULT=!errorlevel!
del download.ps1 >nul 2>&1

if !DOWNLOAD_RESULT! neq 0 (
    echo.
    echo [错误] 下载失败
    echo.
    echo 请尝试以下方案:
    echo 1. 检查网络连接
    echo 2. 手动下载: !DOWNLOAD_URL!
    echo 3. 保存为: !APK_FILE!
    echo 4. 重新运行脚本
    echo.
    pause
    exit /b 1
)

:download_success
echo.
echo [成功] 下载完成
echo.

:install_check
:: 验证文件完整性
if not exist "!APK_FILE!" (
    echo [错误] APK文件不存在
    pause
    exit /b 1
)

:: 显示文件信息
for %%F in ("!APK_FILE!") do (
    set FILE_SIZE=%%~zF
    set /a FILE_SIZE_MB=!FILE_SIZE!/1024/1024
)
echo [文件] 大小: !FILE_SIZE_MB! MB

:: 检查已安装的Termux
echo.
echo 检查现有Termux安装...
adb shell pm list packages com.termux 2>nul | findstr "com.termux" >nul
if not errorlevel 1 (
    echo [发现] 设备上已安装Termux

    :: 获取已安装版本信息
    for /f "delims=" %%i in ('adb shell dumpsys package com.termux ^| findstr "versionName" 2^>nul') do set CURRENT_VERSION=%%i
    echo [版本] !CURRENT_VERSION!

    set /p "uninstall=是否卸载旧版本后重新安装? [Y/n]: "
    if /i not "!uninstall!"=="n" (
        echo 正在卸载旧版本...
        adb uninstall com.termux
        if not errorlevel 1 (
            echo [成功] 旧版本已卸载
        ) else (
            echo [警告] 卸载失败，继续尝试覆盖安装
        )
    )
)

:: 安装APK
echo.
echo ========================================
echo 开始安装 Termux
echo ========================================
echo.
echo [安装] 正在安装到设备...
echo [架构] 原始: !ARCH_RAW! -^> 标准: !ARCH!
echo [文件] !APK_FILE!

:: 先尝试普通安装
adb install "!APK_FILE!" >install.log 2>&1
if not errorlevel 1 (
    echo [成功] Termux 安装完成！
    goto :install_success
)

:: 普通安装失败，尝试替换安装
echo [重试] 尝试替换安装...
adb install -r "!APK_FILE!" >install.log 2>&1
if not errorlevel 1 (
    echo [成功] Termux 替换安装完成！
    goto :install_success
)

:: 替换安装失败，尝试授权安装
echo [重试] 尝试授权安装...
adb install -r -g "!APK_FILE!" >install.log 2>&1
if not errorlevel 1 (
    echo [成功] Termux 授权安装完成！
    goto :install_success
)

:: 所有自动安装都失败
echo [失败] 自动安装失败
echo.
echo 错误信息:
type install.log 2>nul
echo.
echo ========================================
echo 手动安装方案:
echo ========================================
echo.
echo 方法1 - 命令行安装:
echo   adb install -r -g "!APK_FILE!"
echo.
echo 方法2 - 传输到设备:
echo   adb push "!APK_FILE!" /sdcard/Download/
echo   然后在文件管理器中手动安装
echo.
echo 方法3 - 强制安装:
echo   adb install -r -d -g "!APK_FILE!"
echo.
echo 方法4 - 完全重装:
echo   adb uninstall com.termux
echo   adb install "!APK_FILE!"
echo.
echo ========================================
echo 手动安装后的重要步骤:
echo ========================================
echo.
echo 1. 手动安装APK完成后，请先打开 Termux 应用
echo 2. 等待 Termux 完成初始化 (显示"正在初始化"提示，约30-60秒)
echo 3. 初始化完成后，执行:
echo    adb shell
echo    sh /sdcard/termux-init.sh
echo 4. 根据提示选择对应的机型选项
echo.
del install.log >nul 2>&1
goto :manual_install_end

:install_success
echo.
echo ========================================
echo 安装成功！
echo ========================================
echo.
echo 应用信息:
echo   名称: Termux Terminal Emulator
echo   版本: !VERSION!
echo   架构: !ARCH_RAW! (标准化: !ARCH!)
echo   包名: com.termux
echo   文件: !APK_FILE!
echo.

:: 检查termux-init.sh文件是否存在
echo 检查 termux-init.sh 初始化脚本...
if not exist "termux-init.sh" (
    echo [错误] 未找到 termux-init.sh 文件
    echo 请确保 termux-init.sh 文件与此批处理脚本在同一目录
    echo.
    pause
    goto :manual_install_end
)

:: 推送初始化脚本到设备
echo [推送] 正在推送 termux-init.sh 到设备...
adb push termux-init.sh /sdcard/ >nul 2>&1
if not errorlevel 1 (
    echo [成功] termux-init.sh 已推送到设备: /sdcard/termux-init.sh
) else (
    echo [警告] 无法推送 termux-init.sh 到设备
    echo 请手动复制文件到设备的 /sdcard/ 目录
)

:: 清理临时文件
del install.log >nul 2>&1

echo.
echo ========================================
echo 自动启动 Termux 应用
echo ========================================
echo.
echo [启动] 正在打开 Termux 应用...

:: 启动Termux应用
adb shell am start -n com.termux/.HomeActivity >nul 2>&1
if not errorlevel 1 (
    echo [成功] Termux 应用已启动
    echo.
    echo 设备上应该已经打开了 Termux 应用
    echo 请观察设备屏幕，等待初始化完成
) else (
    echo [警告] 无法自动启动 Termux，请手动打开
)

echo.
echo ========================================
echo 重要使用步骤:
echo ========================================
echo.
echo 第1步: 等待 Termux 初始化
echo   - Termux 应用已自动启动
echo   - 首次打开会显示"正在初始化"
echo   - 等待初始化完全完成 (约30-60秒)
echo   - 直到看到终端提示符 ($)
echo.
echo 第2步: 执行初始化配置
echo   打开新的CMD窗口，输入:
echo   adb shell
echo   sh /sdcard/termux-init.sh
echo.
echo 第3步: 选择对应的机型选项
echo   根据设备型号选择相应选项 (1-5)
echo.
echo 第4步: 使用生成的脚本
echo   - 使用: sh /sdcard/termux-shell.sh
echo.
echo 注意事项:
echo - 确保 termux-init.sh 文件与此脚本在同一目录
echo - 确保 Termux 完成初始化后再执行 sh /sdcard/termux-init.sh
echo - root 环境下 pkg 包管理器不可用
echo.

:manual_install_end

:end
echo ========================================
echo 脚本执行完成
echo 当前时间: %date% %time%
echo 用户: crowforkotlin
echo ========================================
echo.
echo 请确保:
echo 1. termux-init.sh 文件在同一目录
echo 2. Termux 应用已正常启动并完成初始化
echo 3. 执行 adb shell 后运行 sh /sdcard/termux-init.sh
echo.
pause