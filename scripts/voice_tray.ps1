param([Parameter(Mandatory = $true)][string]$Archive)
$mutex = [System.Threading.Mutex]::new($false, 'Local\LiDaxiaoVoiceTray')
try { $acquired = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
if (!$acquired) { $mutex.Dispose(); exit }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$icon = New-Object System.Windows.Forms.NotifyIcon
$icon.Icon = [System.Drawing.SystemIcons]::Information
$icon.Text = '李大霄语音监控'
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$status = $menu.Items.Add('查看最新状态')
$logs = $menu.Items.Add('查看日志')
$pause = $menu.Items.Add('暂停 / 恢复')
$exit = $menu.Items.Add('隐藏托盘（监控继续）')
$open = { param($path) if (Test-Path -LiteralPath $path) { Invoke-Item -LiteralPath $path } }
$status.Add_Click({ & $open (Join-Path $Archive 'latest.md') })
$logs.Add_Click({ & $open (Join-Path $Archive 'voice.log') })
$pause.Add_Click({
    $marker = Join-Path $Archive 'pause'
    if (Test-Path -LiteralPath $marker) {
        Remove-Item -LiteralPath $marker
        $icon.Text = '李大霄语音监控'
    } else {
        New-Item -ItemType File -Path $marker | Out-Null
        $icon.Text = '李大霄语音监控（已暂停）'
    }
})
$exit.Add_Click({ [System.Windows.Forms.Application]::ExitThread() })
$icon.ContextMenuStrip = $menu
$icon.Add_DoubleClick({ & $open (Join-Path $Archive 'latest.md') })
try {
    $icon.Visible = $true
    [System.Windows.Forms.Application]::Run()
} finally {
    $icon.Visible = $false
    $icon.Dispose()
    $menu.Dispose()
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
