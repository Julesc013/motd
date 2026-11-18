# Native PowerShell MOTD. Language baseline: Windows PowerShell 1.0 / .NET 2.
# Current engines are tested separately; old syntax does not certify an old OS.
# No JSON parser, advanced-function attributes, try/catch, -join/-split, -in,
# generic type syntax, PS3 automatic variables, or implicit execution-policy change.
# Invoke with & ./message.ps1; do not dot-source it into an ordinary profile.
#Requires -Version 1.0
param(
    [switch] $Demo,
    [switch] $DemoAlerts,
    [switch] $Plain,
    [switch] $Color,
    [switch] $Ascii,
    [switch] $Unicode,
    [switch] $NoHooks,
    [int] $Width = 0,
    [int] $Rows = 0,
    [string] $BarLayout = '',
    [string] $Design = '',
    [string] $Density = '',
    [string] $Detail = '',
    [string] $ColorEmphasis = '',
    [int] $Padding = -1,
    [int] $SectionGap = -1,
    [string] $PanelLayout = '',
    [string] $PanelFrame = '',
    [string] $HeadingStyle = '',
    [string] $BorderStyle = '',
    [string] $BorderVisibility = '',
    [string] $HeadingAlign = '',
    [string] $SeparatorText = '',
    [string] $LabelStyle = '',
    [string] $Overflow = '',
    [switch] $Version,
    [switch] $Help
)

# @MOTD_CONFIG@

if ($Version) { Write-Output ('MOTD ' + $MotdVersion + ' (native PowerShell 1+ syntax)'); return }
if ($Help) {
    Write-Output 'MOTD PowerShell: -Demo -DemoAlerts -Plain -Color -Ascii -Unicode -NoHooks -Width 40..240 -Rows 8..200'
    Write-Output 'Resource bars: -BarLayout inline|wide (numeric labels remain when space is limited).'
    Write-Output 'Presentation: -Design classic|cards|dashboard|ledger|briefing -PanelLayout auto|stack|columns -PanelFrame auto|continuous|separate|none'
    Write-Output 'Headings: -HeadingStyle auto|rule|plain|inline|hidden -HeadingAlign left|center|right -SeparatorText none|summary|custom'
    Write-Output 'Borders: -BorderStyle single|rounded|double|heavy|ascii -BorderVisibility all|outer|sections|none'
    Write-Output 'Text: -LabelStyle full|short -Overflow ellipsis|clip -Density compact|balanced|comfortable -Detail brief|normal|full'
    Write-Output 'Spacing: -Padding 0..3 -SectionGap 0..2 -ColorEmphasis quiet|balanced|vivid'
    Write-Output 'Demonstrations use synthetic data and never run before/after calls.'
    Write-Output 'Local capability checks select CIM, WMI, .NET or Unix sources. Unavailable is not zero.'
    return
}
if ($Width -ne 0 -and ($Width -lt 40 -or $Width -gt 240)) { throw 'Width must be 40..240, or 0 for the recipe.' }
if ($Rows -ne 0 -and ($Rows -lt 8 -or $Rows -gt 200)) { throw 'Rows must be 8..200, or 0 for the recipe.' }
$MotdBarLayout = 'inline'
if ($MotdConfig['display'].ContainsKey('bar_layout')) { $MotdBarLayout = [string]$MotdConfig['display']['bar_layout'] }
if ($BarLayout -ne '') { $MotdBarLayout = $BarLayout }
if ($MotdBarLayout -ne 'inline' -and $MotdBarLayout -ne 'wide') { throw 'BarLayout must be inline or wide.' }
# CLI overrides are data. Validate before collection and before configured calls.
$MotdOverrides = @{
    design = $Design; density = $Density; detail = $Detail; color_emphasis = $ColorEmphasis
    panel_layout = $PanelLayout; panel_frame = $PanelFrame; heading_style = $HeadingStyle
    border_style = $BorderStyle; border_visibility = $BorderVisibility
    heading_align = $HeadingAlign; separator_text = $SeparatorText; label_style = $LabelStyle; overflow = $Overflow
}
$MotdChoices = @{
    design = @('classic','cards','dashboard','ledger','briefing'); density = @('compact','balanced','comfortable')
    detail = @('brief','normal','full'); color_emphasis = @('quiet','balanced','vivid')
    panel_layout = @('auto','stack','columns'); panel_frame = @('auto','continuous','separate','none')
    heading_style = @('auto','rule','plain','inline','hidden'); border_style = @('single','rounded','double','heavy','ascii')
    border_visibility = @('all','outer','sections','none'); heading_align = @('left','center','right')
    separator_text = @('none','summary','custom'); label_style = @('full','short'); overflow = @('ellipsis','clip')
}
foreach ($key in $MotdOverrides.Keys) {
    if ($MotdOverrides[$key] -ne '') { $MotdConfig['display'][$key] = $MotdOverrides[$key] }
    if ($MotdConfig['display'].ContainsKey($key) -and -not ($MotdChoices[$key] -contains $MotdConfig['display'][$key])) {
        throw ('Invalid presentation setting: ' + $key)
    }
}
if ($Padding -lt -1 -or $Padding -gt 3) { throw 'Padding must be 0..3.' }
if ($SectionGap -lt -1 -or $SectionGap -gt 2) { throw 'SectionGap must be 0..2.' }
if ($Padding -ge 0) { $MotdConfig['display']['padding'] = $Padding }
if ($SectionGap -ge 0) { $MotdConfig['display']['section_gap'] = $SectionGap }
if ($DemoAlerts) { $Demo = $true }

# The mutable result object is shared with trap's child scope. A failed read
# cannot fall through into a successful/zero observation. Unlike try/catch this
# syntax exists in PowerShell 1. A partial result is rejected when Ok is false.
function Read-MotdObservation([scriptblock] $Action) {
    $result = @{ Ok = $true; Value = $null; Error = '' }
    $ErrorActionPreference = 'Stop'
    trap { $result.Ok = $false; $result.Error = $_.Exception.Message; continue }
    $result.Value = @(& $Action)
    return $result
}

function New-MotdList { return ,(New-Object System.Collections.ArrayList) }
function Test-MotdCommand([string] $Name) { return (@(Get-Command $Name -ErrorAction SilentlyContinue).Count -gt 0) }
function Join-MotdText($Items, [string] $Separator) { return [string]::Join($Separator, [string[]]@($Items)) }

$MotdWindows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
$MotdEngine = '1.0'
if ($PSVersionTable -and $PSVersionTable.PSVersion) { $MotdEngine = [string]$PSVersionTable.PSVersion }
$MotdMajor = [int]$MotdEngine.Split('.')[0]
$MotdWidth = [int]$MotdConfig['display']['width']
$MotdHeight = [int]$MotdConfig['display']['rows']
if ($Width) { $MotdWidth = $Width }
if ($Rows) { $MotdHeight = $Rows }
if (-not $Width -or -not $Rows) {
    $geometry = Read-MotdObservation { $Host.UI.RawUI.WindowSize }
    if ($geometry.Ok -and $geometry.Value.Count -gt 0) {
        if (-not $Width -and $geometry.Value[0].Width -ge 40) { $MotdWidth = [Math]::Min($MotdWidth, [int]$geometry.Value[0].Width) }
        if (-not $Rows -and $geometry.Value[0].Height -ge 8) { $MotdHeight = [Math]::Min($MotdHeight, [int]$geometry.Value[0].Height) }
    }
}
# Saved appearance choices act as defaults. Explicit positive switches override
# them without PS2's BoundParameters variable, preserving the PS1 grammar target.
if (-not $Ascii -and -not $Unicode) {
    switch ($MotdConfig['display']['charset']) {
        'ascii' { $Ascii = $true }
        'unicode' { $Unicode = $true }
    }
}
if (-not $Plain -and -not $Color) {
    switch ($MotdConfig['display']['color']) {
        'never' { $Plain = $true }
        'always' { $Color = $true }
    }
}
# Old .NET returns null for an existing empty value. Enumerating the legacy
# IDictionary tests key presence correctly without depending on its value.
$MotdEnvironment = [Environment]::GetEnvironmentVariables()
$MotdNoColor = $MotdEnvironment.Contains('NO_COLOR')
$MotdColor = -not $Plain -and -not $MotdNoColor -and $MotdConfig['display']['theme'] -ne 'mono'
if (-not $Color) {
    $terminal = Read-MotdObservation { $Host.UI.SupportsVirtualTerminal -and -not [Console]::IsOutputRedirected }
    $MotdColor = $MotdColor -and $terminal.Ok -and $terminal.Value.Count -gt 0 -and $terminal.Value[0]
}
$MotdAccent = '36'
switch ($MotdConfig['display']['theme']) { 'green' { $MotdAccent = '32' } 'amber' { $MotdAccent = '33' } }
$MotdEscape = [string][char]27
$MotdNotices = New-MotdList
$MotdSections = @{}
$MotdSectionOrder = @($MotdConfig['display']['sections'])
$MotdCurrentSection = ''
$MotdProcesses = $null
$MotdQueryCache = @{}

function ConvertTo-MotdText([object] $Value) {
    $safe = [regex]::Replace([string]$Value, '[\x00-\x1f\x7f-\x9f]', '?')
    if ($Ascii) { $safe = [regex]::Replace($safe, '[^\x20-\x7e]', '?') }
    return $safe
}

function Add-MotdLine([string] $Text, [string] $Tone = 'normal') {
    $section = $MotdSections[$MotdCurrentSection]
    [void]$section.Lines.Add(@{ Text = (ConvertTo-MotdText $Text); Tone = $Tone })
}

function Format-MotdBytes([double] $Bytes) {
    if ($Bytes -lt 0) { return 'unavailable' }
    if ($Bytes -ge 1073741824.0) { return ('{0:N1} GiB' -f ($Bytes / 1073741824.0)) }
    return ('{0:N0} MiB' -f ($Bytes / 1048576.0))
}

function Format-MotdShortBytes([double] $Bytes) {
    if ($Bytes -lt 0) { return '?' }
    if ($Bytes -ge 1073741824.0) { return ('{0:N1}G' -f ($Bytes / 1073741824.0)) }
    if ($Bytes -ge 1048576.0) { return ('{0:N0}M' -f ($Bytes / 1048576.0)) }
    if ($Bytes -ge 1024.0) { return ('{0:N0}K' -f ($Bytes / 1024.0)) }
    return ('{0:N0}B' -f $Bytes)
}

function Format-MotdBar([double] $Used, [double] $Total, [int] $OuterWidth = 0) {
    if ($Total -le 0 -or $Used -lt 0 -or $Used -gt $Total) { return '[unavailable]' }
    $length = 12
    if ((Get-MotdResourceWidth) -lt 60) { $length = 8 }
    if ($OuterWidth -gt 2) { $length = $OuterWidth - 2 }
    $filled = [int][Math]::Round($length * [Math]::Max(0.0, [Math]::Min(1.0, $Used / $Total)))
    $full = '#'; $empty = '-'
    if ($Unicode -and -not $Ascii) { $full = [string][char]0x2588; $empty = [string][char]0x2591 }
    return '[' + ($full * $filled) + ($empty * ($length - $filled)) + ']'
}

function Get-MotdResourceWidth {
    if ($MotdPresentation.Layout -eq 'columns') { return [int][Math]::Floor(($MotdWidth - 2) / 2) }
    return $MotdWidth
}

function Get-MotdWideResourceWidth {
    $width = (Get-MotdResourceWidth) - 2 * $MotdPresentation.Padding
    if ($MotdPresentation.Outer -or $MotdPresentation.Cards) { $width -= 2 }
    return [Math]::Max(3, $width)
}

function Add-MotdWideResource([string] $Label, [double] $Used, [double] $Total, [bool] $AllowEmpty = $false) {
    if ($AllowEmpty -and $Total -eq 0 -and $Used -eq 0) {
        Add-MotdLine ($Label + ': not configured') 'muted'
    } elseif ($Total -le 0 -or $Used -lt 0 -or $Used -gt $Total) {
        Add-MotdLine ($Label + ': unavailable') 'warning'
    } else {
        Add-MotdLine ($Label + ' ' + (Format-MotdShortBytes $Used) + '/' + (Format-MotdShortBytes $Total) + ' used') 'accent'
        Add-MotdLine (Format-MotdBar $Used $Total (Get-MotdWideResourceWidth)) 'accent'
        # Keep the fraction alongside its formatted row. An unpaired dashboard
        # card can expand after planning; the renderer then refits this same
        # observation to its actual width without querying anything again.
        $lines = $MotdSections[$MotdCurrentSection].Lines
        $lines[$lines.Count - 1]['BarUsed'] = $Used
        $lines[$lines.Count - 1]['BarTotal'] = $Total
    }
}

function ConvertTo-MotdWindowsArgument([string] $Argument) {
    $quoted = [regex]::Replace($Argument, '(\\*)"', '${1}${1}\"')
    $quoted = [regex]::Replace($quoted, '(\\+)$', '${1}${1}')
    return '"' + $quoted + '"'
}

function Set-MotdArguments($Info, $Arguments) {
    if ($null -ne $Info.PSObject.Properties['ArgumentList']) {
        foreach ($argument in $Arguments) { [void]$Info.ArgumentList.Add([string]$argument) }
    } else {
        $quoted = @($Arguments | ForEach-Object { ConvertTo-MotdWindowsArgument ([string]$_) })
        $Info.Arguments = Join-MotdText $quoted ' '
    }
}

function Stop-MotdProcess($Process) {
    # Old .NET stops the direct child. Current .NET may stop its descendants.
    # This is not a sandbox and does not promise containment on old Windows.
    if ($MotdMajor -ge 7) { $Process.Kill($true) }
    else { $Process.Kill() }
    [void]$Process.WaitForExit(250)
}

function Invoke-MotdHooks([string] $Phase) {
    if ($Demo -or $NoHooks) { return }
    $number = 0
    foreach ($hook in @($MotdConfig['hooks'][$Phase])) {
        $number++
        if ($hook.argv[0] -ceq 'motd:print') {
            # A built-in literal line action shares the phase/demo gate above.
            # It invokes no process, parser, expression evaluator or shell.
            for ($i = 1; $i -lt $hook.argv.Count; $i++) { Write-Output (ConvertTo-MotdText $hook.argv[$i]) }
            continue
        }
        $state = @{ Process = (New-Object Diagnostics.Process); Status = 127 }
        $read = Read-MotdObservation {
            $info = New-Object Diagnostics.ProcessStartInfo
            $info.FileName = [string]$hook.argv[0]
            $info.UseShellExecute = $false
            $arguments = New-MotdList
            for ($i = 1; $i -lt $hook.argv.Count; $i++) { [void]$arguments.Add([string]$hook.argv[$i]) }
            Set-MotdArguments $info $arguments
            $state.Process.StartInfo = $info
            [void]$state.Process.Start()
            $milliseconds = [int][Math]::Ceiling(1000.0 * [double]$hook.timeout_seconds)
            if ($state.Process.WaitForExit($milliseconds)) { $state.Status = $state.Process.ExitCode }
            else { $state.Status = 124; Stop-MotdProcess $state.Process }
        }
        $state.Process.Dispose()
        if (-not $read.Ok) { [Console]::Error.WriteLine('MOTD hook could not complete: ' + $read.Error) }
        if ($state.Status -ne 0) {
            $message = 'MOTD ' + $Phase + ' hook ' + $number + ' failed (' + $state.Status + ').'
            [Console]::Error.WriteLine($message)
            if ($hook.on_failure -eq 'stop') { throw $message }
        }
    }
}

function Read-MotdExternal([string] $File, $Arguments) {
    # Only fixed local observation commands call this helper. No shell is used.
    # Bounded output avoids redirect-buffer deadlock: a noisy command times out,
    # its partial output is discarded, and the observation becomes unavailable.
    $state = @{ Process = (New-Object Diagnostics.Process); Text = ''; Status = 127 }
    $read = Read-MotdObservation {
        $info = New-Object Diagnostics.ProcessStartInfo
        $info.FileName = $File; $info.UseShellExecute = $false
        $info.RedirectStandardOutput = $true; $info.RedirectStandardError = $true
        Set-MotdArguments $info $Arguments
        $state.Process.StartInfo = $info
        [void]$state.Process.Start()
        if ($state.Process.WaitForExit(1000)) {
            $state.Status = $state.Process.ExitCode
            $state.Text = $state.Process.StandardOutput.ReadToEnd()
        } else { $state.Status = 124; Stop-MotdProcess $state.Process }
    }
    $state.Process.Dispose()
    return @{ Ok = ($read.Ok -and $state.Status -eq 0); Text = $state.Text; Error = $read.Error; Status = $state.Status }
}

function Read-MotdClass([string] $Class) {
    if ($MotdQueryCache.ContainsKey($Class)) { return $MotdQueryCache[$Class] }
    $read = @{ Ok = $false; Value = @(); Error = 'No local CIM/WMI provider' }
    if ($MotdWindows) {
        if (Test-MotdCommand 'Get-CimInstance') {
            $read = Read-MotdObservation { Get-CimInstance -ClassName $Class -OperationTimeoutSec 1 -ErrorAction Stop }
        }
        if (-not $read.Ok -and (Test-MotdCommand 'Get-WmiObject')) {
            $read = Read-MotdObservation { Get-WmiObject -Class $Class -ErrorAction Stop }
        }
    }
    # WMI and module startup are not covered by a hard total renderer deadline.
    $MotdQueryCache[$Class] = $read
    return $read
}

function Read-MotdIdentity {
    if ($Demo) { return @{ Name = 'demo-host'; Uptime = '4d 06h' } }
    $seconds = -1.0
    if (-not $MotdWindows -and [IO.File]::Exists('/proc/uptime')) {
        $read = Read-MotdObservation { [IO.File]::ReadAllText('/proc/uptime') }
        if ($read.Ok -and $read.Value.Count -gt 0 -and $read.Value[0] -match '^\s*(\d+)') { $seconds = [double]$matches[1] }
    } elseif ($MotdWindows) {
        $read = Read-MotdClass 'Win32_OperatingSystem'
        if ($read.Ok -and $read.Value.Count -gt 0) {
            $boot = $read.Value[0].LastBootUpTime
            $elapsed = Read-MotdObservation {
                if ($boot -is [DateTime]) { $started = $boot }
                elseif ($boot) { $started = [Management.ManagementDateTimeConverter]::ToDateTime([string]$boot) }
                else { throw 'Boot time unavailable.' }
                ([DateTime]::Now - $started).TotalSeconds
            }
            if ($elapsed.Ok -and $elapsed.Value.Count -gt 0) { $seconds = [double]$elapsed.Value[0] }
        }
    }
    if ($seconds -lt 0) {
        # TickCount64 is a capability fallback, not a PS1/.NET2 requirement.
        $read = Read-MotdObservation { [Environment]::TickCount64 }
        if ($read.Ok -and $read.Value.Count -gt 0 -and $null -ne $read.Value[0] -and $read.Value[0] -ge 0) { $seconds = [double]$read.Value[0] / 1000.0 }
    }
    $uptime = 'unavailable'
    if ($seconds -ge 0) {
        $days = [int][Math]::Floor($seconds / 86400.0)
        $hours = [int][Math]::Floor(($seconds % 86400.0) / 3600.0)
        $minutes = [int][Math]::Floor(($seconds % 3600.0) / 60.0)
        if ($days -gt 0) { $uptime = [string]$days + 'd ' + [string]$hours + 'h' }
        elseif ($hours -gt 0) { $uptime = [string]$hours + 'h ' + [string]$minutes + 'm' }
        else { $uptime = [string]$minutes + 'm' }
    }
    return @{ Name = (ConvertTo-MotdText ([Environment]::MachineName)); Uptime = $uptime }
}

function Add-MotdSystem {
    if ($Demo) {
        Add-MotdLine 'SYSTEM  demo-host | 8 logical CPUs' 'accent'
        Add-MotdLine 'Windows / Unix | User operator'
        Add-MotdLine 'Up 4d 06h | PowerShell capability demo'
        return
    }
    Add-MotdLine ('SYSTEM  ' + [Environment]::MachineName + ' | ' + [Environment]::ProcessorCount + ' CPUs') 'accent'
    Add-MotdLine ([Environment]::OSVersion.VersionString)
    $session = 'non-SSH/unknown transport'
    if ($env:SSH_CONNECTION -or $env:SSH_TTY) { $session = 'SSH markers present' }
    Add-MotdLine ('User ' + [Environment]::UserName + ' | ' + $session)
    Add-MotdLine ('PowerShell ' + $MotdEngine)
}

function Add-MotdResources {
    $total = -1.0; $used = -1.0; $swapTotal = -1.0; $swapUsed = -1.0
    $diskTotal = -1.0; $diskUsed = -1.0; $rootPath = '/'
    if ($Demo) {
        $total = 17179869184.0; $used = 6442450944.0
        $diskTotal = 549755813888.0; $diskUsed = 128849018880.0
        $swapTotal = 8589934592.0; $swapUsed = 536870912.0
    } elseif ($MotdWindows) {
        $read = Read-MotdClass 'Win32_OperatingSystem'
        if ($read.Ok -and $read.Value.Count -gt 0) {
            $osInfo = $read.Value[0]
            if ($null -ne $osInfo.TotalVisibleMemorySize -and [double]$osInfo.TotalVisibleMemorySize -gt 0) {
                $total = 1024.0 * [double]$osInfo.TotalVisibleMemorySize
                if ($null -ne $osInfo.FreePhysicalMemory -and [double]$osInfo.FreePhysicalMemory -ge 0 -and 1024.0 * [double]$osInfo.FreePhysicalMemory -le $total) {
                    $used = $total - 1024.0 * [double]$osInfo.FreePhysicalMemory
                }
            }
        }
        if ($MotdConfig['display']['show_swap']) {
            $read = Read-MotdClass 'Win32_PageFileUsage'
            if ($read.Ok -and $read.Value.Count -gt 0) {
                $swapTotal = 0.0; $swapUsed = 0.0
                foreach ($pageFile in $read.Value) {
                    $swapTotal += 1048576.0 * [double]$pageFile.AllocatedBaseSize
                    $swapUsed += 1048576.0 * [double]$pageFile.CurrentUsage
                }
            }
        }
    } elseif ([IO.File]::Exists('/proc/meminfo')) {
        $read = Read-MotdObservation { [IO.File]::ReadAllLines('/proc/meminfo') }
        if ($read.Ok) {
            $memory = @{}
            foreach ($line in $read.Value) {
                if ($line -match '^(MemTotal|MemAvailable|MemFree|Buffers|Cached|SReclaimable|Shmem|SwapTotal|SwapFree):\s+(\d+)\s+kB') {
                    $memory[$matches[1]] = 1024.0 * [double]$matches[2]
                }
            }
            if ($memory.ContainsKey('MemTotal')) {
                $total = $memory.MemTotal
                if ($memory.ContainsKey('MemAvailable')) { $used = $total - $memory.MemAvailable }
                else { [void]$MotdNotices.Add('MemAvailable missing; physical used memory is unavailable.') }
            }
            if ($memory.ContainsKey('SwapTotal') -and $memory.ContainsKey('SwapFree')) {
                $swapTotal = $memory.SwapTotal; $swapUsed = $swapTotal - $memory.SwapFree
            }
        }
    } elseif (Test-MotdCommand 'sysctl') {
        $read = Read-MotdExternal 'sysctl' @('-n', 'hw.memsize')
        if (-not $read.Ok) { $read = Read-MotdExternal 'sysctl' @('-n', 'hw.physmem') }
        if ($read.Ok -and $read.Text.Trim() -match '^\d+$') { $total = [double]$read.Text.Trim() }
        [void]$MotdNotices.Add('BSD/macOS memory total detected; used memory needs a platform-specific source.')
    }
    if (-not $Demo) {
        if ($MotdWindows) { $rootPath = $env:SystemDrive + '\' }
        $read = Read-MotdObservation { New-Object -TypeName IO.DriveInfo -ArgumentList $rootPath }
        if ($read.Ok -and $read.Value.Count -gt 0) {
            $drive = $read.Value[0]
            $size = Read-MotdObservation { $drive.TotalSize; $drive.TotalFreeSpace }
            if ($size.Ok -and $size.Value.Count -eq 2) { $diskTotal = [double]$size.Value[0]; $diskUsed = $diskTotal - [double]$size.Value[1] }
        }
    }
    if ($MotdBarLayout -eq 'wide') {
        Add-MotdWideResource 'MEMORY' $used $total
        Add-MotdWideResource ('STORAGE ' + $rootPath) $diskUsed $diskTotal
        if ($MotdConfig['display']['show_swap']) { Add-MotdWideResource 'Swap/pagefile' $swapUsed $swapTotal $true }
    } elseif ((Get-MotdResourceWidth) -lt 60) {
        Add-MotdLine ('MEM ' + (Format-MotdShortBytes $used) + '/' + (Format-MotdShortBytes $total) + ' ' + (Format-MotdBar $used $total)) 'accent'
        Add-MotdLine ('DISK ' + (Format-MotdShortBytes $diskUsed) + '/' + (Format-MotdShortBytes $diskTotal) + ' ' + (Format-MotdBar $diskUsed $diskTotal))
    } else {
        Add-MotdLine ('MEMORY ' + (Format-MotdBytes $used) + ' / ' + (Format-MotdBytes $total) + ' ' + (Format-MotdBar $used $total)) 'accent'
        Add-MotdLine ('STORAGE ' + $rootPath + ' ' + (Format-MotdBytes $diskUsed) + ' / ' + (Format-MotdBytes $diskTotal) + ' ' + (Format-MotdBar $diskUsed $diskTotal))
    }
    if ($MotdBarLayout -ne 'wide' -and $MotdConfig['display']['show_swap']) { Add-MotdLine ('Swap/pagefile ' + (Format-MotdShortBytes $swapUsed) + '/' + (Format-MotdShortBytes $swapTotal)) }
    if ($MotdConfig['display']['show_compression']) {
        if ($Demo) { Add-MotdLine 'Compressed memory: 256 MiB (demo)' 'muted' }
        else { Add-MotdLine 'Compression amount: unavailable' 'muted' }
    }
    if ($MotdConfig['display']['show_pressure']) {
        $pressure = 'Pressure: unavailable'
        if ($Demo) { $pressure = 'Pressure: memory some avg10 0.00%' }
        elseif ([IO.File]::Exists('/proc/pressure/memory')) {
            $read = Read-MotdObservation { [IO.File]::ReadAllLines('/proc/pressure/memory') }
            if ($read.Ok -and $read.Value.Count -gt 0 -and $read.Value[0] -match 'some avg10=([0-9.]+)') { $pressure = 'Pressure: memory some avg10 ' + $matches[1] + '%' }
        }
        Add-MotdLine $pressure 'muted'
    }
}

function Add-MotdServices {
    if ($Demo) {
        Add-MotdLine 'SERVICES  16 run / 21 loaded' 'accent'
        Add-MotdLine '[RUN] sshd  [RUN] storage-worker' 'good'
        Add-MotdLine '[RUN] backup  [STOP] optional-web'
        if ($DemoAlerts) { Add-MotdLine '[FAIL] demo-required-service' 'warning' }
        return
    }
    # Normalize local provider rows once, then apply the same recipe filters and
    # required-service checks on Windows, systemd and launchd. Provider failure
    # never turns an unknown service into a known missing/stopped service.
    $records = New-MotdList
    $observed = $false
    if ($MotdWindows -and (Test-MotdCommand 'Get-Service')) {
        $read = Read-MotdObservation { Get-Service -ErrorAction Stop | Sort-Object Name }
        if ($read.Ok) {
            $observed = $true
            foreach ($service in $read.Value) {
                [void]$records.Add(@{ Name = [string]$service.Name; State = [string]$service.Status; Running = ($service.Status -eq 'Running') })
            }
        }
    } elseif (Test-MotdCommand 'systemctl') {
        $read = Read-MotdExternal 'systemctl' @('list-units', '--type=service', '--all', '--plain', '--no-legend', '--no-pager')
        if ($read.Ok) {
            $observed = $true
            foreach ($line in [regex]::Split($read.Text, '\r?\n')) {
                if ($line -match '^\s*(\S+)\s+\S+\s+(\S+)\s+(\S+)') {
                    [void]$records.Add(@{ Name = $matches[1]; State = $matches[2]; Running = ($matches[2] -eq 'active') })
                }
            }
        }
    } elseif (Test-MotdCommand 'launchctl') {
        $read = Read-MotdExternal 'launchctl' @('list')
        if ($read.Ok) {
            $observed = $true
            foreach ($line in [regex]::Split($read.Text, '\r?\n')) {
                if ($line -match '^(\d+|-)\s+(-?\d+)\s+(\S+)') {
                    $state = 'loaded'; if ($matches[1] -ne '-') { $state = 'run' }
                    [void]$records.Add(@{ Name = $matches[3]; State = $state; Running = ($matches[1] -ne '-') })
                }
            }
        }
    }
    $items = New-MotdList
    foreach ($record in $records) {
        $excluded = $false
        foreach ($pattern in @($MotdConfig['services']['exclude'])) { if ($record.Name -like $pattern) { $excluded = $true; break } }
        if ($excluded) { continue }
        if ($MotdConfig['services']['required'].Count -gt 0 -and $MotdConfig['services']['required'] -notcontains $record.Name) { continue }
        [void]$items.Add('[' + $record.State + '] ' + $record.Name)
    }
    if ($observed) {
        foreach ($required in @($MotdConfig['services']['required'])) {
            $matched = @($records | Where-Object { $_.Name -eq $required })
            if ($matched.Count -eq 0) { [void]$MotdNotices.Add('Required service not listed: ' + $required) }
            elseif (-not $matched[0].Running) { [void]$MotdNotices.Add('Required service not running: ' + $required) }
        }
    }
    if ($items.Count -gt 0) {
        Add-MotdLine ('SERVICES  ' + $items.Count + ' matched') 'accent'
        foreach ($line in @($items | Select-Object -First 10)) { Add-MotdLine $line }
        if ($items.Count -gt 10) { Add-MotdLine ('Showing 10 of ' + $items.Count + '; not a health verdict') 'muted' }
    } else { Add-MotdLine 'SERVICES unavailable/no matched records' 'warning' }
}

function Read-MotdProcesses {
    if ($null -ne $MotdProcesses) { return }
    $script:MotdProcesses = New-MotdList
    if ($Demo) {
        foreach ($row in @(
            @{ Pid = 812; Name = 'storage-worker'; Cpu = 152.4; Memory = 805306368.0; Io = 57982058496.0 },
            @{ Pid = 946; Name = 'disk-check'; Cpu = 18.7; Memory = 134217728.0; Io = 85899345920.0 },
            @{ Pid = 1120; Name = 'database'; Cpu = 38.6; Memory = 2147483648.0; Io = 6871947673.0 },
            @{ Pid = 1304; Name = 'backup'; Cpu = 8.2; Memory = 268435456.0; Io = 25769803776.0 }
        )) { [void]$MotdProcesses.Add($row) }
        return
    }
    $read = Read-MotdObservation { [Diagnostics.Process]::GetProcesses() }
    if (-not $read.Ok) { [void]$MotdNotices.Add('Process enumeration unavailable.'); return }
    $seen = 0
    foreach ($process in $read.Value) {
        if ($seen -ge [int]$MotdConfig['collection']['process_limit']) { $process.Dispose(); continue }
        $seen++
        $row = @{ Pid = -1; Name = '?'; Cpu = -1.0; Memory = -1.0; Io = -1.0 }
        $identity = Read-MotdObservation { $process.Id; $process.ProcessName }
        if ($identity.Ok -and $identity.Value.Count -eq 2) { $row.Pid = $identity.Value[0]; $row.Name = $identity.Value[1] }
        $cpu = Read-MotdObservation { $process.TotalProcessorTime.TotalSeconds }
        if ($cpu.Ok -and $cpu.Value.Count -gt 0) { $row.Cpu = [double]$cpu.Value[0] }
        $memory = Read-MotdObservation { $process.WorkingSet64 }
        if ($memory.Ok -and $memory.Value.Count -gt 0) { $row.Memory = [double]$memory.Value[0] }
        if (-not $MotdWindows -and [IO.File]::Exists('/proc/' + $row.Pid + '/io')) {
            $ioRead = Read-MotdObservation { [IO.File]::ReadAllLines('/proc/' + $row.Pid + '/io') }
            if ($ioRead.Ok) {
                $readBytes = -1.0; $writeBytes = -1.0
                foreach ($line in $ioRead.Value) {
                    if ($line -match '^read_bytes:\s+(\d+)') { $readBytes = [double]$matches[1] }
                    if ($line -match '^write_bytes:\s+(\d+)') { $writeBytes = [double]$matches[1] }
                }
                if ($readBytes -ge 0 -and $writeBytes -ge 0) { $row.Io = $readBytes + $writeBytes }
            }
        }
        if ($row.Pid -ge 0) { [void]$MotdProcesses.Add($row) }
        $process.Dispose()
    }
    if ($seen -lt $read.Value.Count) { [void]$MotdNotices.Add('Process limit reached; rankings are partial.') }
    if ($MotdWindows -and ($MotdConfig['display']['sections'] -contains 'io')) {
        $ioRead = Read-MotdClass 'Win32_Process'
        if ($ioRead.Ok) {
            $byPid = @{}
            foreach ($row in $MotdProcesses) { $byPid[[string]$row.Pid] = $row }
            foreach ($item in $ioRead.Value) {
                $key = [string]$item.ProcessId
                if ($byPid.ContainsKey($key) -and $null -ne $item.ReadTransferCount -and $null -ne $item.WriteTransferCount) {
                    $byPid[$key].Io = [double]$item.ReadTransferCount + [double]$item.WriteTransferCount
                }
            }
        }
    }
}

function Add-MotdProcesses {
    Read-MotdProcesses
    if (-not $MotdProcesses.Count) { Add-MotdLine 'PROCESSES unavailable' 'warning'; return }
    $cpu = @($MotdProcesses | Sort-Object { $_.Cpu } -Descending)
    $memory = @($MotdProcesses | Sort-Object { $_.Memory } -Descending)
    Add-MotdLine ('PROCESSES  CPU total (s) / memory') 'accent'
    $count = [Math]::Min([int]$MotdConfig['display']['top_entries'], [Math]::Max($cpu.Count, $memory.Count))
    for ($i = 0; $i -lt $count; $i++) {
        if ($i -lt $cpu.Count) {
            $row = $cpu[$i]; $cpuText = '?'
            if ($row.Cpu -ge 0) { $cpuText = '{0:N1}' -f $row.Cpu }
            Add-MotdLine ('CPU {0,7}s {1,5} {2}' -f $cpuText, $row.Pid, $row.Name)
        }
        if ($i -lt $memory.Count) {
            $row = $memory[$i]
            Add-MotdLine ('MEM {0,8} {1,5} {2}' -f (Format-MotdShortBytes $row.Memory), $row.Pid, $row.Name)
        }
    }
    Add-MotdLine ('Working sets / cumulative CPU; ' + $MotdProcesses.Count + ' sampled') 'muted'
}

function Add-MotdIo {
    Read-MotdProcesses
    $records = @($MotdProcesses | Where-Object { $_.Io -ge 0 } | Sort-Object { $_.Io } -Descending)
    Add-MotdLine 'I/O  cumulative process R+W bytes' 'accent'
    if ($records.Count -gt 0) {
        foreach ($row in @($records | Select-Object -First ([int]$MotdConfig['display']['top_entries']))) {
            Add-MotdLine ('{0,8} {1,5} {2}' -f (Format-MotdShortBytes $row.Io), $row.Pid, $row.Name)
        }
        Add-MotdLine ($records.Count.ToString() + '/' + $MotdProcesses.Count + ' readable; totals are not rates') 'muted'
    } else { Add-MotdLine 'unavailable (OS API/access missing)' 'warning' }
}

function Add-MotdSessions {
    if ($Demo) {
        Add-MotdLine 'SESSIONS  4 registered logins' 'accent'
        Add-MotdLine 'operator  tty1   console'
        Add-MotdLine 'operator  pts/1  192.0.2.24 (SSH)'
        Add-MotdLine 'operator  pts/2  192.0.2.31 (SSH)'
        return
    }
    $file = 'who'; $arguments = @()
    if ($MotdWindows) { $file = 'quser' }
    if (Test-MotdCommand $file) {
        $read = Read-MotdExternal $file $arguments
        if ($read.Ok -and $read.Text.Trim()) {
            $lines = @([regex]::Split($read.Text.Trim(), '\r?\n'))
            Add-MotdLine 'SESSIONS  local registered records' 'accent'
            foreach ($line in @($lines | Select-Object -First 8)) { Add-MotdLine $line }
            return
        }
    }
    Add-MotdLine ('SESSIONS  ' + [Environment]::UserName + ' (current)') 'accent'
    Add-MotdLine 'Other sessions unavailable/unregistered' 'warning'
}

function Add-MotdConnections {
    if ($Demo) {
        Add-MotdLine 'CONNECTIONS  8 TCP / 3 listeners' 'accent'
        Add-MotdLine ':22 -> 192.0.2.24:51042 Established'
        Add-MotdLine ':22 -> 192.0.2.31:49720 Established'
        Add-MotdLine ':443 -> 198.51.100.8:54016 Established'
        return
    }
    $read = Read-MotdObservation {
        $properties = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
        @{ Tcp = @($properties.GetActiveTcpConnections()); Listeners = @($properties.GetActiveTcpListeners()); Udp = @($properties.GetActiveUdpListeners()) }
    }
    if ($read.Ok -and $read.Value.Count -gt 0) {
        $data = $read.Value[0]
        Add-MotdLine ('CONNECTIONS ' + $data.Tcp.Count + ' TCP / ' + $data.Listeners.Count + ' listen / ' + $data.Udp.Count + ' UDP') 'accent'
        foreach ($connection in @($data.Tcp | Select-Object -First 5)) {
            Add-MotdLine (':' + $connection.LocalEndPoint.Port + ' -> ' + $connection.RemoteEndPoint + ' ' + $connection.State)
        }
    } else { Add-MotdLine 'CONNECTIONS unavailable (OS API/access)' 'warning' }
}

function Add-MotdAttention {
    Add-MotdLine 'ATTENTION' 'accent'
    foreach ($message in @($MotdConfig['messages'])) { Add-MotdLine $message }
    if ($DemoAlerts) { Add-MotdLine 'WARN demo disk usage 91%; check storage' 'warning' }
    if ($MotdNotices.Count -gt 0) { foreach ($notice in $MotdNotices) { Add-MotdLine $notice 'warning' } }
    elseif (-not $DemoAlerts) { Add-MotdLine 'Scope: selected local observations.' 'muted' }
    if ($MotdConfig['collection']['journal']) { Add-MotdLine 'Event/journal collection unavailable.' 'warning' }
}

function Add-MotdHints {
    Add-MotdLine 'HINTS' 'accent'
    foreach ($hint in @($MotdConfig['hints'])) { Add-MotdLine ($hint.label + ': ' + $hint.command + ' - ' + $hint.note) }
}

# Presentation is a pure transformation of the collected section rows. Presets
# resolve to data once; there is no default-Classic or per-design renderer.
function Get-MotdDisplaySetting([string] $Name, $Default) {
    if ($MotdConfig['display'].ContainsKey($Name)) { return $MotdConfig['display'][$Name] }
    return $Default
}

function Initialize-MotdPresentation {
    $design = Get-MotdDisplaySetting 'design' 'classic'
    $policy = $MotdDesignPolicies[$design]
    $layout = Get-MotdDisplaySetting 'panel_layout' 'auto'
    $frame = Get-MotdDisplaySetting 'panel_frame' 'auto'
    $heading = Get-MotdDisplaySetting 'heading_style' 'auto'
    if ($layout -eq 'auto') { $layout = $policy[0] }
    if ($frame -eq 'auto') { $frame = $policy[1] }
    if ($heading -eq 'auto') { $heading = $policy[2] }
    if ($layout -eq 'columns' -and $MotdWidth -lt 80) { $layout = 'stack' }
    if ($layout -eq 'columns' -and $frame -eq 'continuous') { $frame = 'separate' }
    $visibility = Get-MotdDisplaySetting 'border_visibility' 'all'
    $outer = ($visibility -eq 'all' -or $visibility -eq 'outer')
    $rules = ($visibility -eq 'all' -or $visibility -eq 'sections')
    $script:MotdPresentation = @{ Layout = $layout; Frame = $frame; Heading = $heading
        Outer = ($frame -eq 'continuous' -and $outer); Cards = ($frame -eq 'separate' -and $outer)
        Rules = $rules; Padding = [int](Get-MotdDisplaySetting 'padding' 1); Compact = ($MotdHeight -le 25) }
}

function Get-MotdSectionCaption([string] $Id) {
    $titles = Get-MotdDisplaySetting 'section_titles' @{}
    if ($titles.ContainsKey($Id)) { return ConvertTo-MotdText $titles[$Id] }
    $index = 0; if ((Get-MotdDisplaySetting 'label_style' 'full') -eq 'short') { $index = 1 }
    return ConvertTo-MotdText $MotdSectionText[$Id][$index]
}

function Get-MotdTextCells([string] $Text) {
    if ($Text -notmatch '[^\x20-\x7e]') { return $Text.Length }
    $cells = 0; $position = 0
    while ($position -lt $Text.Length) {
        $code = [char]::ConvertToUtf32($Text, $position); $units = 1
        if ($code -gt 65535) { $units = 2 }
        $category = [Globalization.CharUnicodeInfo]::GetUnicodeCategory($Text, $position)
        $size = 1
        if ($category -eq [Globalization.UnicodeCategory]::NonSpacingMark -or $category -eq [Globalization.UnicodeCategory]::EnclosingMark -or $code -eq 0x200D) { $size = 0 }
        elseif (($code -ge 0x1100 -and $code -le 0x115F) -or ($code -ge 0x2E80 -and $code -le 0xA4CF) -or ($code -ge 0xAC00 -and $code -le 0xD7A3) -or ($code -ge 0xF900 -and $code -le 0xFAFF) -or ($code -ge 0xFF01 -and $code -le 0xFF60) -or ($code -ge 0x1F300 -and $code -le 0x1FAFF) -or ($code -ge 0x20000 -and $code -le 0x3FFFD)) { $size = 2 }
        $cells += $size; $position += $units
    }
    return $cells
}

function Format-MotdCell([string] $Text, [int] $Length) {
    if ($Length -le 0) { return '' }
    $text = ConvertTo-MotdText $Text
    $count = Get-MotdTextCells $text
    if ($count -le $Length) { return $text + (' ' * ($Length - $count)) }
    $marker = ''
    if ((Get-MotdDisplaySetting 'overflow' 'ellipsis') -eq 'ellipsis') {
        $marker = '...'; if ($Length -lt 3) { $marker = '.' * $Length }
    }
    $limit = $Length - $marker.Length
    $output = New-Object Text.StringBuilder
    $cells = 0; $position = 0
    while ($position -lt $text.Length) {
        $code = [char]::ConvertToUtf32($text, $position); $units = 1
        if ($code -gt 65535) { $units = 2 }
        $piece = $text.Substring($position, $units)
        $size = Get-MotdTextCells $piece
        if ($cells + $size -gt $limit) { break }
        [void]$output.Append($piece); $cells += $size; $position += $units
    }
    return $output.ToString() + (' ' * ($limit - $cells)) + $marker
}

function Format-MotdDesignTone([string] $Text, [string] $Tone) {
    $emphasis = Get-MotdDisplaySetting 'color_emphasis' 'balanced'
    if (-not $MotdColor -or $Tone -eq 'normal' -or ($emphasis -eq 'quiet' -and $Tone -ne 'warning')) { return $Text }
    $code = $MotdAccent
    switch ($Tone) { 'warning' { $code = '33' } 'good' { $code = '32' } 'muted' { $code = '90' } }
    if ($emphasis -eq 'vivid' -and $Tone -ne 'muted') { $code = '1;' + $code }
    return $MotdEscape + '[' + $code + 'm' + $Text + $MotdEscape + '[0m'
}

function Get-MotdBoxCharacters {
    $style = Get-MotdDisplaySetting 'border_style' 'double'
    if ($Ascii -or -not $Unicode -or $style -eq 'ascii') { return @{ H = '-'; V = '|'; TL = '+'; TR = '+'; BL = '+'; BR = '+' } }
    $values = @(0x2500,0x2502,0x250C,0x2510,0x2514,0x2518)
    switch ($style) {
        'rounded' { $values = @(0x2500,0x2502,0x256D,0x256E,0x2570,0x256F) }
        'double' { $values = @(0x2550,0x2551,0x2554,0x2557,0x255A,0x255D) }
        'heavy' { $values = @(0x2501,0x2503,0x250F,0x2513,0x2517,0x251B) }
    }
    return @{ H = [string][char]$values[0]; V = [string][char]$values[1]; TL = [string][char]$values[2]
        TR = [string][char]$values[3]; BL = [string][char]$values[4]; BR = [string][char]$values[5] }
}

function Format-MotdDesignCell([string] $Text, [int] $Width, [int] $Padding, [bool] $Framed) {
    $characters = Get-MotdBoxCharacters
    $inner = $Width - 2 * $Padding
    if ($Framed) { $inner -= 2 }
    $body = (' ' * $Padding) + (Format-MotdCell $Text $inner) + (' ' * $Padding)
    if ($Framed) { return $characters.V + $body + $characters.V }
    return $body
}

function Format-MotdHeading([string] $Text, [int] $Width, [bool] $Rule, [string] $Left = '', [string] $Right = '') {
    $characters = Get-MotdBoxCharacters
    $inside = $Width - $Left.Length - $Right.Length
    $text = (Format-MotdCell $Text ([Math]::Max(0, $inside - 2))).TrimEnd()
    if ($text -ne '') { $text = ' ' + $text + ' ' }
    $remaining = [Math]::Max(0, $inside - (Get-MotdTextCells $text))
    $before = 0
    switch (Get-MotdDisplaySetting 'heading_align' 'left') {
        'center' { $before = [int][Math]::Floor($remaining / 2) }
        'right' { $before = $remaining }
    }
    $fill = ' '; if ($Rule) { $fill = $characters.H }
    return $Left + ($fill * $before) + $text + ($fill * ($remaining - $before)) + $Right
}

function Get-MotdPresentationRows([string] $Id) {
    $source = $MotdSections[$Id].Lines
    $rows = New-MotdList
    $prefix = $Id.ToUpper(); if ($Id -eq 'io') { $prefix = 'I/O' }
    for ($i = 0; $i -lt $source.Count; $i++) {
        $row = $source[$i].Clone()
        if ($i -eq 0) { $row.Text = [regex]::Replace($row.Text, ('^' + [regex]::Escape($prefix) + '(?:\s+|$)'), '') }
        if ($row.Text -ne '') { [void]$rows.Add($row) }
    }
    if ($Id -eq 'attention') {
        $sorted = New-MotdList
        foreach ($row in $rows) { if ($row.Tone -eq 'warning') { [void]$sorted.Add($row) } }
        foreach ($row in $rows) { if ($row.Tone -ne 'warning') { [void]$sorted.Add($row) } }
        $rows = $sorted
    }
    $MotdSections[$Id]['Summary'] = ''; $MotdSections[$Id]['SummaryTone'] = 'accent'; $MotdSections[$Id]['SummaryRelocated'] = $false
    if ($rows.Count -gt 0) {
        $MotdSections[$Id]['Summary'] = $rows[0].Text
        $MotdSections[$Id]['SummaryTone'] = $rows[0].Tone
        if ((Get-MotdDisplaySetting 'separator_text' 'summary') -eq 'summary' -and $MotdPresentation.Heading -ne 'inline') {
            # Only relocate a complete summary. A clipped rule cannot replace
            # the body observation, particularly a warning on a narrow panel.
            $available = Get-MotdResourceWidth
            if ($MotdPresentation.Outer -or $MotdPresentation.Cards) { $available -= 2 }
            $candidate = (Get-MotdSectionCaption $Id) + ' | ' + $rows[0].Text
            if ($MotdPresentation.Heading -eq 'hidden') { $candidate = $rows[0].Text; $available -= 2 * $MotdPresentation.Padding }
            else { $available -= 2 }
            if ((Get-MotdTextCells $candidate) -le $available) {
                $rows.RemoveAt(0); $MotdSections[$Id]['SummaryRelocated'] = $true
            }
        }
    }
    return ,$rows
}

function Get-MotdSeparatorNote([string] $Id, $Rows) {
    switch (Get-MotdDisplaySetting 'separator_text' 'summary') {
        'custom' { $notes = Get-MotdDisplaySetting 'section_notes' @{}; if ($notes.ContainsKey($Id)) { return ConvertTo-MotdText $notes[$Id] } }
        'summary' { if ($MotdPresentation.Heading -ne 'inline') { return [string]$MotdSections[$Id]['Summary'] } }
    }
    return ''
}

function Get-MotdPanelOverhead([string] $Id, $Rows) {
    $cost = 0
    if ($MotdPresentation.Cards) { $cost += 2 }
    if ($MotdPresentation.Heading -eq 'rule' -or $MotdPresentation.Heading -eq 'plain') {
        if (-not ($MotdPresentation.Cards -and $MotdPresentation.Heading -eq 'rule')) { $cost++ }
    } elseif ((Get-MotdSeparatorNote $Id $Rows) -ne '') { $cost++ }
    return $cost
}

function Get-MotdPresentationGroups($Selected) {
    $groups = New-MotdList
    $columns = 1; if ($MotdPresentation.Layout -eq 'columns') { $columns = 2 }
    for ($i = 0; $i -lt $Selected.Count; $i += $columns) {
        $ids = New-MotdList; [void]$ids.Add($Selected[$i])
        if ($columns -eq 2 -and $i + 1 -lt $Selected.Count) { [void]$ids.Add($Selected[$i + 1]) }
        [void]$groups.Add(@{ Ids = $ids })
    }
    return ,$groups
}

function Measure-MotdPresentation($Selected, $Allocated, $Rows, [int] $Gap) {
    $groups = Get-MotdPresentationGroups $Selected
    $height = 0
    foreach ($group in $groups) {
        $band = 0
        foreach ($id in $group.Ids) { $band = [Math]::Max($band, [int]$Allocated[$id] + (Get-MotdPanelOverhead $id $Rows[$id])) }
        $height += $band
    }
    if ($groups.Count -gt 1) { $height += $Gap * ($groups.Count - 1) }
    return $height
}

function Get-MotdOmissionRows($Selected, [int] $Length) {
    $output = New-MotdList; $line = 'Hidden: '
    foreach ($id in $MotdSectionOrder) {
        if ($Selected.Contains($id)) { continue }
        # Stable IDs keep every omitted section identifiable even when a custom
        # title occupies an entire screen. Visible headings use the shared labels.
        $label = $id; if ($id -eq 'io') { $label = 'I/O' }
        $separator = ', '; if ($line -eq 'Hidden: ' -or $line -eq '  ') { $separator = '' }
        if ($line.Length + $separator.Length + $label.Length -gt $Length) {
            [void]$output.Add($line); $line = '  ' + $label
        } else { $line += $separator + $label }
    }
    if ($line -ne 'Hidden: ') { [void]$output.Add($line) }
    return ,$output
}

function Get-MotdPresentationPlan {
    $order = New-MotdList
    foreach ($id in $MotdSectionOrder) { [void]$order.Add($id) }
    $selected = New-MotdList; $priority = New-MotdList
    foreach ($id in @(Get-MotdDisplaySetting 'priority' @('attention','resources','system','services','processes','io','sessions','connections','hints'))) {
        if (-not $priority.Contains($id)) { [void]$priority.Add($id) }
    }
    foreach ($id in $order) { if (-not $priority.Contains($id)) { [void]$priority.Add($id) } }
    $density = Get-MotdDisplaySetting 'density' 'balanced'
    $detail = Get-MotdDisplaySetting 'detail' 'normal'
    $sectionDetail = Get-MotdDisplaySetting 'section_detail' @{}
    $gap = [int](Get-MotdDisplaySetting 'section_gap' 0)
    if ($density -eq 'comfortable') { $gap = [Math]::Min(2, $gap + 1) }
    if ($density -eq 'compact') { $gap = [Math]::Max(0, $gap - 1) }
    $rows = @{}; $allocated = @{}; $maximum = @{}
    foreach ($id in $order) {
        $rows[$id] = Get-MotdPresentationRows $id
        if ($rows[$id].Count -eq 0 -and (Get-MotdSeparatorNote $id $rows[$id]) -eq '') { continue }
        [void]$selected.Add($id)
        $minimum = 1
        if ($id -eq 'resources' -or $id -eq 'system' -or $id -eq 'io') { $minimum = 2 }
        if ($id -eq 'resources' -and $MotdBarLayout -eq 'wide') { $minimum = 4 }
        if ($id -eq 'processes') { $minimum = 3 }
        if ($MotdSections[$id]['SummaryRelocated']) { $minimum = [Math]::Max(0, $minimum - 1) }
        $minimum = [Math]::Min($minimum, $rows[$id].Count)
        $selectedDetail = $detail
        if ($sectionDetail.ContainsKey($id)) { $selectedDetail = $sectionDetail[$id] }
        $limit = $rows[$id].Count
        if ($selectedDetail -eq 'brief') { $limit = $minimum }
        elseif ($selectedDetail -eq 'normal') { $limit = [Math]::Max($minimum, [Math]::Min(6, $limit)) }
        $allocated[$id] = $minimum; $maximum[$id] = $limit
    }
    $capacity = $MotdHeight - 3
    if ($MotdPresentation.Compact) { $capacity++ }
    $footerWidth = $MotdWidth - 2 * $MotdPresentation.Padding
    if ($MotdPresentation.Outer) { $capacity--; $footerWidth -= 2 }
    for ($i = $priority.Count - 1; $i -ge 0; $i--) {
        $reserved = (Get-MotdOmissionRows $selected $footerWidth).Count
        if ((Measure-MotdPresentation $selected $allocated $rows $gap) + $reserved -le $capacity) { break }
        $id = $priority[$i]
        if ($selected.Contains($id)) { [void]$selected.Remove($id); $allocated[$id] = 0 }
    }
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($id in $priority) {
            if (-not $selected.Contains($id) -or $allocated[$id] -ge $maximum[$id]) { continue }
            $allocated[$id]++
            $reserved = (Get-MotdOmissionRows $selected $footerWidth).Count
            if ((Measure-MotdPresentation $selected $allocated $rows $gap) + $reserved -le $capacity) { $changed = $true }
            else { $allocated[$id]-- }
        }
    }
    return @{ Selected = $selected; Rows = $rows; Allocated = $allocated; Gap = $gap; Footer = (Get-MotdOmissionRows $selected $footerWidth) }
}

function Get-MotdPanelRows([string] $Id, $Rows, [int] $Count, [int] $Width, [int] $BandHeight) {
    $characters = Get-MotdBoxCharacters; $output = New-MotdList
    $caption = Get-MotdSectionCaption $Id
    $note = Get-MotdSeparatorNote $Id $Rows
    $heading = $caption; if ($note -ne '') { $heading += ' | ' + $note }
    $headingTone = 'accent'
    if ((Get-MotdDisplaySetting 'separator_text' 'summary') -eq 'summary' -and $MotdSections[$Id]['SummaryTone'] -eq 'warning') { $headingTone = 'warning' }
    $ruleHeading = ($MotdPresentation.Heading -eq 'rule')
    if ($MotdPresentation.Cards) {
        $top = ''; if ($ruleHeading) { $top = $heading }
        [void]$output.Add((Format-MotdDesignTone (Format-MotdHeading $top $Width $true $characters.TL $characters.TR) $headingTone))
    }
    if (($ruleHeading -and -not $MotdPresentation.Cards) -or $MotdPresentation.Heading -eq 'plain') {
        $innerWidth = $Width; if ($MotdPresentation.Cards) { $innerWidth -= 2 }
        $header = Format-MotdHeading $heading $innerWidth ($ruleHeading -and $MotdPresentation.Rules)
        if ($MotdPresentation.Cards) { $header = $characters.V + $header + $characters.V }
        [void]$output.Add((Format-MotdDesignTone $header $headingTone))
    } elseif (-not $ruleHeading -and $note -ne '') {
        [void]$output.Add((Format-MotdDesignTone (Format-MotdDesignCell $note $Width $MotdPresentation.Padding $MotdPresentation.Cards) $headingTone))
    }
    $bodyCount = $BandHeight - $output.Count
    if ($MotdPresentation.Cards) { $bodyCount-- }
    for ($i = 0; $i -lt $bodyCount; $i++) {
        $text = ''; $tone = 'normal'
        if ($i -lt $Count) {
            $row = $Rows[$i]; $text = $row.Text; $tone = $row.Tone
            if ($row.ContainsKey('BarTotal')) {
                $innerWidth = $Width - 2 * $MotdPresentation.Padding
                if ($MotdPresentation.Cards) { $innerWidth -= 2 }
                $text = Format-MotdBar $row.BarUsed $row.BarTotal $innerWidth
            }
            if ($i -eq 0 -and $MotdPresentation.Heading -eq 'inline') { $text = $caption + ': ' + $text }
        }
        [void]$output.Add((Format-MotdDesignTone (Format-MotdDesignCell $text $Width $MotdPresentation.Padding $MotdPresentation.Cards) $tone))
    }
    if ($MotdPresentation.Cards) { [void]$output.Add((Format-MotdDesignTone ($characters.BL + ($characters.H * ($Width - 2)) + $characters.BR) 'accent')) }
    return ,$output
}

function Get-MotdHeaderTitle {
    $title = [string]$MotdConfig['display']['title']
    if ($MotdPresentation.Compact) {
        $prefix = ''; if ($Demo) { $prefix = 'DEMO | ' }
        return $prefix + (Get-MotdHeaderContext) + ' | ' + $title
    }
    if ($Demo) {
        if ($MotdWidth -lt 60) { $title = 'DEMO | ' + $title }
        else { $title = 'DEMO - synthetic | ' + $title }
    }
    return $title
}
function Get-MotdHeaderContext { return 'Host ' + $MotdIdentity.Name + ' | Up ' + $MotdIdentity.Uptime }

function Write-MotdPresentation {
    $plan = Get-MotdPresentationPlan
    $output = New-MotdList; $characters = Get-MotdBoxCharacters
    $padding = $MotdPresentation.Padding
    $contentWidth = $MotdWidth; if ($MotdPresentation.Outer) { $contentWidth -= 2 }
    if ($MotdPresentation.Outer) {
        [void]$output.Add((Format-MotdDesignTone (Format-MotdHeading (Get-MotdHeaderTitle) $MotdWidth $true $characters.TL $characters.TR) 'accent'))
    } else { [void]$output.Add((Format-MotdDesignTone (Format-MotdDesignCell (Get-MotdHeaderTitle) $MotdWidth $padding $false) 'accent')) }
    if (-not $MotdPresentation.Compact) { [void]$output.Add((Format-MotdDesignTone (Format-MotdDesignCell (Get-MotdHeaderContext) $MotdWidth $padding $MotdPresentation.Outer) 'muted')) }
    $groups = Get-MotdPresentationGroups $plan.Selected; $groupNumber = 0
    foreach ($group in $groups) {
        if ($groupNumber -gt 0) {
            for ($gap = 0; $gap -lt $plan.Gap; $gap++) { [void]$output.Add((Format-MotdDesignCell '' $MotdWidth $padding $MotdPresentation.Outer)) }
        }
        $groupNumber++
        $bandHeight = 0
        foreach ($id in $group.Ids) { $bandHeight = [Math]::Max($bandHeight, [int]$plan.Allocated[$id] + (Get-MotdPanelOverhead $id $plan.Rows[$id])) }
        $leftWidth = $contentWidth; $rightWidth = 0
        if ($group.Ids.Count -eq 2) { $leftWidth = [int][Math]::Floor(($contentWidth - 2) / 2); $rightWidth = $contentWidth - 2 - $leftWidth }
        $id = $group.Ids[0]
        $left = Get-MotdPanelRows $id $plan.Rows[$id] $plan.Allocated[$id] $leftWidth $bandHeight
        $right = $null
        if ($group.Ids.Count -eq 2) { $id = $group.Ids[1]; $right = Get-MotdPanelRows $id $plan.Rows[$id] $plan.Allocated[$id] $rightWidth $bandHeight }
        for ($i = 0; $i -lt $left.Count; $i++) {
            $line = $left[$i]; if ($null -ne $right) { $line += '  ' + $right[$i] }
            if ($MotdPresentation.Outer) { $line = $characters.V + $line + $characters.V }
            [void]$output.Add($line)
        }
    }
    foreach ($footer in $plan.Footer) { [void]$output.Add((Format-MotdDesignTone (Format-MotdDesignCell $footer $MotdWidth $padding $MotdPresentation.Outer) 'muted')) }
    if ($MotdPresentation.Outer) { [void]$output.Add((Format-MotdDesignTone ($characters.BL + ($characters.H * ($MotdWidth - 2)) + $characters.BR) 'accent')) }
    if ($output.Count -gt $MotdHeight - 1) { throw 'Internal presentation plan exceeds the terminal row budget.' }
    foreach ($line in $output) { Write-Output $line }
}

Initialize-MotdPresentation

# Read only selected local observations. Ordinary layouts keep every selected
# section; compact previews explicitly omit lower-priority sections if needed.
Invoke-MotdHooks 'before'
$MotdIdentity = Read-MotdIdentity
foreach ($section in $MotdSectionOrder) {
    $MotdSections[$section] = @{ Lines = (New-MotdList) }
    $MotdCurrentSection = $section
    switch ($section) {
        'system' { Add-MotdSystem }
        'resources' { Add-MotdResources }
        'services' { Add-MotdServices }
        'processes' { Add-MotdProcesses }
        'sessions' { Add-MotdSessions }
        'connections' { Add-MotdConnections }
        'io' { Add-MotdIo }
        # Attention is filled after every selected collector, even if the user
        # places it before I/O/processes in the displayed section order.
        'attention' { }
        'hints' { Add-MotdHints }
    }
}
if ($MotdSections.ContainsKey('attention')) {
    $MotdCurrentSection = 'attention'
    Add-MotdAttention
}
Write-MotdPresentation
Invoke-MotdHooks 'after'
