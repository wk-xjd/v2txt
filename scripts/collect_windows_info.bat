@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "OUTPUT=%~dp0v2txt-machine-info.txt"

echo Collecting Windows machine information for v2txt...

(
echo v2txt Windows Machine Information
echo =================================
echo Collected: %DATE% %TIME%
echo.

echo [Computer]
powershell.exe -NoLogo -NoProfile -Command "$c=Get-CimInstance Win32_ComputerSystem; [PSCustomObject]@{Manufacturer=$c.Manufacturer; Model=$c.Model; SystemType=$c.SystemType} | Format-List | Out-String -Width 200"

echo [CPU]
powershell.exe -NoLogo -NoProfile -Command "$c=Get-CimInstance Win32_Processor | Select-Object -First 1; [PSCustomObject]@{Name=$c.Name.Trim(); PhysicalCores=$c.NumberOfCores; LogicalProcessors=$c.NumberOfLogicalProcessors; MaxClockMHz=$c.MaxClockSpeed} | Format-List | Out-String -Width 200"

echo [Memory]
powershell.exe -NoLogo -NoProfile -Command "$c=Get-CimInstance Win32_ComputerSystem; $o=Get-CimInstance Win32_OperatingSystem; [PSCustomObject]@{InstalledGB=[math]::Round($c.TotalPhysicalMemory/1GB,1); AvailableGB=[math]::Round($o.FreePhysicalMemory/1MB,1); Modules=((Get-CimInstance Win32_PhysicalMemory | ForEach-Object {('{0}GB {1}MHz' -f [math]::Round($_.Capacity/1GB,1),$_.ConfiguredClockSpeed)}) -join ', ')} | Format-List | Out-String -Width 200"

echo [Windows]
powershell.exe -NoLogo -NoProfile -Command "$o=Get-CimInstance Win32_OperatingSystem; [PSCustomObject]@{Name=$o.Caption; Version=$o.Version; Build=$o.BuildNumber; Architecture=$o.OSArchitecture} | Format-List | Out-String -Width 200"

echo [Physical Disks]
powershell.exe -NoLogo -NoProfile -Command "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,@{N='SizeGB';E={[math]::Round($_.Size/1GB)}},HealthStatus | Format-Table -AutoSize | Out-String -Width 200"

echo [Drive Free Space]
powershell.exe -NoLogo -NoProfile -Command "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,@{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},@{N='FreeGB';E={[math]::Round($_.FreeSpace/1GB,1)}} | Format-Table -AutoSize | Out-String -Width 200"

echo [Graphics]
powershell.exe -NoLogo -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion | Format-Table -AutoSize | Out-String -Width 200"

echo [Power Plan]
powercfg.exe /getactivescheme
echo.

echo [v2txt Prerequisites]
where.exe uv 2^>nul || echo uv: not found
where.exe ffmpeg 2^>nul || echo ffmpeg: not found
where.exe ffprobe 2^>nul || echo ffprobe: not found
echo.

echo Privacy note: no serial number, product key, user files, or network configuration was collected.
) > "%OUTPUT%" 2>&1

echo.
type "%OUTPUT%"
echo.
echo Saved to:
echo %OUTPUT%
echo.
echo You can send this text file for v2txt performance tuning.
pause
endlocal
