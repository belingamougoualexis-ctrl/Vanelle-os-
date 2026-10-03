#![cfg_attr(not(debug_assertions),windows_subsystem="windows")]
use anyhow::{anyhow,Result};
use futures_util::StreamExt;
use std::{fs,io::Read,path::{Path,PathBuf},process::Command,sync::Arc,time::Duration};
use tauri::{Emitter,Manager,State};
use tauri_plugin_shell::ShellExt;
use tokio::sync::{Mutex,RwLock};

#[derive(Clone,serde::Serialize,serde::Deserialize)]
struct Model{id:String,path:String,size_bytes:u64}
#[derive(Clone,serde::Serialize,serde::Deserialize)]
struct Msg{role:String,content:String}
#[derive(Clone,serde::Serialize,serde::Deserialize)]
struct Config{
 temperature:f32,
 max_tokens:u32,
 context_size:u32,
 threads:u32,
 gpu_mode:String,
 gpu_layers:String,
 system_prompt:String
}
impl Default for Config{
 fn default()->Self{Self{temperature:0.7,max_tokens:1024,context_size:4096,threads:0,gpu_mode:"auto".into(),gpu_layers:"auto".into(),system_prompt:"Tu es Vanelle, un assistant local utile, précis et honnête.".into()}}
}
#[derive(Clone,serde::Serialize)]
struct Document{name:String,size_bytes:u64,snippet:String}
struct AppState{
 model:RwLock<Option<Model>>,
 config:RwLock<Config>,
 child:Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
 dir:PathBuf,
 docs_path:PathBuf,
 model_state_path:PathBuf,
 docs:RwLock<Vec<(String,String)>>
}

fn models(dir:&Path)->Result<Vec<Model>>{
 fs::create_dir_all(dir)?;
 let mut v=Vec::new();
 for e in fs::read_dir(dir)?{
  let p=e?.path();
  if p.extension().and_then(|x|x.to_str()).map(|x|x.eq_ignore_ascii_case("gguf"))!=Some(true){continue}
  let md=fs::metadata(&p)?;
  v.push(Model{id:p.file_stem().and_then(|x|x.to_str()).unwrap_or("model").to_string(),path:p.to_string_lossy().into_owned(),size_bytes:md.len()});
 }
 v.sort_by(|a,b|a.id.cmp(&b.id));Ok(v)
}
fn valid(p:&Path)->Result<()>{
 let mut f=fs::File::open(p)?;let mut m=[0u8;4];f.read_exact(&mut m)?;
 if &m!=b"GGUF"{return Err(anyhow!("Fichier invalide : signature GGUF absente."))}
 Ok(())
}
fn load_docs(path:&Path)->Vec<(String,String)>{
 fs::read_to_string(path).ok().and_then(|s|serde_json::from_str(&s).ok()).unwrap_or_default()
}
fn save_docs(path:&Path,docs:&[(String,String)])->Result<()>{
 let tmp=path.with_extension("json.tmp");
 fs::write(&tmp,serde_json::to_vec(docs)?)?;
 if path.exists(){fs::remove_file(path)?;}
 fs::rename(tmp,path)?;
 Ok(())
}
fn load_model_id(path:&Path)->Option<String>{fs::read_to_string(path).ok().map(|s|s.trim().to_string()).filter(|s|!s.is_empty())}
fn save_model_id(path:&Path,id:&str)->Result<()>{fs::write(path,id.as_bytes())?;Ok(())}
fn extract_doc(path:&Path)->Result<String>{
 let ext=path.extension().and_then(|x|x.to_str()).unwrap_or("").to_lowercase();
 match ext.as_str(){
  "txt"|"md"|"markdown"|"json"|"csv"=>Ok(fs::read_to_string(path)?),
  "pdf"=>Ok(pdf_extract::extract_text(path).map_err(|e|anyhow!("PDF : {e}"))?),
  "docx"=>{
   let f=fs::File::open(path)?;let mut z=zip::ZipArchive::new(f)?;
   let mut s=String::new();let mut x=z.by_name("word/document.xml")?;x.read_to_string(&mut s)?;
   let mut out=String::new();let mut in_tag=false;
   for c in s.chars(){if c=='<'{in_tag=true;if !out.ends_with(' '){out.push(' ')}}else if c=='>'{in_tag=false}else if !in_tag{out.push(c)}}
   Ok(out.replace("&amp;","&").replace("&lt;","<").replace("&gt;",">"))
  }
  _=>Err(anyhow!("Format non pris en charge. Utilisez TXT, Markdown, JSON, CSV, PDF ou DOCX."))
 }
}
async fn vulkan_available(app:&tauri::AppHandle)->bool{
 let out=match app.shell().sidecar("llama-server-vulkan"){
  Ok(c)=>match c.args(["--list-devices"]).output().await{
   Ok(o)=>String::from_utf8_lossy(&o.stdout).to_string()+&String::from_utf8_lossy(&o.stderr),
   Err(_)=>return false
  },
  Err(_)=>return false
 };
 let low=out.to_lowercase();
 low.contains("vulkan")&&!low.contains("no devices")&&!low.contains("failed to initialize")
}
async fn start(app:&tauri::AppHandle,s:&AppState)->Result<String>{
 if let Some(c)=s.child.lock().await.take(){let _=c.kill();}
 let m=s.model.read().await.clone().ok_or_else(||anyhow!("Aucun modèle sélectionné."))?;
 let cfg=s.config.read().await.clone();
 let use_gpu=match cfg.gpu_mode.as_str(){
  "cpu"=>false,
  "gpu"=>true,
  _=>vulkan_available(app).await
 };
 let bin=if use_gpu{"llama-server-vulkan"}else{"llama-server-cpu"};
 let mut args=vec!["--model".into(),m.path.clone(),"--alias".into(),m.id.clone(),"--host".into(),"127.0.0.1".into(),"--port".into(),"18280".into(),"--ctx-size".into(),cfg.context_size.to_string(),"--n-gpu-layers".into(),if use_gpu{if cfg.gpu_layers=="auto"{"999".to_string()}else{cfg.gpu_layers.clone()}}else{"0".into()},"--jinja".into()];
 if cfg.threads>0{args.extend(["--threads".into(),cfg.threads.to_string()]);}
 let (_events,child)=app.shell().sidecar(bin)?.args(args).spawn()?;
 *s.child.lock().await=Some(child);
 let c=reqwest::Client::new();
 for _ in 0..160{
  if c.get("http://127.0.0.1:18280/health").send().await.map(|r|r.status().is_success()).unwrap_or(false){
   let msg=if use_gpu{"Moteur local : GPU Vulkan".to_string()}else{"Moteur local : CPU".to_string()};
   let _=app.emit("chat://chunk",serde_json::json!({"engine":msg}));
   return Ok(msg)
  }
  tokio::time::sleep(Duration::from_millis(250)).await;
 }
 Err(anyhow!("Le moteur local n'a pas démarré. Vérifiez le modèle et la mémoire."))
}

#[tauri::command]
async fn list_models(s:State<'_,Arc<AppState>>)->Result<Vec<Model>,String>{models(&s.dir).map_err(|e|e.to_string())}
#[tauri::command]
async fn current_model(s:State<'_,Arc<AppState>>)->Result<String,String>{Ok(s.model.read().await.as_ref().map(|m|m.id.clone()).unwrap_or_default())}
#[tauri::command]
async fn hardware_info(app:tauri::AppHandle)->Result<serde_json::Value,String>{
 let cpu=std::thread::available_parallelism().map(|x|x.get()).unwrap_or(1);
 #[cfg(target_os="windows")]
 let ps=Command::new("powershell").args(["-NoProfile","-Command","$g=Get-CimInstance Win32_VideoController | Where-Object {$_.Name}; $names=($g|ForEach-Object {$_.Name}) -join ' | '; $v=($g|ForEach-Object {[uint64]$_.AdapterRAM}|Measure-Object -Maximum).Maximum; $m=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; [pscustomobject]@{gpu=$names;vram=$v;ram=$m}|ConvertTo-Json -Compress"]).output();
 #[cfg(not(target_os="windows"))]
 let ps:Result<std::process::Output,std::io::Error>=Err(std::io::Error::new(std::io::ErrorKind::Other,"not windows"));
 let (gpu,ram,vram)=match ps{
  Ok(o)=>match serde_json::from_slice::<serde_json::Value>(&o.stdout){
   Ok(v)=>(
    v["gpu"].as_str().unwrap_or("GPU non détecté").to_string(),
    v["ram"].as_u64().map(|x|format!("{:.1} Go",x as f64/1073741824.0)).unwrap_or_else(||"RAM non détectée".into()),
    v["vram"].as_u64().map(|x|format!("{:.1} Go",x as f64/1073741824.0)).unwrap_or_else(||"VRAM non détectée".into())
   ),
   Err(_)=>( "GPU non détecté".into(),"RAM non détectée".into(),"VRAM non détectée".into())
  },
  Err(_)=>( "GPU non détecté".into(),"RAM non détectée".into(),"VRAM non détectée".into())
 };
 let vk=if vulkan_available(&app).await{"Vulkan disponible"}else{"Vulkan non disponible"};
 Ok(serde_json::json!({"cpu":format!("{} threads CPU disponibles",cpu),"ram":ram,"gpu":gpu,"vram":vram,"vulkan":vk}))
}
#[tauri::command]
async fn import_model(s:State<'_,Arc<AppState>>,path:String)->Result<Model,String>{
 let p=Path::new(&path);valid(p).map_err(|e|e.to_string())?;
 fs::create_dir_all(&s.dir).map_err(|e|e.to_string())?;
 let name=p.file_name().ok_or("Nom invalide").map_err(String::from)?;
 let d=s.dir.join(name);
 fs::copy(p,&d).map_err(|e|e.to_string())?;
 models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.path==d.to_string_lossy()).ok_or_else(||"Import introuvable".into())
}
#[tauri::command]
async fn remove_model(s:State<'_,Arc<AppState>>,id:String)->Result<(),String>{
 let m=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==id).ok_or("Modèle introuvable")?;
 fs::remove_file(m.path).map_err(|e|e.to_string())?;
 if load_model_id(&s.model_state_path).as_deref()==Some(id.as_str()){let _=fs::remove_file(&s.model_state_path);}
 Ok(())
}
#[tauri::command]
async fn set_model(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,id:String)->Result<(),String>{
 let m=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==id).ok_or("Modèle introuvable")?;
 save_model_id(&s.model_state_path,&m.id).map_err(|e|e.to_string())?;
 *s.model.write().await=Some(m);
 start(&app,&s).await.map_err(|e|e.to_string()).map(|_|())
}
#[tauri::command]
async fn stop_engine(s:State<'_,Arc<AppState>>)->Result<(),String>{
 if let Some(c)=s.child.lock().await.take(){let _=c.kill();}
 Ok(())
}
#[tauri::command]
async fn import_document(s:State<'_,Arc<AppState>>,path:String)->Result<Document,String>{
 let p=Path::new(&path);
 let md=fs::metadata(p).map_err(|e|e.to_string())?;
 if md.len()>100*1024*1024{return Err("Document trop volumineux (limite 100 Mo).".into());}
 let text=extract_doc(p).map_err(|e|e.to_string())?;
 let name=p.file_name().and_then(|x|x.to_str()).unwrap_or("document").to_string();
 let snippet=text.chars().take(500).collect::<String>();
 {
  let mut docs=s.docs.write().await;
  docs.retain(|(n,_)|n!=&name);
  docs.push((name.clone(),text.clone()));
  save_docs(&s.docs_path,&docs).map_err(|e|e.to_string())?;
 }
 Ok(Document{name,size_bytes:md.len(),snippet})
}
#[tauri::command]
async fn list_documents(s:State<'_,Arc<AppState>>)->Result<Vec<Document>,String>{
 let docs=s.docs.read().await;
 Ok(docs.iter().map(|(n,t)|Document{name:n.clone(),size_bytes:t.len() as u64,snippet:t.chars().take(500).collect()}).collect())
}
#[tauri::command]
async fn remove_document(s:State<'_,Arc<AppState>>,name:String)->Result<(),String>{
 let mut docs=s.docs.write().await;
 let before=docs.len();
 docs.retain(|(n,_)|n!=&name);
 if docs.len()==before{return Err("Document introuvable".into());}
 save_docs(&s.docs_path,&docs).map_err(|e|e.to_string())?;
 Ok(())
}
#[tauri::command]
async fn search_documents(s:State<'_,Arc<AppState>>,query:String,limit:usize)->Result<Vec<Document>,String>{
 let q=query.to_lowercase();let terms=q.split_whitespace().filter(|x|x.len()>2).collect::<Vec<_>>();
 let mut scored=s.docs.read().await.iter().cloned().map(|(n,t)|{
  let low=t.to_lowercase();
  let score=terms.iter().map(|x|low.matches(x).count()).sum::<usize>();
  (score,n,t)
 }).filter(|x|x.0>0).collect::<Vec<_>>();
 scored.sort_by(|a,b|b.0.cmp(&a.0));
 Ok(scored.into_iter().take(limit.max(1)).map(|(_,n,t)|{
  let low=t.to_lowercase();let pos=terms.first().and_then(|x|low.find(x)).unwrap_or(0);
  let start=pos.saturating_sub(180);let sn=t.chars().skip(start).take(900).collect::<String>();
  Document{name:n.clone(),size_bytes:t.len() as u64,snippet:sn}
 }).collect())
}
#[tauri::command]
async fn chat(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,messages:Vec<Msg>,config:Config)->Result<(),String>{
 *s.config.write().await=config.clone();
 if s.model.read().await.is_none(){return Err("Aucun modèle local sélectionné.".into())}
 let c=reqwest::Client::new();
 if !c.get("http://127.0.0.1:18280/health").send().await.map(|r|r.status().is_success()).unwrap_or(false){
  start(&app,&s).await.map_err(|e|e.to_string())?;
 }
 let model=s.model.read().await.as_ref().unwrap().id.clone();
 let body=serde_json::json!({"model":model,"messages":messages,"temperature":config.temperature,"max_tokens":config.max_tokens,"stream":true});
 let r=c.post("http://127.0.0.1:18280/v1/chat/completions").json(&body).send().await.map_err(|e|e.to_string())?.error_for_status().map_err(|e|e.to_string())?;
 let mut st=r.bytes_stream();let mut buf=String::new();
 while let Some(chunk)=st.next().await{
  buf.push_str(&String::from_utf8_lossy(&chunk.map_err(|e|e.to_string())?));
  while let Some(i)=buf.find("\n\n"){
   let frame=buf[..i].to_string();buf.drain(..i+2);
   for line in frame.lines(){
    if !line.starts_with("data:"){continue}
    let p=line.trim_start_matches("data:").trim();if p=="[DONE]"{continue}
    if let Ok(v)=serde_json::from_str::<serde_json::Value>(p){
     if let Some(d)=v["choices"][0]["delta"]["content"].as_str(){
      if !d.is_empty(){app.emit("chat://chunk",serde_json::json!({"delta":d})).map_err(|e|e.to_string())?}
     }
    }
   }
  }
 }
 app.emit("chat://chunk",serde_json::json!({"done":true})).map_err(|e|e.to_string())?;Ok(())
}
fn run()->Result<()>{
 tauri::Builder::default()
 .plugin(tauri_plugin_shell::init())
 .plugin(tauri_plugin_dialog::init())
 .setup(|app|{
  let app_data=app.path().app_data_dir()?;let d=app_data.join("models");fs::create_dir_all(&d)?;
  let docs_path=app_data.join("documents.json");
  let model_state_path=app_data.join("current-model.txt");
  let initial_models=models(&d)?;
  let saved_id=load_model_id(&model_state_path);
  let initial= saved_id.as_deref().and_then(|id|initial_models.iter().find(|m|m.id==id).cloned()).or_else(||initial_models.first().cloned());
  let initial_docs=load_docs(&docs_path);
  let s=Arc::new(AppState{model:RwLock::new(initial),config:RwLock::new(Config::default()),child:Mutex::new(None),dir:d,docs_path,model_state_path,docs:RwLock::new(initial_docs)});
  app.manage(s.clone());
  if s.model.blocking_read().is_some(){
   let h=app.handle().clone();let ss=s.clone();
   tauri::async_runtime::spawn(async move{let _=start(&h,&ss).await;});
  }
  Ok(())
 })
 .invoke_handler(tauri::generate_handler![list_models,current_model,hardware_info,import_model,remove_model,set_model,stop_engine,import_document,list_documents,remove_document,search_documents,chat])
 .run(tauri::generate_context!()).map_err(|e|anyhow!(e.to_string()))?;
 Ok(())
}
fn main(){run().expect("Vanelle Local failed");}
