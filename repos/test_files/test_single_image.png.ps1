Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap(100,100)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Blue)
$bmp.Save("C:\DNN\Evoq.Extensions.Tester\repos\test_files\test_single_image.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
Write-Host "Created test_single_image.png"
