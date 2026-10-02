$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Join-Path $PSScriptRoot "..\out"
if (Test-Path $root) { Remove-Item -Recurse -Force $root }
New-Item -ItemType Directory -Force -Path $root | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot "..\app\*") -Destination $root -Recurse -Force

New-Item -ItemType Directory -Force -Path "$root\src-tauri\icons","$root\src-tauri\binaries" | Out-Null
$iconBytes = [Convert]::FromBase64String("AAABAAEAICAAAAEAIAB7AAAAFgAAAIlQTkcNChoKAAAADUlIRFIAAAAgAAAAIAgGAAAAc3p69AAAAEJJREFUeNpjUE1+/X8gMcOoAwadA2gNRh0w9ByAK/FQS92oA0YdMPgdMFoOjDpgNBeMOmDUAaPlwMhzwGjPaMQ5AABlWGVvs64lwAAAABJRU5ErkJggg==")
[IO.File]::WriteAllBytes("$root\src-tauri\icons\icon.ico", $iconBytes)

$temp = Join-Path $env:RUNNER_TEMP "llama.cpp"
if (Test-Path $temp) { Remove-Item -Recurse -Force $temp }
git clone --depth 1 https://github.com/ggml-org/llama.cpp.git $temp

$cpuBuild = Join-Path $env:RUNNER_TEMP "llama-build-cpu"
if (Test-Path $cpuBuild) { Remove-Item -Recurse -Force $cpuBuild }
cmake -S $temp -B $cpuBuild -DGGML_NATIVE=OFF -DGGML_VULKAN=OFF -DLLAMA_BUILD_SERVER=ON -DLLAMA_CURL=OFF -DGGML_BACKEND_DL=OFF -DBUILD_SHARED_LIBS=OFF -DGGML_STATIC=ON -DGGML_OPENMP=OFF
cmake --build $cpuBuild --config Release --target llama-server -j 2
Copy-Item "$cpuBuild\bin\Release\llama-server.exe" "$root\src-tauri\binaries\llama-server-cpu-x86_64-pc-windows-msvc.exe" -Force

$vulkanBuild = Join-Path $env:RUNNER_TEMP "llama-build-vulkan"
if (Test-Path $vulkanBuild) { Remove-Item -Recurse -Force $vulkanBuild }
cmake -S $temp -B $vulkanBuild -DGGML_NATIVE=OFF -DGGML_VULKAN=ON -DLLAMA_BUILD_SERVER=ON -DLLAMA_CURL=OFF -DGGML_BACKEND_DL=OFF -DBUILD_SHARED_LIBS=OFF -DGGML_STATIC=ON -DGGML_OPENMP=OFF
cmake --build $vulkanBuild --config Release --target llama-server -j 2
Copy-Item "$vulkanBuild\bin\Release\llama-server.exe" "$root\src-tauri\binaries\llama-server-vulkan-x86_64-pc-windows-msvc.exe" -Force

Push-Location $root
npm install --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw "npm install a échoué" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Le build frontend a échoué" }
npm run tauri:build -- --target x86_64-pc-windows-msvc
if ($LASTEXITCODE -ne 0) { throw "Le build Tauri a échoué" }
Pop-Location
Write-Host "BUILD_OK"
