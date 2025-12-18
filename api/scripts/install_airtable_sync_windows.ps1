<#
Instala 2 tareas programadas (Windows Task Scheduler) para correr el sync:
  - Diario a las 11:59 AM
  - Diario a las 11:59 PM

Requisitos:
  - Ejecutar PowerShell como Administrador (recomendado).
  - Variables de entorno persistentes ya configuradas (AIRTABLE_*, DATABASE_URL).

Notas de diseño:
  - Se usa schtasks.exe para compatibilidad amplia.
  - La tarea se ejecuta en el directorio back/api para evitar problemas de imports.
#>

param(
  [Parameter(Mandatory = $false)]
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,

  [Parameter(Mandatory = $false)]
  [string]$PythonExe = (Get-Command python).Source
)

$BackApiDir = Join-Path $RepoRoot "back\api"
$ScriptPath = Join-Path $BackApiDir "scripts\airtable_to_postgres_sync.py"

if (-not (Test-Path $ScriptPath)) {
  throw "No se encontró el script: $ScriptPath"
}

$TaskBaseName = "AirtableToPostgresSync"

function New-DailyTask([string]$NameSuffix, [string]$Time24h) {
  $TaskName = "$TaskBaseName-$NameSuffix"
  $Cmd = "`"$PythonExe`" `"$ScriptPath`""

  # /TR no soporta fácilmente 'Start in', por eso envolvemos en cmd y hacemos cd.
  $Tr = "cmd.exe /c `"cd /d `"$BackApiDir`" && $Cmd`""

  schtasks.exe /Create `
    /TN $TaskName `
    /SC DAILY `
    /ST $Time24h `
    /RL HIGHEST `
    /F `
    /TR $Tr | Out-Host
}

Write-Host "Creando tareas programadas para Airtable -> Postgres sync..."

# 11:59 AM
New-DailyTask -NameSuffix "11_59_AM" -Time24h "11:59"

# 11:59 PM (23:59)
New-DailyTask -NameSuffix "11_59_PM" -Time24h "23:59"

Write-Host "Listo. Verifica en Task Scheduler: Task Scheduler Library -> $TaskBaseName-*"


