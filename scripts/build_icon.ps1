# Build only the native app icon. assets/logo.png remains unchanged.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$assetDir = Join-Path $PSScriptRoot '../assets'
$source = [System.Drawing.Bitmap]::new((Join-Path $assetDir 'logo.png'))
$base = [System.Drawing.Bitmap]::new(512, 512, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($base)
$graphics.Clear([System.Drawing.Color]::Transparent)
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$clip = [System.Drawing.Drawing2D.GraphicsPath]::new()
$clip.AddEllipse(0, 0, 512, 512)
$graphics.SetClip($clip)
# Enlarge the interior mark by 6%, retaining the circular outside silhouette.
$graphics.DrawImage($source, [System.Drawing.RectangleF]::new(-15.36, -15.36, 542.72, 542.72))
$graphics.Dispose()
$clip.Dispose()
$source.Dispose()
$base.Save((Join-Path $assetDir 'app-icon.png'), [System.Drawing.Imaging.ImageFormat]::Png)
$frames = @()
foreach ($size in @(16, 20, 24, 32, 40, 48, 64, 128, 256)) {
    $image = [System.Drawing.Bitmap]::new($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($image)
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.DrawImage($base, 0, 0, $size, $size)
    $memory = [System.IO.MemoryStream]::new()
    $image.Save($memory, [System.Drawing.Imaging.ImageFormat]::Png)
    $frames += @{ Size = $size; Bytes = $memory.ToArray() }
    $graphics.Dispose(); $image.Dispose(); $memory.Dispose()
}
$base.Dispose()
$stream = [System.IO.File]::Create((Join-Path $assetDir 'app.ico'))
$writer = [System.IO.BinaryWriter]::new($stream)
$writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$frames.Count)
$offset = 6 + 16 * $frames.Count
foreach ($frame in $frames) {
    $encodedSize = if ($frame.Size -eq 256) { 0 } else { $frame.Size }
    $writer.Write([byte]$encodedSize); $writer.Write([byte]$encodedSize)
    $writer.Write([byte]0); $writer.Write([byte]0)
    $writer.Write([uint16]1); $writer.Write([uint16]32)
    $writer.Write([uint32]$frame.Bytes.Length); $writer.Write([uint32]$offset)
    $offset += $frame.Bytes.Length
}
foreach ($frame in $frames) { $writer.Write([byte[]]$frame.Bytes) }
$writer.Dispose()
Write-Output 'Native app icon built: 16/20/24/32/40/48/64/128/256 px.'
