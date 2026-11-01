param([switch]$SmokeTest)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class TowerNative { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int command); [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string c, string t); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }'
if(-not $SmokeTest){
    $existing = [TowerNative]::FindWindow($null, 'Башня агентов — Codex')
    if($existing -ne [IntPtr]::Zero){[void][TowerNative]::ShowWindow($existing,9);[void][TowerNative]::SetForegroundWindow($existing);return}
}
$base = $PSScriptRoot
$python = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$runtime = Join-Path $base 'runtime'
[void][IO.Directory]::CreateDirectory($runtime)
$script:projects = @()
$script:projectId = $null
$script:page = 0
$script:selectedId = $null
$script:snapshotStamp = ''
$script:animations = @()
$script:animationTick = 0
$script:collapsed = $false
$script:refreshing = $false
$script:brushes = @{}
function Brush([string]$color) {
    if (-not $script:brushes.ContainsKey($color)) {
        $b = [Windows.Media.BrushConverter]::new().ConvertFromString($color)
        $b.Freeze(); $script:brushes[$color] = $b
    }
    return $script:brushes[$color]
}
function Button([string]$text) {
    $b = [Windows.Controls.Button]::new()
    $b.Content = $text; $b.Foreground = Brush '#D8D5C6'; $b.Background = Brush '#24333B'
    $b.BorderBrush = Brush '#43555E'; $b.Padding = '9,5'; $b.Margin = '3'; $b.Cursor = 'Hand'
    return $b
}
function Label([string]$text, [string]$color = '#D8D5C6', [int]$size = 12) {
    $t = [Windows.Controls.TextBlock]::new(); $t.Text = $text
    $t.Foreground = Brush $color; $t.FontSize = $size; $t.Margin = '3'
    $t.TextWrapping = 'Wrap'; return $t
}
function PixelImage([string]$name) {
    $bitmap = [Windows.Media.Imaging.BitmapImage]::new()
    $bitmap.BeginInit(); $bitmap.CacheOption = 'OnLoad'
    $bitmap.UriSource = [Uri](Join-Path $base ('assets/' + $name + '.png'))
    $bitmap.EndInit(); $bitmap.Freeze()
    $image = [Windows.Controls.Image]::new(); $image.Source = $bitmap
    [Windows.Media.RenderOptions]::SetBitmapScalingMode($image, 'NearestNeighbor')
    return $image
}
function StatusColor([string]$status) {
    switch ($status) { active { '#88B4C8' } idle { '#D6B67D' } stopped { '#C59082' } error { '#E37D68' } stale { '#C39E67' } unknown { '#9AA7A9' } default { '#BBC1B4' } }
}
function StatusBadge([string]$status, [string]$tooltip) {
    # Pixel glyphs remain legible without fonts or colour alone.
    $patterns = @{
        active = @('001111100','001111110','001111100','000110000','001100000','011000000','110000000','100000000','000000000')
        idle = @('111111111','010000010','001000100','000101000','000010000','000101000','001010100','011111110','111111111')
        stopped = @('000000000','011111110','011111110','011111110','011111110','011111110','011111110','011111110','000000000')
        error = @('000111000','000111000','000111000','000111000','000111000','000000000','000111000','000111000','000000000')
        unknown = @('001111100','011000110','000000110','000001100','000111000','000110000','000000000','000110000','000110000')
        stale = @('001111100','010000010','100010001','100010001','100011101','100000001','010000010','001111100','000000000')
    }
    if(-not $patterns.ContainsKey($status)){$status='unknown'}
    $badge = [Windows.Controls.Border]::new();$badge.Width=22;$badge.Height=22
    $badge.Background=Brush '#101B22';$badge.BorderBrush=Brush (StatusColor $status);$badge.BorderThickness='1';$badge.ToolTip=$tooltip
    $pixels=[Windows.Controls.Canvas]::new();$pixels.Width=18;$pixels.Height=18;$badge.Child=$pixels
    for($row=0;$row -lt 9;$row++){for($col=0;$col -lt 9;$col++){if($patterns[$status][$row][$col] -eq '1'){
        $dot=[Windows.Shapes.Rectangle]::new();$dot.Width=2;$dot.Height=2;$dot.Fill=Brush (StatusColor $status)
        [Windows.Controls.Canvas]::SetLeft($dot,$col*2);[Windows.Controls.Canvas]::SetTop($dot,$row*2);[void]$pixels.Children.Add($dot)
    }}}
    [Windows.Media.RenderOptions]::SetEdgeMode($pixels,'Aliased')
    return $badge
}
function SetTowerHeight([double]$height) {
    $window.MinHeight=0;$window.MaxHeight=[double]::PositiveInfinity
    $window.Height=$height;$window.MinHeight=$height;$window.MaxHeight=$height
}
$window = [Windows.Window]::new()
$window.Title = 'Башня агентов — Codex'
if(Test-Path (Join-Path $base 'assets/tower-icon.ico')){$window.Icon = [Windows.Media.Imaging.BitmapFrame]::Create([Uri](Join-Path $base 'assets/tower-icon.ico'))}
$window.Width = 650; $window.Height = 490; $window.MinWidth = 470; $window.MinHeight = 490; $window.MaxHeight = 490
$window.WindowStyle = 'None'; $window.ResizeMode = 'CanResizeWithGrip'; $window.Topmost = $true
$window.Background = Brush '#0C1114'; $window.Foreground = Brush '#D8D5C6'
$window.FontFamily = 'Segoe UI'; $window.WindowStartupLocation = 'Manual'
$window.Left = [Math]::Max(0,[Windows.SystemParameters]::WorkArea.Right - 680)
$window.Top = [Math]::Max(0,[Windows.SystemParameters]::WorkArea.Bottom - 520)
$frame = [Windows.Controls.Border]::new(); $frame.BorderBrush = Brush '#43555E'; $frame.BorderThickness = '1'
$window.Content = $frame
$layout = [Windows.Controls.DockPanel]::new(); $frame.Child = $layout
$titlebar = [Windows.Controls.DockPanel]::new(); $titlebar.Background = Brush '#152128'; $titlebar.LastChildFill = $true
[Windows.Controls.DockPanel]::SetDock($titlebar, 'Top'); [void]$layout.Children.Add($titlebar)
$close = Button '×'; $close.ToolTip = 'Закрыть башню'; $close.Add_Click({$window.Close()})
[Windows.Controls.DockPanel]::SetDock($close,'Right'); [void]$titlebar.Children.Add($close)
$collapse = Button '−'; $collapse.ToolTip = 'Свернуть до заголовка'
[Windows.Controls.DockPanel]::SetDock($collapse,'Right'); [void]$titlebar.Children.Add($collapse)
$pin = Button '◆'; $pin.ToolTip = 'Поверх других окон: включено'
$pin.Add_Click({$window.Topmost = -not $window.Topmost; $pin.Content = if($window.Topmost){'◆'}else{'◇'}; $pin.ToolTip = if($window.Topmost){'Поверх других окон: включено'}else{'Поверх других окон: выключено'}})
[Windows.Controls.DockPanel]::SetDock($pin,'Right'); [void]$titlebar.Children.Add($pin)
$title = Label '♜  БАШНЯ АГЕНТОВ' '#D8D5C6' 14; $title.Padding = '8,7'
$title.Add_MouseLeftButtonDown({if($_.ClickCount -eq 2){$collapse.RaiseEvent([Windows.RoutedEventArgs]::new([Windows.Controls.Button]::ClickEvent))}else{$window.DragMove()}})
[void]$titlebar.Children.Add($title)
$body = [Windows.Controls.DockPanel]::new(); $body.Margin = '8'; [void]$layout.Children.Add($body)
$footer = Label 'Подключение к локальному Codex…' '#8C9DA6' 11
$footer.Height=18;$footer.TextWrapping='NoWrap';$footer.TextTrimming='CharacterEllipsis'
[Windows.Controls.DockPanel]::SetDock($footer,'Bottom'); [void]$body.Children.Add($footer)
$details = [Windows.Controls.StackPanel]::new(); $details.Margin = '4,8,4,4';$details.Height=110
[Windows.Controls.DockPanel]::SetDock($details,'Bottom'); [void]$body.Children.Add($details)
$taskTitle = Label '' '#D8D5C6' 14; $taskTitle.Height = 40; $taskTitle.TextTrimming = 'CharacterEllipsis'
$taskStatus = Label '' '#A6BBC5' 12;$taskStatus.Height=20;$taskStatus.TextWrapping='NoWrap';$taskStatus.TextTrimming='CharacterEllipsis'
$agents = Label '' '#8C9DA6' 11; $agents.Height = 32; $agents.TextTrimming = 'CharacterEllipsis'
[void]$details.Children.Add($taskTitle); [void]$details.Children.Add($taskStatus); [void]$details.Children.Add($agents)
$floorbar = [Windows.Controls.DockPanel]::new(); $floorbar.Margin = '0,0,0,6'
[Windows.Controls.DockPanel]::SetDock($floorbar,'Top'); [void]$body.Children.Add($floorbar)
$floorLabel = Label 'Этаж' '#8C9DA6' 12; [void]$floorbar.Children.Add($floorLabel)
$floors = [Windows.Controls.ComboBox]::new(); $floors.MinWidth = 180; $floors.Margin = '5,3'; $floors.DisplayMemberPath = 'name'
[void]$floorbar.Children.Add($floors)
$legend = [Windows.Controls.StackPanel]::new();$legend.Orientation='Horizontal';$legend.Height=26;$legend.Margin='3,0,0,4'
[Windows.Controls.DockPanel]::SetDock($legend,'Top');[void]$body.Children.Add($legend)
foreach($entry in @(@('active','Работает'),@('idle','Ждёт'),@('unknown','Нет данных'))){
    [void]$legend.Children.Add((StatusBadge $entry[0] $entry[1]));$legendText=Label $entry[1] '#A8B7BE' 11;$legendText.Margin='5,2,14,0';[void]$legend.Children.Add($legendText)
}
$pager = [Windows.Controls.DockPanel]::new()
[Windows.Controls.DockPanel]::SetDock($pager,'Bottom'); [void]$body.Children.Add($pager)
$prev = Button '←'; $next = Button '→'; $pageLabel = Label '' '#8C9DA6' 11
[Windows.Controls.DockPanel]::SetDock($prev,'Left'); [Windows.Controls.DockPanel]::SetDock($next,'Right')
[void]$pager.Children.Add($prev); [void]$pager.Children.Add($next); [void]$pager.Children.Add($pageLabel)
$rooms = [Windows.Controls.Primitives.UniformGrid]::new(); $rooms.Columns = 3; $rooms.Rows = 1
[void]$body.Children.Add($rooms)
$collapse.Add_Click({
    if($script:collapsed){$body.Visibility='Visible';SetTowerHeight 490;$collapse.Content='−'}
    else{$body.Visibility='Collapsed';SetTowerHeight 75;$collapse.Content='+'}
    $script:collapsed = -not $script:collapsed
})
function ShowDetails($room) {
    $script:selectedId = $room.id; $taskTitle.Text = $room.title; $taskTitle.ToolTip = $room.title
    $activeChildren = @($room.agents | Where-Object status -eq 'active')
    $taskStatus.Text = $room.label + '  ·  субагентов: ' + @($room.agents).Count + '  ·  работают: ' + $activeChildren.Count
    $taskStatus.Foreground = Brush (StatusColor $room.status)
    $agentNames = @($room.agents | ForEach-Object {if($_.agent_nickname){$_.agent_nickname + ': ' + $_.label}})
    $agents.Text = if($agentNames.Count){$agentNames -join '  ·  '}else{'Герой комнаты — основной агент этого чата'}
    $agents.ToolTip = $agents.Text
}
function RenderRooms {
    $rooms.Children.Clear(); $script:animations = @()
    $project = $script:projects | Where-Object id -eq $script:projectId | Select-Object -First 1
    if(-not $project){return}
    $all = @($project.rooms); $totalPages = [Math]::Max(1,[Math]::Ceiling($all.Count / 3))
    $script:page = [Math]::Max(0,[Math]::Min($script:page,$totalPages-1))
    $pageLabel.Text = 'Комнаты ' + ($script:page*3+1) + '–' + [Math]::Min($all.Count,$script:page*3+3) + ' из ' + $all.Count
    if(-not $all.Count){$pageLabel.Text='На этом этаже пока нет задач';$taskTitle.Text='Пустой этаж';$taskStatus.Text='';$agents.Text=''}
    $prev.IsEnabled = $script:page -gt 0; $next.IsEnabled = $script:page -lt ($totalPages-1)
    $visible = @($all | Select-Object -Skip ($script:page*3) -First 3)
    if(-not @($visible | Where-Object id -eq $script:selectedId).Count){$script:selectedId=($visible | Select-Object -First 1).id}
    foreach($room in $visible){
        $idx = $rooms.Children.Count; $kind = @('book','forge','map')[$idx % 3]
        $button = Button ''; $button.Padding='0'; $button.Margin='3'; $button.HorizontalContentAlignment='Stretch'; $button.VerticalContentAlignment='Stretch'
        $button.ToolTip = $room.title + "`n" + $room.label
        if($room.id -eq $script:selectedId){$button.BorderBrush = Brush '#88B4C8';$button.BorderThickness='2'}
        $stack = [Windows.Controls.DockPanel]::new(); $button.Content = $stack
        $caption = [Windows.Controls.StackPanel]::new();$caption.Height=42; [Windows.Controls.DockPanel]::SetDock($caption,'Bottom');[void]$stack.Children.Add($caption)
        $name = Label $room.title '#D8D5C6' 11; $name.TextWrapping='NoWrap';$name.TextTrimming='CharacterEllipsis'
        [void]$caption.Children.Add($name); [void]$caption.Children.Add((Label $room.label (StatusColor $room.status) 11))
        $scene = [Windows.Controls.Grid]::new(); [void]$stack.Children.Add($scene)
        $background = PixelImage $kind; $background.Stretch='Fill'; [void]$scene.Children.Add($background)
        $spriteCanvas = [Windows.Controls.Canvas]::new(); $spriteCanvas.Width=193;$spriteCanvas.Height=224
        $viewbox = [Windows.Controls.Viewbox]::new();$viewbox.Stretch='Fill';$viewbox.Child=$spriteCanvas;[void]$scene.Children.Add($viewbox)
        $occupants = @($room) + @($room.agents)
        for($j=0;$j -lt [Math]::Min(4,$occupants.Count);$j++){
            $hero = PixelImage $kind; $hero.Width=32;$hero.Height=34
            $hero.Source = (PixelImage ('hero-'+$kind)).Source
            $hx = 48 + ($j%2)*65; $hy = 142 + [Math]::Floor($j/2)*47
            [Windows.Controls.Canvas]::SetLeft($hero,$hx);[Windows.Controls.Canvas]::SetTop($hero,$hy)
            if($occupants[$j].status -ne 'active'){$hero.Opacity=.6}
            [void]$spriteCanvas.Children.Add($hero)
            $who=if($occupants[$j].agent_nickname){$occupants[$j].agent_nickname}else{'Основной агент'}
            $badge=StatusBadge $occupants[$j].status ($who+' · '+$occupants[$j].label)
            [Windows.Controls.Canvas]::SetLeft($badge,$hx+5);[Windows.Controls.Canvas]::SetTop($badge,$hy-24);[void]$spriteCanvas.Children.Add($badge)
            if($occupants[$j].status -eq 'active'){$script:animations += @{image=$hero;badge=$badge; y=$hy; phase=$j}}
        }
        if($occupants.Count -gt 4){$extra=Label ('+'+($occupants.Count-4)) '#D8D5C6' 12;[Windows.Controls.Canvas]::SetLeft($extra,151);[Windows.Controls.Canvas]::SetTop($extra,185);[void]$spriteCanvas.Children.Add($extra)}
        $button.Tag=$room
        $button.Add_Click({ShowDetails $this.Tag; RenderRooms})
        [void]$rooms.Children.Add($button)
    }
    $chosen = $all | Where-Object id -eq $script:selectedId | Select-Object -First 1
    if(-not $chosen){$chosen=$visible | Select-Object -First 1}
    if($chosen){ShowDetails $chosen}
}
$floors.Add_SelectionChanged({
    if(-not $script:refreshing -and $null -ne $floors.SelectedItem){$script:projectId=$floors.SelectedItem.id;$script:page=0;$script:selectedId=$null;RenderRooms}
})
$prev.Add_Click({$script:page--;RenderRooms});$next.Add_Click({$script:page++;RenderRooms})
function UpdateSnapshot {
    $path=Join-Path $runtime 'snapshot.json'
    if(-not (Test-Path -LiteralPath $path)){return}
    try {
        $raw=[IO.File]::ReadAllText($path,[Text.Encoding]::UTF8)
        $data=ConvertFrom-Json -InputObject $raw
        if($data.error){$footer.Text='Ошибка подключения: '+$data.error;$script:animations=@();return}
        $age=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-$data.updatedAt
        if($age -gt 12){$footer.Text='Источник не обновлялся: '+[Math]::Floor($age)+' с';$script:animations=@();return}
        $footer.Text='Локальный Codex · только чтение · обновление каждые 3 с'
        if($raw -eq $script:snapshotStamp){return}
        $script:snapshotStamp=$raw;$script:projects=@($data.projects)
        $script:refreshing=$true
        try {
            $floors.ItemsSource=$script:projects
            $chosen=$script:projects | Where-Object id -eq $script:projectId | Select-Object -First 1
            if(-not $chosen){$chosen=$script:projects | Select-Object -First 1;$script:page=0}
            if($chosen){$script:projectId=$chosen.id;$floors.SelectedItem=$chosen}
        } finally {$script:refreshing=$false}
        RenderRooms
    } catch {$footer.Text='Не удалось прочитать обновление: '+$_.Exception.Message}
}
$start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$python
$start.Arguments='"'+(Join-Path $base 'collector.py')+'" --watch'
$start.UseShellExecute=$false;$start.CreateNoWindow=$true
$collector=[Diagnostics.Process]::Start($start)
$timer=[Windows.Threading.DispatcherTimer]::new();$timer.Interval=[TimeSpan]::FromSeconds(1)
$timer.Add_Tick({UpdateSnapshot});$timer.Start()
$animation=[Windows.Threading.DispatcherTimer]::new();$animation.Interval=[TimeSpan]::FromMilliseconds(450)
$animation.Add_Tick({$script:animationTick++;foreach($a in $script:animations){[Windows.Controls.Canvas]::SetTop($a.image,$a.y-(($script:animationTick+$a.phase)%2)*2);$a.badge.Opacity=if(($script:animationTick+$a.phase)%2){.65}else{1}}});$animation.Start()
$window.Add_Closed({$timer.Stop();$animation.Stop()})
$window.Add_ContentRendered({
    # A hidden PowerShell launcher can pass SW_HIDE to the first native window.
    # Explicitly show our WPF window after WPF has created it.
    $nativeHandle = [Windows.Interop.WindowInteropHelper]::new($window).Handle
    [void][TowerNative]::ShowWindow($nativeHandle,5)
    UpdateSnapshot
    if($SmokeTest){
        $check=[Windows.Threading.DispatcherTimer]::new();$check.Interval=[TimeSpan]::FromSeconds(4)
        $check.Add_Tick({
            try {
                UpdateSnapshot
                if($floors.Items.Count -lt 1 -or $rooms.Children.Count -lt 1){throw 'No real project rooms rendered'}
                if($floors.Items.Count -gt 1){$floors.SelectedIndex=1;RenderRooms}
                if($next.IsEnabled){$script:page++;RenderRooms}
                $window.UpdateLayout()
                $fixedRoomHeight=$rooms.ActualHeight
                $fixedDetailsHeight=$details.ActualHeight
                foreach($roomButton in @($rooms.Children)){
                    ShowDetails $roomButton.Tag;$window.UpdateLayout()
                    if([Math]::Abs($rooms.ActualHeight-$fixedRoomHeight) -gt .1 -or [Math]::Abs($details.ActualHeight-$fixedDetailsHeight) -gt .1){throw 'Room height changed after task selection'}
                }
                foreach($state in @('active','idle','stopped','error','unknown','stale')){
                    $testBadge=StatusBadge $state $state
                    if($testBadge.Child.Children.Count -lt 1){throw ('Missing status icon: '+$state)}
                }
                $window.Height=650;$window.UpdateLayout()
                if($window.ActualHeight -ne 490){throw 'Expanded height is not locked'}
                SetTowerHeight 75
                if($window.Height -ne 75){throw 'Collapse height failed'}
                SetTowerHeight 490;$window.UpdateLayout()
                $bmp=[Windows.Media.Imaging.RenderTargetBitmap]::new([int]$window.ActualWidth,[int]$window.ActualHeight,96,96,[Windows.Media.PixelFormats]::Pbgra32)
                $bmp.Render($window);$encoder=[Windows.Media.Imaging.PngBitmapEncoder]::new();$encoder.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($bmp))
                $stream=[IO.File]::Create((Join-Path $runtime 'overlay-smoke.png'));try{$encoder.Save($stream)}finally{$stream.Dispose()}
                [IO.File]::WriteAllText((Join-Path $runtime 'smoke-result.txt'),('PASS: floors='+$floors.Items.Count+' rooms='+$rooms.Children.Count+' fixed-height=490 stable-selection-layout six-status-icons collapse=75'))
            } catch {[IO.File]::WriteAllText((Join-Path $runtime 'smoke-result.txt'),('FAIL: '+$_.Exception.Message))}
            $this.Stop();$window.Close()
        });$check.Start()
    }
})
try {[void]$window.ShowDialog()} finally {if(-not $collector.HasExited){$collector.Kill()};$collector.Dispose()}
