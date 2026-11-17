# Execute trusted, generated MOTD files on an actual PowerShell 1+ host.
# Copy this file and generated .ps1 outputs to the target; Python is not needed.
# Example (PowerShell 2):
# powershell.exe -Version 2 -NoProfile -Command "& '.\tools\test_legacy_powershell.ps1' -ArtifactsDirectory '.\build\legacy-powershell-inputs' -ExpectedMajor 2 -Output '.\build\powershell-2-evidence.xml' -IncludeLive"
# Invoke the corresponding installed engine for versions 1, 3, 4 or 5; -Version
# is not a mechanism for installing those engines on a current Windows image.
# This harness executes its input scripts. Only supply generated files you trust.
# It never installs a runtime, changes execution policy or modifies login files.
# XML output works with .NET 2 and does not depend on PS3's ConvertTo-Json.
#Requires -Version 1.0
param(
    [string] $Artifact = '',
    [string] $ArtifactsDirectory = '',
    [int] $ExpectedMajor = 0,
    [string] $Output = 'powershell-evidence.xml',
    [switch] $IncludeLive
)

$ErrorActionPreference = 'Stop'
$EvidenceDocument = New-Object Xml.XmlDocument
$EvidenceRoot = $EvidenceDocument.CreateElement('motd-powershell-evidence')
[void]$EvidenceDocument.AppendChild($EvidenceRoot)
$EvidenceRoot.SetAttribute('schema-version', '1')
$EvidenceRoot.SetAttribute('started-at-utc', [DateTime]::UtcNow.ToString('o'))
$EvidenceRoot.SetAttribute('status', 'running')
$EvidenceOutput = [IO.Path]::GetFullPath($Output)

function Save-Evidence {
    $EvidenceRoot.SetAttribute('completed-at-utc', [DateTime]::UtcNow.ToString('o'))
    $EvidenceDocument.Save($EvidenceOutput)
}

trap {
    $EvidenceRoot.SetAttribute('status', 'failed')
    $EvidenceRoot.SetAttribute('fatal-error', $_.Exception.Message)
    Save-Evidence
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}

function Get-ArtifactSha256([string] $Path) {
    $hash = [Security.Cryptography.SHA256]::Create()
    $bytes = $hash.ComputeHash([IO.File]::ReadAllBytes($Path))
    $hash.Clear()
    return [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}

function Invoke-ObservedCase([string] $Path, [int] $Columns, [int] $Rows, [bool] $Unicode, [bool] $Live) {
    $state = @{ Ok = $true; Lines = @(); Error = '' }
    trap { $state.Ok = $false; $state.Error = $_.Exception.Message; continue }
    if ($Live) { $state.Lines = @(& $Path -NoHooks -Plain -Ascii -Width $Columns -Rows $Rows | ForEach-Object { [string]$_ }) }
    elseif ($Unicode) { $state.Lines = @(& $Path -DemoAlerts -NoHooks -Plain -Unicode -Width $Columns -Rows $Rows | ForEach-Object { [string]$_ }) }
    else { $state.Lines = @(& $Path -DemoAlerts -NoHooks -Plain -Ascii -Width $Columns -Rows $Rows | ForEach-Object { [string]$_ }) }
    return $state
}

$actualVersion = [string]$Host.Version
if ($PSVersionTable -and $PSVersionTable.PSVersion) { $actualVersion = [string]$PSVersionTable.PSVersion }
$actualMajor = [int]$actualVersion.Split('.')[0]
$EvidenceRoot.SetAttribute('expected-major', [string]$ExpectedMajor)
$EvidenceRoot.SetAttribute('actual-version', $actualVersion)
$EvidenceRoot.SetAttribute('clr-version', [string][Environment]::Version)
$EvidenceRoot.SetAttribute('os-version', [Environment]::OSVersion.VersionString)
$EvidenceRoot.SetAttribute('process-bitness', [string]([IntPtr]::Size * 8))
$EvidenceRoot.SetAttribute('automation-assembly', [Management.Automation.PSObject].Assembly.FullName)
$createMethods = @(([scriptblock]).GetMethods() | Where-Object { $_.Name -eq 'Create' -and $_.IsStatic })
$EvidenceRoot.SetAttribute('scriptblock-create-available', [string]($createMethods.Count -gt 0))
if ($ExpectedMajor -lt 1 -or $ExpectedMajor -gt 7) { throw 'Supply -ExpectedMajor 1..7 so the harness can reject a different engine.' }
if ($actualMajor -ne $ExpectedMajor) { throw ('Expected PowerShell ' + $ExpectedMajor + ', actually running ' + $actualVersion + '; no compatibility evidence collected.') }

$files = New-Object Collections.ArrayList
if ($Artifact -ne '') { [void]$files.Add([IO.Path]::GetFullPath($Artifact)) }
if ($ArtifactsDirectory -ne '') {
    foreach ($file in @(Get-ChildItem -LiteralPath $ArtifactsDirectory -Filter '*.ps1' | Sort-Object Name)) {
        if (-not $file.PSIsContainer) { [void]$files.Add($file.FullName) }
    }
}
if ($files.Count -eq 0) { throw 'Supply -Artifact or a directory containing generated .ps1 files.' }
$cases = 0; $failed = 0
foreach ($path in $files) {
    if (-not [IO.File]::Exists($path)) { throw ('Artifact missing: ' + $path) }
    $artifactNode = $EvidenceDocument.CreateElement('artifact')
    $artifactNode.SetAttribute('file', [IO.Path]::GetFileName($path))
    $artifactNode.SetAttribute('sha256', (Get-ArtifactSha256 $path))
    [void]$EvidenceRoot.AppendChild($artifactNode)
    foreach ($geometry in @(@(40, 25), @(40, 50), @(80, 25), @(80, 50))) {
        foreach ($unicode in @($false, $true)) {
            $columns = [int]$geometry[0]; $rows = [int]$geometry[1]
            $case = $EvidenceDocument.CreateElement('case')
            $case.SetAttribute('columns', [string]$columns); $case.SetAttribute('rows', [string]$rows)
            $case.SetAttribute('unicode', [string]$unicode); $case.SetAttribute('kind', 'synthetic-alerts')
            $result = Invoke-ObservedCase $path $columns $rows $unicode $false
            $ok = $result.Ok -and $result.Lines.Count -gt 0 -and $result.Lines.Count -le $rows - 1
            $demo = $false
            foreach ($line in $result.Lines) {
                # The supplied fixtures use ASCII plus single-cell box/bar glyphs.
                # Unicode grapheme width on arbitrary input is a separate test.
                if ($line.Length -ne $columns -or $line.IndexOf([char]27) -ge 0) { $ok = $false }
                if ($line.Contains('DEMO')) { $demo = $true }
            }
            $ok = $ok -and $demo
            $case.SetAttribute('passed', [string]$ok); $case.SetAttribute('rendered-rows', [string]$result.Lines.Count)
            if ($result.Error -ne '') { $case.SetAttribute('error', $result.Error) }
            [void]$artifactNode.AppendChild($case)
            $cases++; if (-not $ok) { $failed++ }
        }
    }
}
if ($IncludeLive) {
    $case = $EvidenceDocument.CreateElement('case')
    $case.SetAttribute('kind', 'live-local-no-hooks')
    $result = Invoke-ObservedCase $files[0] 80 50 $false $true
    $ok = $result.Ok -and $result.Lines.Count -gt 0 -and $result.Lines.Count -le 49
    foreach ($line in $result.Lines) { if ($line.Length -ne 80 -or $line.Contains('DEMO')) { $ok = $false } }
    $case.SetAttribute('passed', [string]$ok); $case.SetAttribute('rendered-rows', [string]$result.Lines.Count)
    if ($result.Error -ne '') { $case.SetAttribute('error', $result.Error) }
    [void]$EvidenceRoot.AppendChild($case)
    $cases++; if (-not $ok) { $failed++ }
}
$EvidenceRoot.SetAttribute('cases', [string]$cases)
$EvidenceRoot.SetAttribute('failed', [string]$failed)
$EvidenceRoot.SetAttribute('status', 'passed')
if ($failed -gt 0) { $EvidenceRoot.SetAttribute('status', 'failed') }
Save-Evidence
Write-Output ('PowerShell ' + $actualVersion + ': ' + ($cases - $failed) + '/' + $cases + ' cases passed. Evidence: ' + $EvidenceOutput)
if ($failed -gt 0) { exit 1 }
exit 0
