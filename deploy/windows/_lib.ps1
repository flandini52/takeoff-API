# Funzioni condivise dagli script in deploy/windows/. Non va eseguito
# direttamente: viene caricato con "dot-sourcing" (. .\_lib.ps1) dagli
# altri script di questa cartella. Compatibile PowerShell 5.1, nessun
# modulo esterno.

function Get-RepoRoot {
    # deploy/windows/<script>.ps1 -> deploy/windows -> deploy -> repo root
    return Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

function Read-EnvFile {
    # Legge il file .env alla root del repo: solo righe "CHIAVE=valore"
    # non commentate (le righe che iniziano per # sono ignorate, cosi'
    # come i blocchi alternativi commentati in .env.example/.env).
    param([Parameter(Mandatory)] [string]$Path)
    if (-not (Test-Path $Path)) {
        throw "File .env non trovato: $Path. Copia .env.example in .env e compilalo prima di continuare."
    }
    $result = @{}
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        $result[$key] = $value
    }
    return $result
}

function Assert-LocalDashboardDb {
    # Controllo di sicurezza obbligatorio prima di qualunque operazione sul
    # database: questo progetto gira sullo stesso server di altri database
    # CRITICI (SILOG su 5432, TeamPortal su 5433/5434, pgbouncer TeamPortal
    # su 5434) che non vanno MAI toccati. Si ferma se .env non punta
    # esplicitamente a localhost:5435 — la porta della sola istanza
    # Postgres 16 dedicata a questa dashboard.
    param([Parameter(Mandatory)] [hashtable]$EnvValues)
    $dbHost = $EnvValues["DB_HOST"]
    $dbPort = $EnvValues["DB_PORT"]
    if ($dbHost -ne "localhost" -or $dbPort -ne "5435") {
        throw ("DB_HOST/DB_PORT in .env non sono 'localhost'/'5435' (trovati: " + `
               "'$dbHost'/'$dbPort'). Interrotto per sicurezza: questo script tocca " + `
               "solo il Postgres 16 locale della dashboard sulla porta 5435, mai " + `
               "le porte 5432/5433/5434 usate da altri database sul server.")
    }
}

function Read-SecurePasswordAsPlainText {
    # Chiede una password a runtime (mai salvata su disco) e la restituisce
    # in chiaro solo per passarla a psql/pg_dump via PGPASSWORD.
    param([Parameter(Mandatory)] [string]$Prompt)
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Get-BackupDir {
    # Cartella di destinazione dei backup: BACKUP_DIR da .env se
    # raggiungibile, altrimenti un fallback locale sotto logs/ (mai dentro
    # al repo tracciato da Git: logs/ e' in .gitignore).
    param([Parameter(Mandatory)] [hashtable]$EnvValues, [Parameter(Mandatory)] [string]$RepoRoot)
    $configured = $EnvValues["BACKUP_DIR"]
    $parentReachable = $false
    if (-not [string]::IsNullOrWhiteSpace($configured)) {
        $parent = Split-Path -Parent $configured
        $parentReachable = [string]::IsNullOrWhiteSpace($parent) -or (Test-Path $parent -ErrorAction SilentlyContinue)
    }
    if ($parentReachable) {
        if (-not (Test-Path $configured)) { New-Item -ItemType Directory -Path $configured -Force | Out-Null }
        return $configured
    }
    $fallback = Join-Path $RepoRoot "logs\backups"
    if (-not (Test-Path $fallback)) { New-Item -ItemType Directory -Path $fallback -Force | Out-Null }
    if (-not [string]::IsNullOrWhiteSpace($configured)) {
        Write-Warning "BACKUP_DIR '$configured' non raggiungibile, uso il fallback locale: $fallback"
    }
    return $fallback
}

function Get-PostgresBinPath {
    # Percorso di un eseguibile della cartella bin di PostgreSQL 16 (unica
    # versione usata da questa dashboard sul server — non confondere con
    # l'installazione 9.4 usata da SILOG).
    param([Parameter(Mandatory)] [string]$Name)
    $path = "C:\Program Files\PostgreSQL\16\bin\$Name"
    if (-not (Test-Path $path)) {
        throw "Eseguibile non trovato: $path. Controlla l'installazione di PostgreSQL 16."
    }
    return $path
}
