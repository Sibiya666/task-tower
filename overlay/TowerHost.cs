using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;

public sealed class TowerHost : Window
{
    const string WindowTitle = "Башня агентов — Codex";
    readonly string folder;
    readonly bool smoke;
    readonly string snapshotPath;
    readonly WebView2CompositionControl web = new WebView2CompositionControl();
    readonly DispatcherTimer timer = new DispatcherTimer();
    readonly DispatcherTimer deadline = new DispatcherTimer();
    readonly JavaScriptSerializer json = new JavaScriptSerializer();
    Process collector;
    bool ready, collapsed;
    bool floorView;
    Rect overviewBounds;
    IntPtr overviewMonitor;
    NativeRect overviewMonitorWork;
    string lastData;
    int result;
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr FindWindow(string c,string t);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h,int c);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ReleaseCapture();
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
    [StructLayout(LayoutKind.Sequential)] struct NativeRect {public int Left,Top,Right,Bottom;}
    [StructLayout(LayoutKind.Sequential)] struct MonitorInfo {public int Size;public NativeRect Monitor,Work;public uint Flags;}
    [DllImport("user32.dll")] static extern IntPtr MonitorFromWindow(IntPtr h,uint flags);
    [DllImport("user32.dll",CharSet=CharSet.Auto)] static extern bool GetMonitorInfo(IntPtr monitor,ref MonitorInfo info);

    static Point ClampPosition(Rect bounds,Rect work)
    {
        return new Point(Math.Max(work.Left,Math.Min(bounds.Left,work.Right-bounds.Width)),
                         Math.Max(work.Top,Math.Min(bounds.Top,work.Bottom-bounds.Height)));
    }
    Rect MonitorWorkArea()
    {
        var info=new MonitorInfo();info.Size=Marshal.SizeOf(typeof(MonitorInfo));
        var monitor=MonitorFromWindow(new WindowInteropHelper(this).Handle,2);
        if(!GetMonitorInfo(monitor,ref info))return SystemParameters.WorkArea;
        // PointFromScreen accounts for the window's current DPI and screen origin.
        Point a=PointFromScreen(new Point(info.Work.Left,info.Work.Top));
        Point b=PointFromScreen(new Point(info.Work.Right,info.Work.Bottom));
        return new Rect(new Point(Left+a.X,Top+a.Y),new Point(Left+b.X,Top+b.Y));
    }
    void KeepInsideMonitor()
    {
        var point=ClampPosition(new Rect(Left,Top,Width,Height),MonitorWorkArea());
        Left=point.X;Top=point.Y;
    }
    void RestoreOverviewVisibility()
    {
        if(floorView)return;
        var info=new MonitorInfo();info.Size=Marshal.SizeOf(typeof(MonitorInfo));
        bool unchanged=GetMonitorInfo(overviewMonitor,ref info)
            && info.Work.Left==overviewMonitorWork.Left && info.Work.Top==overviewMonitorWork.Top
            && info.Work.Right==overviewMonitorWork.Right && info.Work.Bottom==overviewMonitorWork.Bottom;
        if(!unchanged)KeepInsideMonitor();
    }

    public static int Run(string folder, string python, bool smoke)
    {
        IntPtr existing = FindWindow(null,WindowTitle);
        if(!smoke && existing != IntPtr.Zero){ShowWindow(existing,9);SetForegroundWindow(existing);return 0;}
        TowerHost window = new TowerHost(folder,python,smoke);
        window.ShowDialog();
        return window.result;
    }

    TowerHost(string folder,string python,bool smoke)
    {
        this.folder=folder;this.smoke=smoke;
        snapshotPath=Path.Combine(folder,"runtime/snapshot-"+Process.GetCurrentProcess().Id+".json");
        Title=WindowTitle;Width=650;MinWidth=470;MaxWidth=1000;
        Height=560;MinHeight=560;MaxHeight=560;
        WindowStyle=WindowStyle.None;AllowsTransparency=true;ResizeMode=ResizeMode.CanResize;Topmost=true;
        Background=Brushes.Transparent;
        web.DefaultBackgroundColor=System.Drawing.Color.Transparent;
        Left=Math.Max(0,SystemParameters.WorkArea.Right-680);
        Top=Math.Max(0,SystemParameters.WorkArea.Bottom-590);
        Icon=BitmapFrame.Create(new Uri(Path.Combine(folder,"assets/tower-icon.ico")));
        Content=web;
        Directory.CreateDirectory(Path.Combine(folder,"runtime"));
        collector=Process.Start(new ProcessStartInfo(python,"\""+Path.Combine(folder,"collector.py")+"\" --watch --output \""+snapshotPath+"\""){
            UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=folder});
        File.WriteAllText(Path.Combine(folder,"runtime/overlay-source.json"),json.Serialize(new {hostPid=Process.GetCurrentProcess().Id,collectorPid=collector.Id,snapshot=snapshotPath}));
        timer.Interval=TimeSpan.FromSeconds(1);timer.Tick+=(s,e)=>PushSnapshot();
        deadline.Interval=TimeSpan.FromSeconds(30);
        deadline.Tick+=(s,e)=>{deadline.Stop();if(!ready){Log(new Exception("WebView2 startup timed out"));result=1;Close();}};
        Loaded+=async (s,e)=>{deadline.Start();await Initialize();};
        ContentRendered+=(s,e)=>ShowWindow(new WindowInteropHelper(this).Handle,5);
        Closed+=(s,e)=>{
            timer.Stop();deadline.Stop();ready=false;
            try{web.Dispose();}catch{}
            if(collector!=null){try{if(!collector.HasExited){collector.Kill();collector.WaitForExit(2000);}}catch{}collector.Dispose();}
        };
    }

    async Task Initialize()
    {
        try{
            CoreWebView2Environment env=await CoreWebView2Environment.CreateAsync(null,Path.Combine(folder,"runtime/webview-profile"));
            await web.EnsureCoreWebView2Async(env);
            CoreWebView2 core=web.CoreWebView2;
            core.Settings.AreDefaultContextMenusEnabled=false;
            core.Settings.AreDevToolsEnabled=false;
            core.Settings.IsStatusBarEnabled=false;
            core.Settings.IsZoomControlEnabled=false;
            core.Settings.AreBrowserAcceleratorKeysEnabled=false;
            core.SetVirtualHostNameToFolderMapping("tower.local",Path.Combine(folder,"web"),CoreWebView2HostResourceAccessKind.DenyCors);
            core.NavigationStarting+=(s,e)=>{Uri uri;if(!Uri.TryCreate(e.Uri,UriKind.Absolute,out uri)||uri.Scheme!="https"||uri.Host!="tower.local")e.Cancel=true;};
            core.NewWindowRequested+=(s,e)=>e.Handled=true;
            core.WebMessageReceived+=(s,e)=>{
                if(!e.Source.StartsWith("https://tower.local/",StringComparison.Ordinal))return;
                try{
                    var message=json.Deserialize<System.Collections.Generic.Dictionary<string,string>>(e.WebMessageAsJson);
                    string action;if(!message.TryGetValue("action",out action))return;
                    switch(action){
                        case "ready":deadline.Stop();ready=true;lastData=null;PushSnapshot();break;
                        case "close":Close();break;
                        case "pin":Topmost=!Topmost;break;
                        case "floor-view":
                            if(!floorView){
                                overviewBounds=new Rect(Left,Top,Width,Height);
                                overviewMonitor=MonitorFromWindow(new WindowInteropHelper(this).Handle,2);
                                var savedMonitor=new MonitorInfo();savedMonitor.Size=Marshal.SizeOf(typeof(MonitorInfo));
                                if(GetMonitorInfo(overviewMonitor,ref savedMonitor))overviewMonitorWork=savedMonitor.Work;
                                var work=MonitorWorkArea();double right=Left+Width;
                                MinWidth=300;MaxWidth=500;Width=340;SetHeight(300);
                                var point=ClampPosition(new Rect(right-Width,Top,Width,Height),work);
                                Left=point.X;Top=point.Y;floorView=true;
                                Dispatcher.BeginInvoke(new Action(KeepInsideMonitor),DispatcherPriority.Loaded);
                            }
                            break;
                        case "overview-view":
                            if(floorView){
                                MaxWidth=1000;Width=Math.Max(470,overviewBounds.Width);MinWidth=470;SetHeight(overviewBounds.Height);
                                Left=overviewBounds.Left;Top=overviewBounds.Top;floorView=false;
                                Dispatcher.BeginInvoke(new Action(RestoreOverviewVisibility),DispatcherPriority.Loaded);
                            }
                            break;
                        case "collapse":collapsed=!collapsed;SetHeight(collapsed?40:560);break;
                        case "drag":ReleaseCapture();SendMessage(new WindowInteropHelper(this).Handle,0xA1,new IntPtr(2),IntPtr.Zero);break;
                    }
                }catch(Exception ex){Log(ex);}
            };
            core.NavigationCompleted+=async (s,e)=>{
                if(!e.IsSuccess){Log(new Exception("WebView navigation failed: "+e.WebErrorStatus));if(smoke){result=1;Close();}return;}
                if(smoke)await SmokeTest();
            };
            core.Navigate("https://tower.local/index.html");timer.Start();
        }catch(Exception ex){
            Log(ex);result=1;
            Content=new TextBlock{Text="Не удалось запустить HTML-оверлей:\n"+ex.Message,Foreground=Brushes.LightGray,TextWrapping=TextWrapping.Wrap,Margin=new Thickness(20)};
            if(smoke)Close();
        }
    }

    void SetHeight(double height){MinHeight=0;MaxHeight=double.PositiveInfinity;Height=height;MinHeight=height;MaxHeight=height;}
    void PushSnapshot()
    {
        if(!ready)return;
        try{
            string raw=File.ReadAllText(snapshotPath);
            if(raw==lastData)return;
            web.CoreWebView2.PostWebMessageAsJson(raw);lastData=raw;
        }catch(IOException){}catch(Exception ex){Log(ex);}
    }

    async Task SmokeTest()
    {
        try{
            await Task.Delay(4000);
            await web.CoreWebView2.ExecuteScriptAsync("document.getElementById('back-icon').click()");
            await Task.Delay(150);
            string ok=await web.CoreWebView2.ExecuteScriptAsync("Boolean(window.Tower && window.Tower.ready && document.querySelectorAll('.room').length)");
            if(ok!="true")throw new Exception("HTML did not render live project rooms");
            string tower=await web.CoreWebView2.ExecuteScriptAsync("document.querySelectorAll('.tower-floor').length === 1 && Boolean(document.querySelector('.scene canvas')) && [...document.querySelectorAll('.employee-marker')].every(m => m.dataset.agentId && m.dataset.status !== 'completed')");
            if(tower!="true")throw new Exception("Selected floor or truthful employee presence missing");
            string overview=await web.CoreWebView2.ExecuteScriptAsync("Boolean(document.body.classList.contains('overview-mode') && document.querySelectorAll('.overview-floor').length)");
            if(overview!="true")throw new Exception("Whole tower home screen missing");
            if(!AllowsTransparency || web.DefaultBackgroundColor.A!=0)throw new Exception("Native overlay is not transparent");
            string chrome=await web.CoreWebView2.ExecuteScriptAsync("getComputedStyle(document.getElementById('details')).display === 'none' && getComputedStyle(document.body).backgroundColor === 'rgba(0, 0, 0, 0)'");
            if(chrome!="true")throw new Exception("Overview chrome or opaque background remains");
            await web.CoreWebView2.ExecuteScriptAsync("document.getElementById('pin').click()");
            await Task.Delay(100);
            if(Topmost)throw new Exception("Pin control did not reach native window");
            await web.CoreWebView2.ExecuteScriptAsync("document.getElementById('pin').click()");
            await Task.Delay(100);
            if(!Topmost)throw new Exception("Pin control did not restore topmost");
            var negative=ClampPosition(new Rect(-2100,900,340,300),new Rect(-1920,0,1920,1040));
            if(negative.X!=-1920 || negative.Y!=740)throw new Exception("Negative monitor work-area clamp failed");
            var rightEdge=ClampPosition(new Rect(1900,1040,340,300),new Rect(0,0,1920,1040));
            if(rightEdge.X!=1580 || rightEdge.Y!=740)throw new Exception("Right/bottom clamp failed");
            var savedOverview=new Point(Left,Top);
            await web.CoreWebView2.ExecuteScriptAsync("document.querySelector('.overview-floor').click()");
            await Task.Delay(200);
            if(Math.Abs(Width-340)>1 || Math.Abs(Height-300)>1)throw new Exception("Compact floor window size failed");
            if(!MonitorWorkArea().Contains(new Rect(Left,Top,Width,Height)))throw new Exception("Room extends outside monitor work area");
            using(var stream=File.Create(Path.Combine(folder,"runtime/compact-floor-smoke.png")))
                await web.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream);
            Left+=31;Top+=19;
            await web.CoreWebView2.ExecuteScriptAsync("document.getElementById('back-icon').click()");
            await Task.Delay(200);
            if(Math.Abs(Width-650)>1 || Math.Abs(Height-560)>1)throw new Exception("Back icon did not restore overview size");
            if(Math.Abs(Left-savedOverview.X)>1 || Math.Abs(Top-savedOverview.Y)>1)throw new Exception("Room movement changed saved overview position");
            Left=MonitorWorkArea().Left-25;
            double partialLeft=Left;
            await web.CoreWebView2.ExecuteScriptAsync("document.querySelector('.overview-floor').click()");
            await Task.Delay(150);
            await web.CoreWebView2.ExecuteScriptAsync("document.getElementById('back-icon').click()");
            await Task.Delay(150);
            if(Math.Abs(Left-partialLeft)>1)throw new Exception("Partially offscreen overview was not restored exactly");
            Left=savedOverview.X;
            Width=1000;await Task.Delay(150);
            string overflow=await web.CoreWebView2.ExecuteScriptAsync("document.documentElement.scrollWidth > innerWidth || document.documentElement.scrollHeight > innerHeight");
            if(overflow!="false")throw new Exception("HTML overflow in wide window");
            Width=650;
            await Task.Delay(150);
            using(var stream=File.Create(Path.Combine(folder,"runtime/html-host-smoke.png")))
                await web.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream);
            using(var bitmap=new System.Drawing.Bitmap(Path.Combine(folder,"runtime/html-host-smoke.png")))
                if(bitmap.GetPixel(0,0).A!=0)throw new Exception("WebView capture background is opaque");
            File.WriteAllText(Path.Combine(folder,"runtime/html-host-result.txt"),"PASS: transparent composition window, clear alpha background, native pin controls, live towers, wide-window layout");
        }catch(Exception ex){result=1;File.WriteAllText(Path.Combine(folder,"runtime/html-host-result.txt"),"FAIL: "+ex);}
        Close();
    }
    void Log(Exception ex){try{File.AppendAllText(Path.Combine(folder,"runtime/html-host-error.log"),DateTime.UtcNow.ToString("o")+" "+ex+Environment.NewLine);}catch{}}
}
