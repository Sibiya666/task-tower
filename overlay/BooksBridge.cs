using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

// Native authority and bounded helper ownership. No WebView value chooses a
// process, configuration path, repository allowlist or working directory.
public sealed class BooksBridge : IDisposable
{
    public const int FrameLimit=8*1024*1024, StreamLimit=64*1024*1024, FrameCount=32;
    static readonly UTF8Encoding Utf8=new UTF8Encoding(false,true);
    readonly HashSet<string> repositories=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    readonly HashSet<string> projects=new HashSet<string>(StringComparer.Ordinal);
    readonly object gate=new object();
    Process process;
    long attempt;
    bool disposed, refreshing;
    string latest;
    DateTime? lastSuccess;
    static JavaScriptSerializer Serializer(){return new JavaScriptSerializer{MaxJsonLength=FrameLimit,RecursionLimit=100};}
    static string Serialize(Dictionary<string,object> value)
    {
        string raw=Serializer().Serialize(value);
        if(Utf8.GetByteCount(raw)+1>FrameLimit)throw new FormatException();
        return raw;
    }
    public string LatestJson {get {lock(gate)return latest;}}
    public DateTime? LastSuccessUtc {get {lock(gate)return lastSuccess;}}
    public bool IsRefreshing {get {lock(gate)return refreshing;}}
    public long AttemptId {get {lock(gate)return attempt;}}

    public BooksBridge(IEnumerable<string> configuredRepositories,IEnumerable<string> configuredProjects)
    {
        foreach(var repo in configuredRepositories)
            if(Regex.IsMatch(repo,@"\A[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*\z"))repositories.Add(repo);
        foreach(var url in configuredProjects)
            if(Regex.IsMatch(url,@"\Ahttps://github\.com/(users|orgs)/[A-Za-z0-9-]+/projects/[1-9][0-9]*\z"))projects.Add(url);
    }
    public static BooksBridge FromConfiguration(string path)
    {
        var repos=new List<string>();var urls=new List<string>();
        if(!String.IsNullOrEmpty(path))try{
            // Reject reparse points before resolving, including ancestor junctions.
            var file=new FileInfo(Path.GetFullPath(path));
            if((file.Attributes&FileAttributes.ReparsePoint)!=0)throw new IOException();
            for(var parent=file.Directory;parent!=null;parent=parent.Parent)
                if((parent.Attributes&FileAttributes.ReparsePoint)!=0)throw new IOException();
            if(file.Length>1024*1024)throw new IOException();
            var value=Parse(File.ReadAllText(file.FullName,Utf8));
            if(value.Count!=2 || !value.ContainsKey("version") || Integer(value["version"])!=1)throw new FormatException();
            var rows=value["projects"] as object[];if(rows==null)throw new FormatException();
            foreach(var row in rows){
                var entry=row as Dictionary<string,object>;if(entry==null)throw new FormatException();
                var repo=entry["repository"] as string;
                if(repo==null || !Regex.IsMatch(repo,@"\A[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*\z"))throw new FormatException();
                repos.Add(repo);
                object project;if(entry.TryGetValue("project_url",out project) && project!=null){
                    string url=project as string;
                    if(url==null || !Regex.IsMatch(url,@"\Ahttps://github\.com/(users|orgs)/[A-Za-z0-9-]+/projects/[1-9][0-9]*\z"))throw new FormatException();
                    urls.Add(url);
                }
            }
        }catch{repos.Clear();urls.Clear();}
        return new BooksBridge(repos,urls);
    }
    public bool IsAllowedSource(string url)
    {
        if(String.IsNullOrEmpty(url) || url.Length>8192 || url.Any(c=>Char.IsControl(c)||c=='\\') || url.Contains("?") || url.Contains("#"))return false;
        // Check raw spelling before Uri can normalize traversal or authority.
        if(!url.StartsWith("https://github.com/",StringComparison.Ordinal))return false;
        Uri uri;if(!Uri.TryCreate(url,UriKind.Absolute,out uri) || uri.Host!="github.com" || uri.Scheme!="https" || !uri.IsDefaultPort || uri.UserInfo!="")return false;
        if(projects.Contains(url))return true;
        var match=Regex.Match(url,@"\Ahttps://github\.com/([^/]+/[^/]+)/(.*)\z");
        if(!match.Success || !repositories.Contains(match.Groups[1].Value))return false;
        string path=match.Groups[2].Value;
        if(Regex.IsMatch(path,@"\A(?:issues|pull|milestone)/[1-9][0-9]*\z"))return true;
        var blob=Regex.Match(path,@"\Ablob/[0-9a-fA-F]{40}/(.+)\z");if(!blob.Success)return false;
        string relative=blob.Groups[1].Value;
        if(Regex.IsMatch(relative,@"%(?:2f|5c|2e|25)",RegexOptions.IgnoreCase))return false;
        // Invalid percent escapes and decoded controls must not reach a browser.
        if(Regex.IsMatch(relative,@"%(?![0-9a-fA-F]{2})"))return false;
        string decoded=Uri.UnescapeDataString(relative);
        if(!decoded.EndsWith(".md",StringComparison.OrdinalIgnoreCase) || decoded.Any(c=>Char.IsControl(c)||c=='\\'||c==':'||c=='?'||c=='#'))return false;
        return decoded.Split('/').All(part=>part!="" && part!="." && part!="..");
    }
    public bool OpenSource(string url,Action<string> opener)
    {
        if(!IsAllowedSource(url))return false;
        try{opener(url);return true;}catch{return false;}
    }
    public static string QuoteArgument(string value)
    {
        if(value==null || value.IndexOf('\0')>=0)throw new ArgumentException();
        var result=new StringBuilder("\"");int slashes=0;
        foreach(char c in value){
            if(c=='\\'){slashes++;continue;}
            if(c=='\"'){result.Append('\\',slashes*2+1);result.Append(c);slashes=0;continue;}
            result.Append('\\',slashes);slashes=0;result.Append(c);
        }
        result.Append('\\',slashes*2);return result.Append('"').ToString();
    }
    public static ProcessStartInfo HelperStartInfo(string python,string root)
    {
        return new ProcessStartInfo(python,"-m task_tower.overlay_books"){
            WorkingDirectory=Path.GetFullPath(root),UseShellExecute=false,CreateNoWindow=true,
            RedirectStandardOutput=true,RedirectStandardError=true};
    }
    public static bool TryMessage(string source,string raw,out string action,out string url)
    {
        action=null;url=null;
        if(source!="https://tower.local/index.html" || raw==null)return false;
        try{
            if(Utf8.GetByteCount(raw)>16384)return false;
            var value=Parse(raw);object a;
            if(!value.TryGetValue("action",out a) || !(a is string))return false;
            action=(string)a;
            if(action=="books-refresh")return value.Count==1;
            object target;
            if(action!="books-open-source" || value.Count!=2 || !value.TryGetValue("url",out target) || !(target is string))return false;
            url=(string)target;return true;
        }catch{return false;}
    }
    static long Integer(object value)
    {
        if(value is int)return (int)value;if(value is long)return (long)value;throw new FormatException();
    }
    static Dictionary<string,object> Parse(string raw)
    {
        // JavaScriptSerializer otherwise silently overwrites duplicate keys.
        var stack=new Stack<HashSet<string>>();
        for(int i=0;i<raw.Length;i++){
            char c=raw[i];if(c=='{'){stack.Push(new HashSet<string>(StringComparer.Ordinal));continue;}
            if(c=='}'){if(stack.Count==0)throw new FormatException();stack.Pop();continue;}
            if(c!='"')continue;
            int start=i++;bool ended=false;
            for(;i<raw.Length;i++){
                if(raw[i]=='\\'){i++;continue;}
                if(raw[i]=='"'){ended=true;break;}
            }
            if(!ended)throw new FormatException();
            int end=i;int next=i+1;while(next<raw.Length && Char.IsWhiteSpace(raw[next]))next++;
            if(next<raw.Length && raw[next]==':'){
                string key=Serializer().Deserialize<string>(raw.Substring(start,end-start+1));
                if(stack.Count==0 || !stack.Peek().Add(key))throw new FormatException();
            }
        }
        var result=Serializer().DeserializeObject(raw) as Dictionary<string,object>;if(result==null)throw new FormatException();return result;
    }
    Dictionary<string,object> Frame(string raw,long previous)
    {
        var value=Parse(raw);
        var keys=new HashSet<string>("kind version sequence final state fetched_at entries errors".Split(' '));
        if(value.Count!=keys.Count || value.Keys.Any(k=>!keys.Contains(k)) || (string)value["kind"]!="books" || Integer(value["version"])!=1 || Integer(value["sequence"])<=previous || !(value["final"] is bool))throw new FormatException();
        var state=value["state"] as string;
        if(!new[]{"ready","partial","unavailable","unconfigured"}.Contains(state))throw new FormatException();
        if(value["fetched_at"]!=null && !(value["fetched_at"] is string))throw new FormatException();
        var entries=value["entries"] as object[];var errors=value["errors"] as object[];
        if(entries==null || entries.Length>10000 || errors==null)throw new FormatException();
        var fields=new HashSet<string>("id repository number project book title source status remote_state verification description phase blockers blocked_by results history relationships stages remote_attempt created_at updated_at capture path commit artifact_state declaration_source issues milestone available".Split(' '));
        foreach(var item in entries){
            var entry=item as Dictionary<string,object>;
            if(entry==null || entry.Keys.Any(k=>!fields.Contains(k)))throw new FormatException();
            foreach(string key in new[]{"id","repository","project","book","source","title","status"})if(!entry.ContainsKey(key)||!(entry[key] is string))throw new FormatException();
            string repo=(string)entry["repository"];
            if(!repositories.Contains(repo) || !IsAllowedSource((string)entry["source"]))throw new FormatException();
            if((string)entry["book"]!="library"){
                if(!new[]{"ideas","tasks"}.Contains((string)entry["book"]) || !entry.ContainsKey("number") || Integer(entry["number"])<1 ||
                    (string)entry["id"]!=repo+"#"+Integer(entry["number"]) || (string)entry["source"]!="https://github.com/"+repo+"/issues/"+Integer(entry["number"]))throw new FormatException();
                object proof;if(!entry.TryGetValue("verification",out proof)|| !new[]{"pending","verified","unverified","not_required"}.Contains(proof as string))throw new FormatException();
                if((string)entry["status"]=="done" && (string)proof!="verified")throw new FormatException();
                if(state=="ready" && (string)proof=="pending")throw new FormatException();
            }else{
                if(!entry.ContainsKey("commit") || !(entry["commit"] is string) || !Regex.IsMatch((string)entry["commit"],@"\A[0-9a-f]{40}\z") ||
                    !entry.ContainsKey("path") || !(entry["path"] is string) || (string)entry["id"]!=repo+":"+(string)entry["path"]+"@"+(string)entry["commit"])throw new FormatException();
                string prefix="https://github.com/"+repo+"/blob/"+(string)entry["commit"]+"/";
                string source=(string)entry["source"];
                if(!source.StartsWith(prefix,StringComparison.Ordinal) || Uri.UnescapeDataString(source.Substring(prefix.Length))!=(string)entry["path"])throw new FormatException();
            }
        }
        foreach(var item in errors){var error=item as Dictionary<string,object>;if(error==null || error.Count!=3 || new[]{"project","source","error"}.Any(k=>!error.ContainsKey(k)||!(error[k] is string)))throw new FormatException();}
        if(state=="ready" && errors.Length!=0)throw new FormatException();
        Serialize(value);
        return value;
    }
    Dictionary<string,object> Retained(string state,bool error)
    {
        Dictionary<string,object> value;
        if(latest!=null)value=Parse(latest);
        else value=new Dictionary<string,object>{{"kind","books"},{"version",1},{"sequence",1},{"final",false},{"fetched_at",null},{"entries",new object[0]},{"errors",new object[0]}};
        value["state"]=state;value["stale"]=true;value["final"]=false;
        foreach(var item in (object[])value["entries"]){var row=(Dictionary<string,object>)item;if((string)row["book"]!="library"){
            row["verification"]="pending";if((string)row["status"]=="done")row["status"]="needs_input";
        }}
        if(error)value["errors"]=new object[]{new Dictionary<string,object>{{"project",""},{"source",""},{"error","Books refresh interrupted or invalid"}}};
        return value;
    }
    bool Current(long id){return !disposed && attempt==id;}
    void Publish(long id,Dictionary<string,object> value,Action<string> publish)
    {
        lock(gate){
            if(!Current(id))return;
            try{latest=Serialize(value);}
            catch{latest="{\"kind\":\"books\",\"version\":1,\"sequence\":1,\"final\":false,\"state\":\"unavailable\",\"fetched_at\":null,\"entries\":[],\"errors\":[{\"project\":\"\",\"source\":\"\",\"error\":\"Books snapshot limit exceeded\"}],\"stale\":true}";}
            // A disposed UI consumer cannot prevent helper cleanup.
            try{publish(latest);}catch{}
        }
    }
    public async Task RefreshAsync(ProcessStartInfo start,Action<string> publish,int timeoutMilliseconds=120000)
    {
        if(timeoutMilliseconds<1 || timeoutMilliseconds>120000)throw new ArgumentOutOfRangeException();
        long id;
        lock(gate){if(disposed || refreshing)return;refreshing=true;id=++attempt;}
        Process owned=null;Task reader=null;bool success=false,accepting=true;
        try{
            Dictionary<string,object> loading;lock(gate)loading=Retained("loading",false);Publish(id,loading,publish);
            // Enforce the shell-free redirected contract even for trusted callers.
            start.UseShellExecute=false;start.CreateNoWindow=true;start.RedirectStandardOutput=true;start.RedirectStandardError=true;
            owned=new Process{StartInfo=start};
            lock(gate){if(!Current(id))throw new OperationCanceledException();owned.Start();process=owned;}
            // Drain stderr with bounded memory, never log or serialize its contents.
            var stderr=owned.StandardError.BaseStream;
            Task drain=Task.Run(()=>{try{var scratch=new byte[4096];while(stderr.Read(scratch,0,scratch.Length)>0){}}catch{}});
            Process child=owned;
            reader=Task.Run(()=>{
                long previous=0,total=0;int frames=0;bool final=false;Dictionary<string,object> last=null;
                var bytes=new byte[16384];using(var line=new MemoryStream()){
                    var stdout=child.StandardOutput.BaseStream;int count;
                    while((count=stdout.Read(bytes,0,bytes.Length))>0){
                        total+=count;if(total>StreamLimit)throw new FormatException();
                        int begin=0;
                        for(int i=0;i<count;i++)if(bytes[i]==10){
                            line.Write(bytes,begin,i-begin);begin=i+1;
                            if(line.Length+1>FrameLimit || final || ++frames>FrameCount)throw new FormatException();
                            string raw=Utf8.GetString(line.ToArray());line.SetLength(0);
                            var value=Frame(raw,previous);previous=Integer(value["sequence"]);final=(bool)value["final"];last=value;
                            // Partial progress is immediate. Hold a terminal frame
                            // until EOF/exit validates that nothing followed it.
                            lock(gate){if(accepting && !final)Publish(id,value,publish);}
                        }
                        line.Write(bytes,begin,count-begin);if(line.Length+1>FrameLimit)throw new FormatException();
                    }
                    if(line.Length!=0 || !final)throw new FormatException();
                }
                child.WaitForExit();
                int expectedExit=new[]{"ready","unconfigured"}.Contains((string)last["state"])?0:1;
                if(child.ExitCode!=expectedExit)throw new FormatException();
                lock(gate){if(accepting)Publish(id,last,publish);}
                success=(string)last["state"]=="ready";
            });
            if(await Task.WhenAny(reader,Task.Delay(timeoutMilliseconds)).ConfigureAwait(false)!=reader)throw new TimeoutException();
            await reader.ConfigureAwait(false);
            lock(gate){if(Current(id) && success)lastSuccess=DateTime.UtcNow;}
        }catch{
            Dictionary<string,object> failed;lock(gate){accepting=false;failed=Retained("partial",true);if(((object[])failed["entries"]).Length==0)failed["state"]="unavailable";}Publish(id,failed,publish);
        }{
            if(owned!=null){
                try{if(!owned.HasExited)owned.Kill();}catch{}
                // Reap away from the UI thread; close pipes to release readers.
                await Task.Run(()=>{try{owned.WaitForExit(2000);}catch{}try{owned.StandardOutput.Close();owned.StandardError.Close();}catch{}}).ConfigureAwait(false);
                if(reader!=null){try{if(await Task.WhenAny(reader,Task.Delay(2000)).ConfigureAwait(false)==reader)await reader.ConfigureAwait(false);else GC.KeepAlive(reader.ContinueWith(t=>GC.KeepAlive(t.Exception),TaskContinuationOptions.OnlyOnFaulted));}catch{}}
                owned.Dispose();
            }
            lock(gate){if(attempt==id){process=null;refreshing=false;}}
        }
    }
    public void Dispose()
    {
        lock(gate){disposed=true;++attempt;refreshing=false;if(process!=null){try{if(!process.HasExited)process.Kill();}catch{}}}
    }
}
