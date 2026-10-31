param(
    [string]$Python = "python",
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) { throw "Python not found: $Python" }

$libRoot = $root

if (-not $SkipClean) {
    foreach ($folder in @("build", "dist")) {
        $target = [IO.Path]::GetFullPath((Join-Path $root $folder))
        if ([IO.Path]::GetDirectoryName($target) -ne $root) { throw "Unsafe build path" }
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    }
}

$versionFile = Join-Path $root "build\version_info.txt"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $versionFile) | Out-Null
@'
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(0, 4, 0, 0), prodvers=(0, 4, 0, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080404b0', [
        StringStruct('CompanyName', ''),
        StringStruct('FileDescription', '\u952e\u9f20\u7535\u91cf'),
        StringStruct('FileVersion', '0.4.0'),
        StringStruct('InternalName', 'KeyMouseBattery'),
        StringStruct('OriginalFilename', 'KeyMouseBattery.exe'),
        StringStruct('ProductName', '\u952e\u9f20\u7535\u91cf'),
        StringStruct('ProductVersion', '0.4.0'),
        StringStruct('LegalCopyright', 'MIT; KeyMouseBattery contributors')])]),
    VarFileInfo([VarStruct('Translation', [0x0804, 1200])])])
'@ | Set-Content -Path $versionFile -Encoding utf8

$iconPath = Join-Path $root "assets\app.ico"
$addData = "$(Join-Path $root 'assets');assets"
$entry = Join-Path $root "KeyMouseBattery.pyw"
$logPath = Join-Path $root "build.log"

$argsList = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--name", "KeyMouseBattery",
    "--icon", $iconPath,
    "--version-file", $versionFile,
    "--add-data", $addData,
    "--paths", $libRoot,
    "--paths", $root,
    "--hidden-import", "winrt.windows.foundation",
    "--hidden-import", "winrt.windows.foundation.collections",
    "--hidden-import", "winrt.windows.storage.streams",
    "--hidden-import", "winrt.windows.devices.bluetooth",
    "--hidden-import", "winrt.windows.devices.bluetooth.advertisement",
    "--hidden-import", "winrt.windows.devices.bluetooth.genericattributeprofile",
    "--hidden-import", "winrt.windows.devices.enumeration",
    "--collect-submodules", "keymousebattery",
    $entry
)

$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python @argsList 2>&1 | Out-File -FilePath $logPath -Encoding utf8
$code = $LASTEXITCODE
$ErrorActionPreference = $previous

if ($code -ne 0) { throw "PyInstaller failed, see build.log" }

$exe = Join-Path $root "dist\KeyMouseBattery\KeyMouseBattery.exe"
"OK: $exe $((Get-Item $exe).Length) bytes"
