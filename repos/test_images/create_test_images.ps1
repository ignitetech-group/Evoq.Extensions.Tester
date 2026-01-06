Add-Type -AssemblyName System.Drawing

# Create PNG test image
$bmp = New-Object System.Drawing.Bitmap(200, 200)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Blue)
$font = New-Object System.Drawing.Font("Arial", 16)
$g.DrawString("Test PNG", $font, [System.Drawing.Brushes]::White, 30, 90)
$bmp.Save("C:\DNN\Evoq.Extensions.Tester\repos\test_images\test_image.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
Write-Output "PNG created"

# Create JPG test image
$bmp2 = New-Object System.Drawing.Bitmap(200, 200)
$g2 = [System.Drawing.Graphics]::FromImage($bmp2)
$g2.Clear([System.Drawing.Color]::Green)
$g2.DrawString("Test JPG", $font, [System.Drawing.Brushes]::White, 30, 90)
$bmp2.Save("C:\DNN\Evoq.Extensions.Tester\repos\test_images\test_image.jpg", [System.Drawing.Imaging.ImageFormat]::Jpeg)
$g2.Dispose()
$bmp2.Dispose()
Write-Output "JPG created"

# Create GIF test image
$bmp3 = New-Object System.Drawing.Bitmap(200, 200)
$g3 = [System.Drawing.Graphics]::FromImage($bmp3)
$g3.Clear([System.Drawing.Color]::Red)
$g3.DrawString("Test GIF", $font, [System.Drawing.Brushes]::White, 30, 90)
$bmp3.Save("C:\DNN\Evoq.Extensions.Tester\repos\test_images\test_image.gif", [System.Drawing.Imaging.ImageFormat]::Gif)
$g3.Dispose()
$bmp3.Dispose()
Write-Output "GIF created"

# Create BMP test image
$bmp4 = New-Object System.Drawing.Bitmap(200, 200)
$g4 = [System.Drawing.Graphics]::FromImage($bmp4)
$g4.Clear([System.Drawing.Color]::Yellow)
$g4.DrawString("Test BMP", $font, [System.Drawing.Brushes]::Black, 30, 90)
$bmp4.Save("C:\DNN\Evoq.Extensions.Tester\repos\test_images\test_image.bmp", [System.Drawing.Imaging.ImageFormat]::Bmp)
$g4.Dispose()
$bmp4.Dispose()
Write-Output "BMP created"

# Create a large test image (for size testing)
$bmpLarge = New-Object System.Drawing.Bitmap(2000, 2000)
$gLarge = [System.Drawing.Graphics]::FromImage($bmpLarge)
$gLarge.Clear([System.Drawing.Color]::Purple)
$gLarge.DrawString("Large Test Image", (New-Object System.Drawing.Font("Arial", 48)), [System.Drawing.Brushes]::White, 300, 900)
$bmpLarge.Save("C:\DNN\Evoq.Extensions.Tester\repos\test_images\large_image.png", [System.Drawing.Imaging.ImageFormat]::Png)
$gLarge.Dispose()
$bmpLarge.Dispose()
Write-Output "Large PNG created"

$font.Dispose()
Write-Output "All test images created successfully"
