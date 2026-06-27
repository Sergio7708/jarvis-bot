
$python = "C:\Python314\python.exe"
$cwd = "C:\Users\Сергей\Documents\Hermes\projects\jarvis-bot"
$out = Join-Path $cwd "bot_out3.txt"
$err = Join-Path $cwd "bot_err3.txt"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$psi.Arguments = "main.py"
$psi.WorkingDirectory = $cwd
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true

$p = [System.Diagnostics.Process]::Start($psi)
$p.Id
