param(
    [Parameter(Mandatory=$true)]
    [string]$Prompt,

    [string]$OutputPath = "",

    [ValidateSet("volcengine", "openai", "bfl")]
    [string]$Provider = "volcengine",

    [string]$Model = "",

    [string]$Size = "1024x1024",

    [string]$Quality = "high",

    [int]$Seed = -1,

    [string]$ConfigFile = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($ConfigFile -eq "") {
    $ConfigFile = Join-Path (Join-Path $scriptDir "..") "config\api-config.json"
}

if ($OutputPath -eq "") {
    $outputDir = Join-Path $scriptDir "..\output"
    if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputPath = Join-Path $outputDir "img_${timestamp}.png"
}

$outputDir = Split-Path $OutputPath -Parent
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }

function Get-ApiKey([string]$ProviderName) {
    $envVar = switch ($ProviderName) {
        "volcengine" { $env:VOLCENGINE_API_KEY }
        "openai"     { $env:OPENAI_API_KEY }
        "bfl"        { $env:BFL_API_KEY }
    }
    if ($envVar) { return $envVar }
    if (Test-Path $ConfigFile) {
        $config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        $key = switch ($ProviderName) {
            "volcengine" { $config.volcengine_api_key }
            "openai"     { $config.openai_api_key }
            "bfl"        { $config.bfl_api_key }
        }
        if ($key) { return $key }
    }
    return $null
}

function Invoke-Volcengine([string]$Prompt, [string]$Model, [string]$Size, [string]$Quality, [string]$ApiKey, [string]$OutFile) {
    if ($Model -eq "") { $Model = "doubao-seedream-5-0-260128" }

    $sizeMap = @{
        "1024x1024" = "1K"; "1536x1536" = "1.5K"; "2048x2048" = "2K"; "4096x4096" = "4K"
        "1024x576"  = "1K"; "576x1024"  = "1K";  "2048x1152" = "2K"; "1152x2048" = "2K"
        "4096x2304" = "4K"; "2304x4096" = "4K"
    }
    $volcSize = "2K"
    if ($sizeMap.ContainsKey($Size)) { $volcSize = $sizeMap[$Size] }
    if ($Size -match "^\d+K$") { $volcSize = $Size }

    $body = @{
        model                         = $Model
        prompt                        = $Prompt
        size                          = $volcSize
        response_format               = "url"
        sequential_image_generation   = "disabled"
        stream                        = $false
        watermark                     = $false
    }

    $jsonBody = $body | ConvertTo-Json -Depth 5
    $headers = @{
        "Authorization" = "Bearer $ApiKey"
        "Content-Type"  = "application/json"
    }

    $truncPrompt = if ($Prompt.Length -gt 120) { $Prompt.Substring(0, 120) + "..." } else { $Prompt }
    Write-Host "[INFO] Provider: Volcengine (Jimeng) | Model: $Model | Size: $volcSize"
    Write-Host "[INFO] Prompt: $truncPrompt"

    try {
        $response = Invoke-RestMethod -Uri "https://ark.cn-beijing.volces.com/api/v3/images/generations" -Method Post -Headers $headers -Body $jsonBody -TimeoutSec 180
    } catch {
        $statusCode = ""
        if ($_.Exception.Response) { $statusCode = $_.Exception.Response.StatusCode.value__ }
        $errorBody = ""
        if ($_.ErrorDetails) { $errorBody = $_.ErrorDetails.Message }
        Write-Host "[ERROR] Volcengine API failed (HTTP ${statusCode}): $errorBody"
        return $false
    }

    $item = $response.data[0]
    if ($item.url) {
        Write-Host "[INFO] Image ready, downloading..."
        Invoke-WebRequest -Uri $item.url -OutFile $OutFile -TimeoutSec 120
    } elseif ($item.b64_json) {
        $bytes = [Convert]::FromBase64String($item.b64_json)
        [IO.File]::WriteAllBytes($OutFile, $bytes)
    } else {
        Write-Host "[ERROR] No image data in response"
        return $false
    }
    return $true
}

function Invoke-OpenAI([string]$Prompt, [string]$Model, [string]$Size, [string]$Quality, [string]$ApiKey, [string]$OutFile) {
    if ($Model -eq "") { $Model = "gpt-image-1" }

    $body = @{
        model  = $Model
        prompt = $Prompt
        size   = $Size
        n      = 1
    }

    if ($Model -eq "gpt-image-1") {
        $body["output_format"] = "png"
    } else {
        $body["quality"] = $Quality
        $body["response_format"] = "b64_json"
    }

    $jsonBody = $body | ConvertTo-Json -Depth 5
    $headers = @{
        "Authorization" = "Bearer $ApiKey"
        "Content-Type"  = "application/json"
    }

    $truncPrompt = if ($Prompt.Length -gt 120) { $Prompt.Substring(0, 120) + "..." } else { $Prompt }
    Write-Host "[INFO] Provider: OpenAI | Model: $Model | Size: $Size"
    Write-Host "[INFO] Prompt: $truncPrompt"

    try {
        $response = Invoke-RestMethod -Uri "https://api.openai.com/v1/images/generations" -Method Post -Headers $headers -Body $jsonBody -TimeoutSec 180
    } catch {
        $statusCode = ""
        if ($_.Exception.Response) { $statusCode = $_.Exception.Response.StatusCode.value__ }
        $errorBody = ""
        if ($_.ErrorDetails) { $errorBody = $_.ErrorDetails.Message }
        Write-Host "[ERROR] OpenAI API failed (HTTP ${statusCode}): $errorBody"
        return $false
    }

    $item = $response.data[0]
    if ($item.b64_json) {
        $bytes = [Convert]::FromBase64String($item.b64_json)
        [IO.File]::WriteAllBytes($OutFile, $bytes)
    } elseif ($item.url) {
        Invoke-WebRequest -Uri $item.url -OutFile $OutFile -TimeoutSec 60
    } else {
        Write-Host "[ERROR] No image data in response"
        return $false
    }
    return $true
}

function Invoke-BFL([string]$Prompt, [string]$Model, [string]$Size, [int]$Seed, [string]$ApiKey, [string]$OutFile) {
    if ($Model -eq "") { $Model = "flux-pro-1.1" }

    $endpoints = @{
        "flux-pro"     = "https://api.bfl.ai/v1/flux-pro"
        "flux-pro-1.1" = "https://api.bfl.ai/v1/flux-pro-1.1"
        "flux-dev"     = "https://api.bfl.ai/v1/flux-dev"
        "flux-dev-1.1" = "https://api.bfl.ai/v1/flux-dev-1.1"
    }

    if (-not $endpoints.ContainsKey($Model)) {
        Write-Host "[ERROR] Unknown BFL model: $Model"
        return $false
    }
    $endpoint = $endpoints[$Model]

    $aspectMap = @{
        "1024x1024" = "1:1";  "1024x1536" = "2:3"; "1536x1024" = "3:2"
        "1024x576"  = "16:9"; "576x1024"  = "9:16"; "1440x1024" = "4:3"
        "1024x1440" = "3:4";  "768x1024"  = "3:4"; "1024x768"  = "4:3"
    }
    $aspect = "1:1"
    if ($aspectMap.ContainsKey($Size)) { $aspect = $aspectMap[$Size] }

    $body = @{ prompt = $Prompt; aspect_ratio = $aspect; output_format = "png" }
    if ($Seed -ge 0) { $body["seed"] = $Seed }

    $jsonBody = $body | ConvertTo-Json -Depth 5
    $headers = @{ "X-Key" = $ApiKey; "Content-Type" = "application/json"; "accept" = "application/json" }

    $truncPrompt = if ($Prompt.Length -gt 120) { $Prompt.Substring(0, 120) + "..." } else { $Prompt }
    Write-Host "[INFO] Provider: BFL | Model: $Model | Aspect: $aspect"
    Write-Host "[INFO] Prompt: $truncPrompt"

    try {
        $initResp = Invoke-RestMethod -Uri $endpoint -Method Post -Headers $headers -Body $jsonBody -TimeoutSec 30
    } catch {
        $statusCode = ""
        if ($_.Exception.Response) { $statusCode = $_.Exception.Response.StatusCode.value__ }
        $errorBody = ""
        if ($_.ErrorDetails) { $errorBody = $_.ErrorDetails.Message }
        Write-Host "[ERROR] BFL API failed (HTTP ${statusCode}): $errorBody"
        return $false
    }

    $taskId = $initResp.id
    if (-not $taskId) { Write-Host "[ERROR] No task ID in BFL response"; return $false }

    Write-Host "[INFO] Task ID: $taskId - polling..."
    $pollHeaders = @{ "accept" = "application/json" }
    $maxAttempts = 120
    $attempt = 0

    while ($attempt -lt $maxAttempts) {
        $attempt++
        Start-Sleep -Seconds 2
        try {
            $status = Invoke-RestMethod -Uri "https://api.bfl.ai/v1/get_result?id=$taskId" -Method Get -Headers $pollHeaders -TimeoutSec 15
        } catch { continue }

        if ($status.status -eq "Ready" -and $status.result -and $status.result.sample) {
            Write-Host "[INFO] Image ready, downloading..."
            Invoke-WebRequest -Uri $status.result.sample -OutFile $OutFile -TimeoutSec 60
            return $true
        }
        if ($status.status -match "Moderated") { Write-Host "[ERROR] Content moderated"; return $false }
        if ($status.status -eq "Error") { Write-Host "[ERROR] BFL task error"; return $false }
        if ($attempt % 10 -eq 0) { Write-Host "[INFO] Waiting... ($attempt/$maxAttempts)" }
    }
    Write-Host "[ERROR] BFL task timed out"
    return $false
}

try {
    $apiKey = Get-ApiKey $Provider

    if (-not $apiKey) {
        $keyEnvVar = switch ($Provider) {
            "volcengine" { "VOLCENGINE_API_KEY" }
            "openai"     { "OPENAI_API_KEY" }
            "bfl"        { "BFL_API_KEY" }
        }
        Write-Host "[ERROR] No API key found for provider '$Provider'."
        Write-Host ""
        Write-Host "Set it via one of these methods:"
        Write-Host ""
        Write-Host "Method 1 - Environment variable:"
        Write-Host "  `$env:$keyEnvVar = 'your-api-key'"
        Write-Host ""
        Write-Host "Method 2 - Config file at: $ConfigFile"
        $jsonKey = switch ($Provider) {
            "volcengine" { "volcengine_api_key" }
            "openai"     { "openai_api_key" }
            "bfl"        { "bfl_api_key" }
        }
        Write-Host "  { `"$jsonKey`": `"your-api-key`" }"
        Write-Host ""
        Write-Host "Get an API key:"
        Write-Host "  Volcengine (Jimeng): https://console.volcengine.com/ark"
        Write-Host "  OpenAI:              https://platform.openai.com/api-keys"
        Write-Host "  BFL:                 https://docs.bfl.ai/"
        exit 1
    }

    $success = $false
    switch ($Provider) {
        "volcengine" { $success = Invoke-Volcengine -Prompt $Prompt -Model $Model -Size $Size -Quality $Quality -ApiKey $apiKey -OutFile $OutputPath }
        "openai"     { $success = Invoke-OpenAI -Prompt $Prompt -Model $Model -Size $Size -Quality $Quality -ApiKey $apiKey -OutFile $OutputPath }
        "bfl"        { $success = Invoke-BFL -Prompt $Prompt -Model $Model -Size $Size -Seed $Seed -ApiKey $apiKey -OutFile $OutputPath }
    }

    if ($success) {
        $fileInfo = Get-Item $OutputPath
        $fileSizeKB = [math]::Round($fileInfo.Length / 1024, 1)
        Write-Host "[OK] Image saved: $OutputPath ($fileSizeKB KB)"
    } else {
        exit 1
    }
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)"
    exit 1
}
