param(
    [Parameter(Mandatory=$true)][string]$Tipo,
    [Parameter(Mandatory=$true)][string]$Texto,
    [string]$PR = "-"
)
$archivo = Join-Path $PSScriptRoot "..\docs\registro.md"
$fecha = Get-Date -Format "yyyy-MM-dd"
$fila = "| $fecha | $Tipo | $Texto | $PR |"
$lineas = [System.Collections.Generic.List[string]](Get-Content $archivo -Encoding UTF8)
$i = $lineas.FindIndex({ param($l) $l -like "|---*" })
$lineas.Insert($i + 1, $fila)
[System.IO.File]::WriteAllLines($archivo, $lineas, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Anotado: $fila"