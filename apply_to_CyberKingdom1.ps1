param([string]$Root = ".")
$target = Join-Path $Root "web/index.html"
if (-not (Test-Path $target)) { throw "Execute apontando para a raiz do CyberKingdom1." }
Copy-Item $target (Join-Path $Root "web/index_technical_v0.1.html") -Force
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Copy-Item (Join-Path $here "web/index.html") $target -Force
New-Item -ItemType Directory -Path (Join-Path $Root "docs") -Force | Out-Null
Copy-Item (Join-Path $here "docs/VS001_RECREATED_FREEZE.md") (Join-Path $Root "docs/VS001_RECREATED_FREEZE.md") -Force
Write-Host "VS-001 Recreated Integrated Candidate 01 aplicada."
