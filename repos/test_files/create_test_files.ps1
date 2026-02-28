Add-Type -AssemblyName System.Drawing

# Create test image 2
$bmp2 = New-Object System.Drawing.Bitmap(100,100)
$g2 = [System.Drawing.Graphics]::FromImage($bmp2)
$g2.Clear([System.Drawing.Color]::Red)
$bmp2.Save("C:\DNN\Evoq.Extensions.Tester\repos\test_files\test_image2.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g2.Dispose()
$bmp2.Dispose()

# Create test image 3
$bmp3 = New-Object System.Drawing.Bitmap(100,100)
$g3 = [System.Drawing.Graphics]::FromImage($bmp3)
$g3.Clear([System.Drawing.Color]::Green)
$bmp3.Save("C:\DNN\Evoq.Extensions.Tester\repos\test_files\test_image3.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g3.Dispose()
$bmp3.Dispose()

# Create large file (10MB) - may exceed limit
$largeContent = "x" * (10 * 1024 * 1024)
[System.IO.File]::WriteAllText("C:\DNN\Evoq.Extensions.Tester\repos\test_files\test_large_file.txt", $largeContent)

# Create .exe file for unsupported type test
[System.IO.File]::WriteAllText("C:\DNN\Evoq.Extensions.Tester\repos\test_files\test_unsupported.exe", "MZ fake exe content")

Write-Host "All test files created successfully"
