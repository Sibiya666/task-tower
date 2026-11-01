const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');

test('host integrates the trusted books bridge without changing composition or collector delivery',()=>{
  const host=fs.readFileSync(path.join(__dirname,'TowerHost.cs'),'utf8');
  const launch=fs.readFileSync(path.join(__dirname,'run-html-overlay.ps1'),'utf8');
  assert.match(host,/Task RefreshBooksAsync\(/);
  assert.match(host,/bool OpenBookSource\(string url\)/);
  assert.match(host,/BooksBridge\.TryMessage\(e\.Source/);
  assert.match(host,/books\.Dispose\(\)/);
  assert.match(host,/WebView2CompositionControl/);
  assert.match(host,/PostWebMessageAsJson\(raw\);lastData=raw/);
  assert.match(launch,/BooksBridge\.cs/);
});

test('compiled native boundary: allowlist, quoting, progressive read, timeout, invalid streams and cleanup', {timeout:90000}, ()=>{
  const bridge=path.join(__dirname,'BooksBridge.cs');
  assert.ok(fs.existsSync(bridge),'BooksBridge production boundary is missing');
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'books native Ю '));
  const python=path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
  const helper=path.join(dir,'helper.py');
  fs.writeFileSync(helper,String.raw`import json,sys,time,os
mode=sys.argv[1]; barrier=sys.argv[2]
with open(barrier+'.pid','w') as process_file: process_file.write(str(os.getpid()))
def frame(sequence, final=False, state='partial', library=False):
 row=dict(id='owner/repo#1',repository='owner/repo',number=1,project='p',book='tasks',title='Issue',source='https://github.com/owner/repo/issues/1',status='open',verification='pending')
 if state=='ready': row.update(status='done',verification='verified')
 rows=[row]
 if library: rows.append(dict(id='owner/repo:README.md@'+'a'*40,repository='owner/repo',project='p',book='library',title='README.md',path='README.md',commit='a'*40,source='https://github.com/owner/repo/blob/'+'a'*40+'/README.md',status='source',artifact_state='accepted',available=True))
 return dict(kind='books',version=1,sequence=sequence,final=final,state=state,fetched_at='2026-11-01T00:00:00Z',entries=rows,errors=[])
def send(value): print(json.dumps(value),flush=True)
if mode=='invalidutf8': sys.stdout.buffer.write(b'\xff\n');sys.stdout.buffer.flush()
elif mode=='malformed': print('{bad',flush=True)
elif mode=='missingfinal': send(frame(1))
elif mode=='nonmonotonic': send(frame(2));send(frame(1,True))
elif mode=='afterfinal': send(frame(1,True,'ready'));send(frame(2,True,'ready'))
elif mode=='provenance':
 value=frame(1,True,'ready');value['entries'][0]['source']='https://github.com/other/repo/issues/1';send(value)
elif mode=='privatefield':
 value=frame(1,True,'ready');value['entries'][0]['checkout']='PRIVATE';send(value)
elif mode=='entries':
 value=frame(1,True);value['entries']*=10001;send(value)
elif mode=='linecap': print('x'*(8*1024*1024+1),flush=True)
elif mode=='frames':
 for i in range(33): send(frame(i+1,i==32))
elif mode=='totalcap':
 for i in range(10):
  value=frame(i+1,i==9);value['entries'][0]['description']='x'*(7*1024*1024);send(value)
elif mode=='ready': send(frame(1,True,'ready'))
else:
 send(frame(1));send(frame(2,library=True))
 while not os.path.exists(barrier): time.sleep(.01)
 send(frame(3,True,'ready',True))
`);
  const harness=String.raw`
using System;using System.IO;using System.Diagnostics;using System.Collections.Generic;using System.Threading;using System.Threading.Tasks;using System.Web.Script.Serialization;
public static class NativeBooksTest {
 static string python,helper,dir,rootDir;static JavaScriptSerializer json=new JavaScriptSerializer(){MaxJsonLength=10*1024*1024};
 static void Check(bool ok,string message){if(!ok)throw new Exception(message);}
 static ProcessStartInfo Start(string mode,string barrier){return new ProcessStartInfo(python,BooksBridge.QuoteArgument(helper)+" "+BooksBridge.QuoteArgument(mode)+" "+BooksBridge.QuoteArgument(barrier)){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};}
 static Dictionary<string,object> Parse(string raw){return (Dictionary<string,object>)json.DeserializeObject(raw);}
 public static void Run(string p,string h,string d,string root){python=p;helper=h;dir=d;rootDir=root;RunAsync().GetAwaiter().GetResult();}
 static async Task RunAsync(){
 var b=new BooksBridge(new[]{"owner/repo"},new[]{"https://github.com/users/owner/projects/1"});
 string root="https://github.com/owner/repo/";
 string config=Path.Combine(dir,"private connections.json");
 File.WriteAllText(config,json.Serialize(new {version=1,projects=new[]{new{id="p",repository="owner/repo",checkout=dir,runner_label="local",project_url="https://github.com/users/owner/projects/1"}}}));
 using(var configured=BooksBridge.FromConfiguration(config)){
  Check(configured.IsAllowedSource(root+"issues/1"),"private config repo");
  Check(configured.IsAllowedSource("https://github.com/users/owner/projects/1"),"private config exact project");
  File.WriteAllText(config,"{}");Check(configured.IsAllowedSource(root+"issues/1"),"allowlist immutable");
 }
 using(var invalid=BooksBridge.FromConfiguration(config))Check(!invalid.IsAllowedSource(root+"issues/1"),"invalid config fail closed");
 using(var actualHelper=new BooksBridge(new string[0],new string[0])){
  var info=BooksBridge.HelperStartInfo(python,rootDir);info.EnvironmentVariables.Remove("TASK_TOWER_CONNECTIONS");
  Check(info.Arguments=="-m task_tower.overlay_books" && !info.UseShellExecute && info.WorkingDirectory==Path.GetFullPath(rootDir),"fixed canonical module invocation");
  await actualHelper.RefreshAsync(info,s=>{},5000);Check(Parse(actualHelper.LatestJson)["state"].ToString()=="unconfigured","actual canonical module helper");
 }
 foreach(string tail in new[]{"issues/1","pull/2","milestone/3","blob/"+new string('a',40)+"/docs/a%20b.md"})Check(b.IsAllowedSource(root+tail),"allowed source "+tail);
 Check(b.IsAllowedSource("https://github.com/users/owner/projects/1"),"configured project");
 foreach(string url in new[]{root+"issues/0",root+"issues/1?x",root+"issues/1#x",root+"issues/1/",root+"blob/main/a.md",root+"blob/"+new string('a',40)+"/../a.md",root+"blob/"+new string('a',40)+"/%2e%2e/a.md",root+"blob/"+new string('a',40)+"/a%2fb.md",root+"blob/"+new string('a',40)+"/a%5cb.md",root+"blob/"+new string('a',40)+"/a%252fb.md","https://github.com:443/owner/repo/issues/1","https://x@github.com/owner/repo/issues/1","https://github.com.evil/owner/repo/issues/1","https://github.com/other/repo/issues/1","https://github.com/users/owner/projects/2","https://github.com/owner/repo/issues/1\n","https://github.com\\owner/repo/issues/1","file:///x"})Check(!b.IsAllowedSource(url),"rejected source "+url);
 int opened=0;Check(b.OpenSource(root+"issues/1",s=>{opened++;}),"open allowed");Check(!b.OpenSource("https://evil.invalid",s=>{opened++;}),"reject opener");Check(opened==1,"injected opener");
 string action,urlOut;Check(BooksBridge.TryMessage("https://tower.local/index.html","{\"action\":\"books-refresh\"}",out action,out urlOut),"refresh message");
 foreach(string source in new[]{"https://tower.local/other.html","https://tower.local/index.html?q","https://tower.local/index.html#x","https://tower.local.evil/index.html"})Check(!BooksBridge.TryMessage(source,"{\"action\":\"books-refresh\"}",out action,out urlOut),"origin");
 foreach(string msg in new[]{"{\"action\":\"books-refresh\",\"url\":\"x\"}","{\"action\":\"books-open-source\",\"url\":\"x\",\"extra\":1}","{\"action\":\"books-refresh\",\"action\":\"books-refresh\"}","{\"action\":\"books-refresh\",\"x\":\""+new string('x',16384)+"\"}"})Check(!BooksBridge.TryMessage("https://tower.local/index.html",msg,out action,out urlOut),"exact message");
 // Windows CRT argv roundtrip through the actual Python executable, with no shell.
 string quotes=Path.Combine(dir,"argv.py");File.WriteAllText(quotes,"import json,sys; print(json.dumps(sys.argv[1:],ensure_ascii=True))");
 string[] args={"", "space path Ю", "quote\"value", "trailing\\", "space and trailing\\", "& calc.exe | $()"};
 var psi=new ProcessStartInfo(python,BooksBridge.QuoteArgument(quotes)+" "+String.Join(" ",Array.ConvertAll(args,BooksBridge.QuoteArgument))){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true};
 using(var proc=Process.Start(psi)){var actual=json.Deserialize<string[]>(proc.StandardOutput.ReadToEnd());proc.WaitForExit();Check(String.Join("\n",args)==String.Join("\n",actual),"argv roundtrip");}
 string barrier=Path.Combine(dir,"release");var library=new TaskCompletionSource<bool>();var messages=new List<string>();
 Action<string> receive=raw=>{lock(messages)messages.Add(raw);var value=Parse(raw);if(((object[])value["entries"]).Length==2)library.TrySetResult(true);};
 var refresh=b.RefreshAsync(Start("block",barrier),receive,5000);
 Check(await Task.WhenAny(library.Task,Task.Delay(3500))==library.Task,"library before helper exit");
 Check(!refresh.IsCompleted && b.IsRefreshing,"live frames before exit");
 await b.RefreshAsync(Start("ready",barrier),receive,5000);Check(!refresh.IsCompleted,"single flight");
 File.WriteAllText(barrier,"");await refresh;Check(b.LastSuccessUtc.HasValue,"final ready success");var success=b.LastSuccessUtc;
 File.Delete(barrier);bool invalidated=false;
 var timed=b.RefreshAsync(Start("block",barrier),raw=>{receive(raw);if(Parse(raw)["state"].ToString()=="loading"){var entries=(object[])Parse(raw)["entries"];invalidated=((Dictionary<string,object>)entries[0])["verification"].ToString()=="pending";}},700);
 await timed;Check(invalidated,"old proof invalidated at new refresh");Check(b.LastSuccessUtc==success,"timeout last-success unchanged");var retained=Parse(b.LatestJson);Check(retained["state"].ToString()=="partial" && (bool)retained["stale"],"timeout stale partial");Check(((object[])retained["entries"]).Length==2,"timeout keeps library");Check(!b.IsRefreshing,"timeout reaped");
 int before;lock(messages)before=messages.Count;File.WriteAllText(barrier,"");await Task.Delay(80);lock(messages)Check(messages.Count==before,"late timed-out proof discarded");File.Delete(barrier);
 foreach(string mode in new[]{"malformed","invalidutf8","missingfinal","nonmonotonic","afterfinal","provenance","privatefield","entries","linecap","frames","totalcap"}){await b.RefreshAsync(Start(mode,barrier),receive,10000);Check(b.LastSuccessUtc==success,"invalid stream no success "+mode);Check((bool)Parse(b.LatestJson)["stale"],"invalid stream stale "+mode);}
 var closing=b.RefreshAsync(Start("block",barrier),receive,5000);await Task.Delay(200);int childId=Int32.Parse(File.ReadAllText(barrier+".pid"));b.Dispose();await closing;Check(!b.IsRefreshing,"close cleanup");
 bool alive=false;try{using(var child=Process.GetProcessById(childId))alive=!child.HasExited;}catch(ArgumentException){}Check(!alive,"closed helper actually reaped");
 Console.WriteLine("native books harness passed");
 }
}`;
  const harnessPath=path.join(dir,'Harness.cs');fs.writeFileSync(harnessPath,harness);
  const ps=path.join(dir,'run.ps1');
  const q=s=>`'${s.replaceAll("'","''")}'`;
  fs.writeFileSync(ps,`\uFEFF$ErrorActionPreference='Stop'\nAdd-Type -Path @(${q(bridge)},${q(harnessPath)}) -ReferencedAssemblies System.dll,System.Core.dll,System.Web.Extensions.dll\n[NativeBooksTest]::Run(${q(python)},${q(helper)},${q(dir)},${q(path.dirname(__dirname))})\n`,'utf8');
  try{
    const result=spawnSync('powershell.exe',['-NoProfile','-ExecutionPolicy','Bypass','-File',ps],{encoding:'utf8',timeout:85000,maxBuffer:2000000});
    assert.equal(result.status,0,`${result.stdout}\n${result.stderr}\n${result.error||''}`);
    assert.match(result.stdout,/native books harness passed/);
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
