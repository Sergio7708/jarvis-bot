$workDir = "C:\Users\Сергей\Documents\Hermes\projects\jarvis-bot"
$logFile = Join-Path $workDir "bot_error.log"
$python = "C:\Python314\python.exe"

# Kill any existing main.py process
Get-CimInstance Win32_Process -Filter "Name='python.exe' AND CommandLine LIKE '%main.py%'" | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep 1

# Start bot with stdout+stderr to log
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$psi.Arguments = "main.py"
$psi.WorkingDirectory = $workDir
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

$p = [System.Diagnostics.Process]::Start($psi)

# Wait a moment then capture output
Start-Sleep 3

if (!$p.HasExited) {
    Write-Output "BOT_RUNNING PID=$($p.Id)"
    # Dump stderr
    $err = $p.StandardError.ReadToEnd()
    if ($err) { Write-Output "STDERR: $err" }
} else {
    Write-Output "BOT_EXITED code=$($p.ExitCode)"
    $out = $p.StandardOutput.ReadToEnd()
    $err = $p.StandardError.ReadToEnd()
    if ($out) { Write-Output "STDOUT: $out" }
    if ($err) { Write-Output "STDERR: $err" }
}
