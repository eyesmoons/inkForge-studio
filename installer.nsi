; =============================================================
; WeChatPublisher Setup Script (NSIS)
; =============================================================

!include "MUI2.nsh"

; ── App Info ────────────────────────────────────────────────
!define APP_NAME "WeChatPublisher"
!define APP_DISPLAY "微信公众号发布助手"
!define APP_VERSION "1.0.0"
!define APP_EXE "WeChatPublisher.exe"
!define APP_ICON "AppIcon.ico"
!define COMP_NAME "WeChatPublisher Team"

; ── Output ──────────────────────────────────────────────────
OutFile "WeChatPublisher-Setup.exe"
InstallDir "$PROGRAMFILES\${APP_NAME}"
InstallDirRegKey HKLM "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

; ── Version Info ────────────────────────────────────────────
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_DISPLAY}"
VIAddVersionKey "CompanyName" "${COMP_NAME}"
VIAddVersionKey "FileDescription" "${APP_DISPLAY} Installer"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "LegalCopyright" "Copyright 2026"

; ── MUI Settings ───────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_ICON "assets\${APP_ICON}"
!define MUI_UNICON "assets\${APP_ICON}"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "assets\${APP_ICON}"

; ── MUI Pages ──────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "启动微信公众号发布助手"
!insertmacro MUI_PAGE_FINISH

; ── Uninstaller Pages ──────────────────────────────────────
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; ── Languages ───────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ── Installer Sections ─────────────────────────────────────
Section "主程序" SEC01
    SectionIn RO

    SetOutPath "$INSTDIR"

    ; 安装主程序文件
    File "dist\${APP_EXE}"
    File "assets\${APP_ICON}"

    ; 写入卸载程序
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; 写入注册表（安装信息）
    WriteRegStr HKLM "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_DISPLAY}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon" "$INSTDIR\${APP_ICON}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${COMP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1

    ; 记录安装大小（约 50MB）
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "EstimatedSize" $0
SectionEnd

Section "开始菜单快捷方式" SEC02
    CreateDirectory "$SMPROGRAMS\${APP_DISPLAY}"
    CreateShortCut "$SMPROGRAMS\${APP_DISPLAY}\${APP_DISPLAY}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_ICON}" 0
    CreateShortCut "$SMPROGRAMS\${APP_DISPLAY}\卸载${APP_DISPLAY}.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\${APP_ICON}" 0
SectionEnd

Section "桌面快捷方式" SEC03
    CreateShortCut "$DESKTOP\${APP_DISPLAY}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_ICON}" 0
SectionEnd

; ── Section Descriptions ───────────────────────────────────
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC01} "安装微信公众号发布助手主程序（必选）"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC02} "在开始菜单中创建快捷方式"
    !insertmacro MUI_DESCRIPTION_TEXT ${SEC03} "在桌面创建快捷方式"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ── Uninstaller Section ────────────────────────────────────
Section "Uninstall"

    ; 先关闭正在运行的程序
    nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE}'

    ; 删除文件
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\${APP_ICON}"
    Delete "$INSTDIR\uninstall.exe"

    ; 删除数据目录（用户数据，可选清理）
    ; RMDir /r "$APPDATA\WeChatPublisher"

    ; 删除安装目录
    RMDir "$INSTDIR"

    ; 删除快捷方式
    Delete "$SMPROGRAMS\${APP_DISPLAY}\${APP_DISPLAY}.lnk"
    Delete "$SMPROGRAMS\${APP_DISPLAY}\卸载${APP_DISPLAY}.lnk"
    RMDir "$SMPROGRAMS\${APP_DISPLAY}"
    Delete "$DESKTOP\${APP_DISPLAY}.lnk"

    ; 删除注册表
    DeleteRegKey HKLM "Software\${APP_NAME}"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

SectionEnd
