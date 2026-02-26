$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
foreach ($p in $procs) {
    if ($p.CommandLine -like "*sft-accounting-runner.py*") {
        Write-Host $p.CommandLine
    }
}
