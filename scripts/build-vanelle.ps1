$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Join-Path $PSScriptRoot "..\out"
if (Test-Path $root) { Remove-Item -Recurse -Force $root }
New-Item -ItemType Directory -Force -Path $root | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot "..\app\*") -Destination $root -Recurse -Force

New-Item -ItemType Directory -Force -Path "$root\src-tauri\icons","$root\src-tauri\binaries" | Out-Null
$iconBytes = [Convert]::FromBase64String("AAABAAEAICAAAAEAIAB7AAAAFgAAAIlQTkcNChoKAAAADUlIRFIAAAAgAAAAIAgGAAAAc3p69AAAAEJJREFUeNpjUE1+/X8gMcOoAwadA2gNRh0w9ByAK/FQS92oA0YdMPgdMFoOjDpgNBeMOmDUAaPlwMhzwGjPaMQ5AABl0WGVvs64lwAAAABJRU5ErkJggg==")
[IO.File]::WriteAllBytes("$root\src-tauri\icons\icon.ico", $iconBytes)

$temp = Join-Path $env:RUNNER_TEMP "qvac-fabric-llm"
if (Test-Path $temp) { Remove-Item -Recurse -Force $temp }
git clone --depth 1 https://github.com/tetherto/qvac-fabric-llm.cpp.git $temp
Push-Location $temp
$qvacCommit = (git rev-parse HEAD).Trim()
Write-Host "QVAC_ENGINE_COMMIT=$qvacCommit"
Pop-Location

function Build-Llama([string]$buildDir,[bool]$vulkan) {
  if (Test-Path $buildDir) { Remove-Item -Recurse -Force $buildDir }
  $args=@(
    "-S",$temp,"-B",$buildDir,
    "-DGGML_NATIVE=OFF",
    "-DLLAMA_BUILD_SERVER=ON",
    "-DLLAMA_BUILD_TOOLS=ON",
    "-DLLAMA_CURL=OFF",
    "-DGGML_BACKEND_DL=OFF",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DGGML_STATIC=ON",
    "-DGGML_OPENMP=OFF"
  )
  if ($vulkan) { $args += "-DGGML_VULKAN=ON" } else { $args += "-DGGML_VULKAN=OFF" }
  cmake @args
  cmake --build $buildDir --config Release --target llama-server llama-finetune-lora llama-export-lora llama-perplexity -j 2
}

$cpuBuild = Join-Path $env:RUNNER_TEMP "qvac-build-cpu"
Build-Llama $cpuBuild $false
$cpuBin = Join-Path $cpuBuild "bin\Release"
Copy-Item "$cpuBin\llama-server.exe" "$root\src-tauri\binaries\llama-server-cpu-x86_64-pc-windows-msvc.exe" -Force
Copy-Item "$cpuBin\llama-finetune-lora.exe" "$root\src-tauri\binaries\llama-finetune-lora-x86_64-pc-windows-msvc.exe" -Force
Copy-Item "$cpuBin\llama-export-lora.exe" "$root\src-tauri\binaries\llama-export-lora-x86_64-pc-windows-msvc.exe" -Force
Copy-Item "$cpuBin\llama-perplexity.exe" "$root\src-tauri\binaries\llama-perplexity-x86_64-pc-windows-msvc.exe" -Force

$spirvConfig = Join-Path $env:RUNNER_TEMP "spirv-config"
if (Test-Path $spirvConfig) { Remove-Item -Recurse -Force $spirvConfig }
New-Item -ItemType Directory -Force -Path $spirvConfig | Out-Null
@'
set(SPIRV-Headers_FOUND TRUE)
set(SPIRV_HEADERS_FOUND TRUE)
'@ | Set-Content (Join-Path $spirvConfig "SPIRV-HeadersConfig.cmake") -Encoding utf8

$vulkanBuild = Join-Path $env:RUNNER_TEMP "qvac-build-vulkan"
if (Test-Path $vulkanBuild) { Remove-Item -Recurse -Force $vulkanBuild }
$vulkanArgs=@(
  "-S",$temp,"-B",$vulkanBuild,
  "-DGGML_NATIVE=OFF",
  "-DGGML_VULKAN=ON",
  "-DLLAMA_BUILD_SERVER=ON",
  "-DLLAMA_BUILD_TOOLS=ON",
  "-DSPIRV-Headers_DIR=$spirvConfig",
  "-DLLAMA_CURL=OFF",
  "-DGGML_BACKEND_DL=OFF",
  "-DBUILD_SHARED_LIBS=OFF",
  "-DGGML_STATIC=ON",
  "-DGGML_OPENMP=OFF"
)
cmake @vulkanArgs
cmake --build $vulkanBuild --config Release --target llama-server llama-finetune-lora llama-export-lora llama-perplexity -j 2
$vulkanBin = Join-Path $vulkanBuild "bin\Release"
Copy-Item "$vulkanBin\llama-server.exe" "$root\src-tauri\binaries\llama-server-vulkan-x86_64-pc-windows-msvc.exe" -Force
Copy-Item "$vulkanBin\llama-finetune-lora.exe" "$root\src-tauri\binaries\llama-finetune-lora-vulkan-x86_64-pc-windows-msvc.exe" -Force
Copy-Item "$vulkanBin\llama-export-lora.exe" "$root\src-tauri\binaries\llama-export-lora-vulkan-x86_64-pc-windows-msvc.exe" -Force
Copy-Item "$vulkanBin\llama-perplexity.exe" "$root\src-tauri\binaries\llama-perplexity-vulkan-x86_64-pc-windows-msvc.exe" -Force

Push-Location $root
npm install --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw "npm install a échoué" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Le build frontend a échoué" }
npm run tauri:build -- --target x86_64-pc-windows-msvc
if ($LASTEXITCODE -ne 0) { throw "Le build Tauri a échoué" }
Pop-Location
Write-Host "BUILD_OK"
