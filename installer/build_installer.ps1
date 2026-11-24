$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDirectory = Join-Path $projectRoot "dist"
$payload = Join-Path ([System.IO.Path]::GetTempPath()) ("RodoviariaPayload-" + [guid]::NewGuid())
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("RodoviariaBuild-" + [guid]::NewGuid())
$archive = Join-Path ([System.IO.Path]::GetTempPath()) ("RenCloud-" + [guid]::NewGuid() + ".zip")
$extract = Join-Path ([System.IO.Path]::GetTempPath()) ("RenCloud-" + [guid]::NewGuid())
$pluginUrl = "https://github.com/RenCloud/scs-sdk-plugin/releases/download/V.1.12.1/release_v_1_12_1.zip"
$expectedPluginHash = "1d03dbc7a975e72203c60a7b9998021ceb8800b836bf28a131279979ad386cd4"

New-Item -ItemType Directory -Path $payload, $work -Force | Out-Null
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
try {
    $requiredFiles = @(
        "app_rodoviaria.py",
        "falar_rodoviaria.py",
        "telemetria_ets2.py",
        "campainha.wav",
        "fundo_rodoviaria.wav",
        "installer\setup_rodoviaria.py",
        "installer\create_icon.py",
        "installer\THIRD-PARTY-NOTICES.txt"
    )
    foreach ($relativePath in $requiredFiles) {
        $path = Join-Path $projectRoot $relativePath
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Arquivo necessário não encontrado: $path"
        }
    }

    Invoke-WebRequest -Uri $pluginUrl -OutFile $archive
    Expand-Archive -LiteralPath $archive -DestinationPath $extract
    $pluginMatches = @(
        Get-ChildItem -LiteralPath $extract -Recurse -File -Filter "scs-telemetry.dll" |
            Where-Object { $_.Directory.Name -eq "Win64" }
    )
    if ($pluginMatches.Count -ne 1) {
        throw "O pacote RenCloud não contém exatamente uma DLL Win64 scs-telemetry.dll."
    }
    $pluginHash = (Get-FileHash -LiteralPath $pluginMatches[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($pluginHash -ne $expectedPluginHash) {
        throw "O SHA-256 do plugin baixado não corresponde ao esperado: $pluginHash"
    }

    $commonArguments = @(
        "--clean", "--noconfirm", "--onefile", "--noconsole",
        "--workpath", $work, "--specpath", $work
    )
    $iconScript = Join-Path $projectRoot "installer\create_icon.py"
    & py -3.15 $iconScript
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao gerar o ícone do aplicativo."
    }
    $iconPath = Join-Path $projectRoot "installer\RodoviariaETS2.ico"
    $imagePath = Join-Path $projectRoot "installer\RodoviariaETS2.png"

    & py -3.15 -m PyInstaller @commonArguments `
        "--distpath" $payload "--name" "RodoviariaETS2" "--icon" $iconPath `
        "--add-data" "$iconPath;." `
        (Join-Path $projectRoot "app_rodoviaria.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao compilar o aplicativo principal."
    }

    & py -3.15 -m PyInstaller @commonArguments `
        "--distpath" $payload "--name" "RodoviariaEngine" "--icon" $iconPath `
        (Join-Path $projectRoot "falar_rodoviaria.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao compilar o motor de anúncios."
    }

    Copy-Item -LiteralPath $pluginMatches[0].FullName `
        -Destination (Join-Path $payload "scs-telemetry.dll")
    Copy-Item -LiteralPath (Join-Path $projectRoot "campainha.wav") -Destination $payload
    Copy-Item -LiteralPath (Join-Path $projectRoot "fundo_rodoviaria.wav") -Destination $payload
    Copy-Item -LiteralPath (Join-Path $projectRoot "installer\THIRD-PARTY-NOTICES.txt") `
        -Destination $payload
    Copy-Item -LiteralPath $iconPath -Destination $payload
    Copy-Item -LiteralPath $imagePath -Destination $payload

    $installerArguments = @(
        "--clean", "--noconfirm", "--onefile", "--noconsole",
        "--workpath", (Join-Path $work "setup"),
        "--specpath", $work,
        "--distpath", $outputDirectory,
        "--name", "RodoviariaETS2-Setup",
        "--icon", $iconPath
    )
    foreach ($fileName in @(
        "RodoviariaETS2.exe",
        "RodoviariaEngine.exe",
        "scs-telemetry.dll",
        "campainha.wav",
        "fundo_rodoviaria.wav",
        "THIRD-PARTY-NOTICES.txt",
        "RodoviariaETS2.ico",
        "RodoviariaETS2.png"
    )) {
        $installerArguments += @("--add-data", "$(Join-Path $payload $fileName);payload")
    }
    $installerArguments += (Join-Path $projectRoot "installer\setup_rodoviaria.py")
    & py -3.15 -m PyInstaller @installerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao empacotar RodoviariaETS2-Setup.exe."
    }

    $installerPath = Join-Path $outputDirectory "RodoviariaETS2-Setup.exe"
    $desktop = [Environment]::GetFolderPath("Desktop")
    $desktopPath = Join-Path $desktop "RodoviariaETS2-Setup.exe"
    Copy-Item -LiteralPath $installerPath -Destination $desktopPath -Force
    Write-Output "Instalador: $installerPath"
    Write-Output "Cópia na Área de Trabalho: $desktopPath"
    Write-Output "Plugin incluído e validado (SHA-256): $pluginHash"
}
finally {
    foreach ($temporaryPath in @($payload, $work, $archive, $extract)) {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Recurse -Force
        }
    }
}
