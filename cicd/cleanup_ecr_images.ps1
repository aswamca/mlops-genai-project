param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryName,

    [Parameter(Mandatory = $true)]
    [string]$Region,

    [Parameter(Mandatory = $true)]
    [string]$LocalImageReferences,

    [int]$KeepBuildImages = 3
)

$ErrorActionPreference = "Stop"

try {
    $response = & aws ecr describe-images `
        --repository-name $RepositoryName `
        --region $Region `
        --output json
    if ($LASTEXITCODE -ne 0) {
        throw "Could not list ECR images for '$RepositoryName'."
    }

    $imageDetails = @((($response -join "`n") | ConvertFrom-Json).imageDetails)
    $buildImages = @(
        $imageDetails |
            Where-Object {
                $tags = @($_.imageTags)
                $buildTags = @($tags | Where-Object { $_ -match '^\d+$' })
                $otherTags = @($tags | Where-Object { $_ -notmatch '^\d+$' -and $_ -ne "latest" })
                $buildTags.Count -gt 0 -and $otherTags.Count -eq 0
            } |
            Sort-Object -Property imagePushedAt -Descending
    )

    if ($buildImages.Count -le $KeepBuildImages) {
        Write-Host "ECR '$RepositoryName' has $($buildImages.Count) build image(s); none need pruning."
        return
    }

    $imagesToDelete = @(
        $buildImages |
            Select-Object -Skip $KeepBuildImages |
            Where-Object { @($_.imageTags) -notcontains "latest" }
    )
    Write-Host "Keeping the newest $KeepBuildImages build images in ECR '$RepositoryName'."

    for ($offset = 0; $offset -lt $imagesToDelete.Count; $offset += 100) {
        $end = [Math]::Min($offset + 99, $imagesToDelete.Count - 1)
        $batch = @($imagesToDelete[$offset..$end])
        $imageIds = @($batch | ForEach-Object { "imageDigest=$($_.imageDigest)" })
        $awsArgs = @(
            "ecr", "batch-delete-image",
            "--repository-name", $RepositoryName,
            "--region", $Region,
            "--image-ids"
        ) + $imageIds + @("--output", "json")
        $deleteResponse = & aws @awsArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Could not delete old ECR images from '$RepositoryName'."
        }

        $deleteResult = (($deleteResponse -join "`n") | ConvertFrom-Json)
        if (@($deleteResult.failures).Count -gt 0) {
            $deleteResult.failures | ForEach-Object {
                Write-Error "ECR did not delete $($_.imageId.imageDigest): $($_.failureReason)"
            }
            throw "ECR returned one or more image deletion failures for '$RepositoryName'."
        }
        Write-Host "Deleted $(@($deleteResult.imageIds).Count) old build image(s) from ECR."
    }
}
finally {
    $localRefs = @(
        $LocalImageReferences.Split(";") |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
    if ($localRefs.Count -gt 0) {
        & docker image rm @localRefs
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to remove one or more local Docker image tags: $($localRefs -join ', ')"
        }
        Write-Host "Removed pushed local Docker image tags: $($localRefs -join ', ')"
    }
}
