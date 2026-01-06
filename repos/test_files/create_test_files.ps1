Add-Type -AssemblyName System.Drawing

# Create test image
$bmp = New-Object System.Drawing.Bitmap(100,100)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Blue)
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Yellow)
$g.FillEllipse($brush, 25, 25, 50, 50)
$bmp.Save("$PSScriptRoot\test_image.png")
$g.Dispose()
$bmp.Dispose()
Write-Host "test_image.png created"

# Create second test image
$bmp2 = New-Object System.Drawing.Bitmap(100,100)
$g2 = [System.Drawing.Graphics]::FromImage($bmp2)
$g2.Clear([System.Drawing.Color]::Green)
$brush2 = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Red)
$g2.FillRectangle($brush2, 20, 20, 60, 60)
$bmp2.Save("$PSScriptRoot\test_image2.png")
$g2.Dispose()
$bmp2.Dispose()
Write-Host "test_image2.png created"

# Create test document
Set-Content -Path "$PSScriptRoot\test_document.txt" -Value "This is a test document for Activity Stream attachment testing.`nCreated on $(Get-Date)"
Write-Host "test_document.txt created"

# Create unsupported file type
Set-Content -Path "$PSScriptRoot\test_unsupported.exe" -Value "FAKE EXE FILE"
Write-Host "test_unsupported.exe created"

# Create large file (1MB - may exceed typical upload limits)
$largeContent = "X" * 1048576
Set-Content -Path "$PSScriptRoot\large_file.txt" -Value $largeContent
Write-Host "large_file.txt created (1MB)"

Write-Host "All test files created successfully!"
