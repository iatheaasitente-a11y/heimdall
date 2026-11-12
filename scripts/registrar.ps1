param(
    [Parameter(Mandatory=$true)][string]$Tipo,
    [Parameter(Mandatory=$true)][string]$Texto,
    [string]$PR = "-"
)

function ConvertTo-MarkdownCell([string]$Valor) {
    $sinSaltos = $Valor.Replace("`r", " ").Replace("`n", " ")
    return $sinSaltos.Replace("\", "\\").Replace("|", "\|")
}

$archivo = Join-Path $PSScriptRoot "..\docs\registro.md"
$fecha = Get-Date -Format "yyyy-MM-dd"
$Tipo = ConvertTo-MarkdownCell $Tipo
$Texto = ConvertTo-MarkdownCell $Texto
$PR = ConvertTo-MarkdownCell $PR
$fila = "| $fecha | $Tipo | $Texto | $PR |"
$lineas = [System.Collections.Generic.List[string]](Get-Content $archivo -Encoding UTF8)
$indiceCabecera = $lineas.FindIndex({ param($l) $l -match "^\|\s*Fecha\s*\|" })
$indiceSeparador = $lineas.FindIndex({ param($l) $l -match "^\|\s*:?-{3,}" })
if ($indiceCabecera -lt 0 -or $indiceSeparador -le $indiceCabecera) {
    throw "No se encontró la cabecera de la tabla en docs\registro.md."
}
$lineas.Insert($indiceSeparador + 1, $fila)
[System.IO.File]::WriteAllLines($archivo, $lineas, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Anotado: $fila"