$dir = "C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\ACCOUNTING_RAW_ANSWERS"
$files = Get-ChildItem $dir -Filter Q*.md
$range = $files | Where-Object { 
    $q = [int]($_.BaseName -replace 'Q','')
    $q -ge 918 -and $q -le 1134
}
$range | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name, LastWriteTime
