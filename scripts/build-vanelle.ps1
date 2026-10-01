$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Join-Path $PSScriptRoot "..\out"
if (Test-Path $root) { Remove-Item -Recurse -Force $root }
New-Item -ItemType Directory -Force -Path "$root\src","$root\src-tauri\src","$root\src-tauri\capabilities","$root\src-tauri\binaries" | Out-Null

@'
{
  "name": "vanelle-local",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build": "vite build",
    "tauri": "tauri",
    "tauri:build": "tauri build"
  },
  "dependencies": {
    "@tauri-apps/api": "^2.8.0",
    "@tauri-apps/plugin-dialog": "^2.3.0",
    "react": "^19.1.1",
    "react-dom": "^19.1.1"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.8.0",
    "@vitejs/plugin-react": "^5.0.4",
    "typescript": "^5.9.2",
    "vite": "^7.1.7"
  }
}
'@ | Set-Content "$root\package.json" -Encoding utf8

@'
<!doctype html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vanelle Local</title></head>
<body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body>
</html>
'@ | Set-Content "$root\index.html" -Encoding utf8

@'
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

function App() {
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Initialisation…");

  async function refresh() {
    try {
      const m = await invoke("list_models");
      setModels(m);
      const current = await invoke("current_model");
      setModel(current || "");
      setStatus(current ? "Modèle actif : " + current : "Importez un modèle GGUF pour commencer");
    } catch (e) {
      setStatus(String(e));
    }
  }

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    let off;
    import("@tauri-apps/api/event").then(({ listen }) =>
      listen("chat://chunk", e => {
        const p = e.payload;
        if (p.delta) {
          setMessages(x => x.map((m, i) => i === x.length - 1 ? { ...m, content: m.content + p.delta } : m));
        }
        if (p.error) {
          setStatus(p.error);
          setBusy(false);
        }
        if (p.done) {
          setBusy(false);
          setStatus(model ? "Modèle actif : " + model : "Prêt");
        }
      })
    ).then(fn => off = fn);
    return () => off?.();
  }, [model]);

  async function importModel() {
    const p = await open({ multiple: false, filters: [{ name: "Modèle GGUF", extensions: ["gguf"] }] });
    if (typeof p !== "string") return;
    try {
      const m = await invoke("import_model", { path: p });
      await invoke("set_model", { id: m.id });
      await refresh();
    } catch (e) {
      setStatus(String(e));
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    if (!model) {
      setStatus("Importez d’abord un modèle GGUF.");
      return;
    }
    const next = [...messages, { role: "user", content: text }, { role: "assistant", content: "" }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      await invoke("chat", { messages: next.slice(0, -1) });
    } catch (e) {
      setStatus(String(e));
      setMessages(x => x.slice(0, -1));
      setBusy(false);
    }
  }

  return <div className="app">
    <aside>
      <div className="brand"><b>Vanelle</b><span>LOCAL AI</span></div>
      <button className="primary" onClick={() => setMessages([])}>Nouvelle conversation</button>
      <div className="label">Modèles locaux</div>
      {models.map(m =>
        <button key={m.id} className={m.id === model ? "model active" : "model"}
          onClick={async () => {
            try {
              await invoke("set_model", { id: m.id });
              setModel(m.id);
              setStatus("Modèle actif : " + m.id);
            } catch (e) {
              setStatus(String(e));
            }
          }}>
          {m.id}<small>{(m.size_bytes / 1073741824).toFixed(2)} Go</small>
        </button>
      )}
      {!models.length && <div className="muted">Aucun modèle importé.</div>}
      <div className="spacer" />
      <div className="privacy">Moteur local. Aucun fournisseur IA externe obligatoire.</div>
    </aside>
    <main>
      <header>
        <div><h1>Assistant local</h1><p>{status}</p></div>
        <button onClick={importModel}>Importer un GGUF</button>
      </header>
      <section className="messages">
        {!messages.length &&
          <div className="empty"><h2>Votre IA locale</h2><p>Importez un modèle GGUF, puis écrivez votre message.</p></div>}
        {messages.map((m, i) =>
          <article key={i} className={m.role}>
            <div className="who">{m.role === "user" ? "Vous" : "Vanelle"}</div>
            <div>{m.content || (busy && i === messages.length - 1 ? "Génération…" : "")}</div>
          </article>
        )}
      </section>
      <footer>
        <textarea value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="Écrivez votre message…" />
        <div className="footerbar">
          <span>Entrée : envoyer · Maj+Entrée : nouvelle ligne</span>
          <button className="send" disabled={busy || !input.trim()} onClick={send}>{busy ? "…" : "Envoyer"}</button>
        </div>
      </footer>
    </main>
  </div>;
}

createRoot(document.getElementById("root")).render(<App />);
'@ | Set-Content "$root\src\main.jsx" -Encoding utf8

@'
:root{font-family:Segoe UI,Arial,sans-serif;color:#111827;background:#f7f9fc}
*{box-sizing:border-box}body{margin:0}.app{height:100vh;display:grid;grid-template-columns:280px 1fr}
aside{background:#fff;border-right:1px solid #e5e7eb;padding:26px;display:flex;flex-direction:column;gap:14px}
main{min-width:0;display:flex;flex-direction:column}button,textarea{font:inherit}
button{border:1px solid #d9e0ea;background:#fff;border-radius:10px;padding:11px 14px;cursor:pointer;font-weight:650}
button:hover{border-color:#2563eb}.primary,.send{background:#2563eb;color:#fff;border-color:#2563eb}
.brand{display:flex;align-items:baseline;gap:8px;font-size:25px;margin-bottom:6px}.brand span{font-size:10px;letter-spacing:1.5px;color:#2563eb}
.label{font-size:11px;color:#64748b;font-weight:800;text-transform:uppercase;margin-top:12px}.model{text-align:left;width:100%}
.model small{display:block;color:#64748b;font-size:11px;margin-top:3px}.model.active{background:#eff6ff;border-color:#2563eb;color:#1d4ed8}
.muted,.privacy{color:#64748b;font-size:13px;line-height:1.5}.spacer{flex:1}
header{background:#fff;border-bottom:1px solid #e5e7eb;padding:18px 30px;display:flex;align-items:center;justify-content:space-between}
h1{margin:0;font-size:22px}header p{margin:5px 0 0;color:#64748b;font-size:13px}.messages{flex:1;overflow:auto;padding:32px 12%;display:flex;flex-direction:column;gap:18px}
.empty{margin:auto;text-align:center;color:#64748b}.empty h2{color:#111827}.user,.assistant{max-width:820px;padding:15px 18px;border-radius:16px;line-height:1.6}
.user{align-self:flex-end;background:#2563eb;color:#fff}.assistant{align-self:flex-start;background:#fff;border:1px solid #e2e8f0}
.who{font-size:12px;font-weight:700;opacity:.7;margin-bottom:4px}footer{background:#fff;border-top:1px solid #e5e7eb;padding:16px 12% 20px}
textarea{width:100%;min-height:80px;resize:vertical;padding:14px;border:1px solid #d9e0ea;border-radius:14px;outline:none}
.footerbar{display:flex;justify-content:space-between;align-items:center;color:#94a3b8;font-size:12px;margin-top:8px}
'@ | Set-Content "$root\src\style.css" -Encoding utf8

@'
[package]
name="vanelle-local"
version="1.0.0"
edition="2021"
build="build.rs"
[lib]
name="vanelle_local_lib"
crate-type=["cdylib","rlib"]
[build-dependencies]
tauri-build={version="2.4",features=[]}
[dependencies]
anyhow="1"
futures-util="0.3"
reqwest={version="0.12",default-features=false,features=["json","stream","rustls-tls"]}
serde={version="1",features=["derive"]}
serde_json="1"
tauri={version="2.5",features=[]}
tauri-plugin-dialog="2.3"
tauri-plugin-shell="2.3"
tokio={version="1",features=["process","time","sync"]}
'@ | Set-Content "$root\src-tauri\Cargo.toml" -Encoding utf8

"fn main(){tauri_build::build()}" | Set-Content "$root\src-tauri\build.rs" -Encoding utf8

@'
{"$schema":"https://schema.tauri.app/config/2","productName":"Vanelle Local","version":"1.0.0","identifier":"com.vanelle.local","build":{"beforeBuildCommand":"npm run build","frontendDist":"../dist"},"app":{"windows":[{"label":"main","title":"Vanelle Local","width":1280,"height":820,"minWidth":900,"minHeight":600}],"security":{"csp":"default-src 'self'; connect-src 'self' http://127.0.0.1:*; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'"}},"bundle":{"active":true,"targets":["nsis"],"externalBin":["binaries/llama-server"],"category":"Productivity","shortDescription":"Assistant IA local","longDescription":"Assistant conversationnel local basé sur un modèle GGUF et llama.cpp."}}
'@ | Set-Content "$root\src-tauri\tauri.conf.json" -Encoding utf8

@'
{"$schema":"../gen/schemas/desktop-schema.json","identifier":"default","description":"Permissions minimales","windows":["main"],"permissions":["core:default","event:default","dialog:default",{"identifier":"shell:allow-spawn","allow":[{"name":"llama-server","sidecar":true},{"name":"binaries/llama-server","sidecar":true}]},{"identifier":"shell:allow-execute","allow":[{"name":"llama-server","sidecar":true},{"name":"binaries/llama-server","sidecar":true}]}]}
'@ | Set-Content "$root\src-tauri\capabilities\default.json" -Encoding utf8

@'
#![cfg_attr(not(debug_assertions),windows_subsystem="windows")]
use anyhow::{anyhow,Result};
use futures_util::StreamExt;
use std::{fs,path::{Path,PathBuf},sync::Arc,time::Duration};
use tauri::{Emitter,Manager,State};
use tauri_plugin_shell::ShellExt;
use tokio::sync::Mutex;

#[derive(Clone,serde::Serialize,serde::Deserialize)]struct Model{id:String,path:String,size_bytes:u64}
#[derive(Clone,serde::Serialize,serde::Deserialize)]struct Msg{role:String,content:String}
struct AppState{model:Mutex<Option<Model>>,child:Mutex<Option<tauri_plugin_shell::process::CommandChild>>,dir:PathBuf}

fn models(dir:&Path)->Result<Vec<Model>>{fs::create_dir_all(dir)?;let mut v=Vec::new();for e in fs::read_dir(dir)?{let p=e?.path();if p.extension().and_then(|x|x.to_str()).map(|x|x.eq_ignore_ascii_case("gguf"))!=Some(true){continue}let md=fs::metadata(&p)?;v.push(Model{id:p.file_stem().and_then(|x|x.to_str()).unwrap_or("model").to_string(),path:p.to_string_lossy().into_owned(),size_bytes:md.len()})}v.sort_by(|a,b|a.id.cmp(&b.id));Ok(v)}
fn valid(p:&Path)->Result<()> {use std::io::Read;let mut f=fs::File::open(p)?;let mut m=[0u8;4];f.read_exact(&mut m)?;if &m!=b"GGUF"{return Err(anyhow!("Fichier invalide : signature GGUF absente."))}Ok(())}

async fn start(app:&tauri::AppHandle,s:&AppState)->Result<()>{
 if let Some(c)=s.child.lock().await.take(){let _=c.kill();}
 let m=s.model.lock().await.clone().ok_or_else(||anyhow!("Aucun modèle sélectionné."))?;
 let args=vec!["--model".into(),m.path,"--alias".into(),m.id,"--host".into(),"127.0.0.1".into(),"--port".into(),"18280".into(),"--ctx-size".into(),"4096".into(),"--threads".into(),"0".into(),"--n-gpu-layers".into(),"0".into(),"--jinja".into()];
 let (_events,child)=app.shell().sidecar("llama-server")?.args(args).spawn()?;
 *s.child.lock().await=Some(child);
 let c=reqwest::Client::new();
 for _ in 0..120 {if c.get("http://127.0.0.1:18280/health").send().await.map(|r|r.status().is_success()).unwrap_or(false){return Ok(())}tokio::time::sleep(Duration::from_millis(250)).await}
 Err(anyhow!("Le moteur local n'a pas démarré. Vérifiez le modèle et la mémoire."))
}

#[tauri::command]async fn list_models(s:State<'_,Arc<AppState>>)->Result<Vec<Model>,String>{models(&s.dir).map_err(|e|e.to_string())}
#[tauri::command]async fn current_model(s:State<'_,Arc<AppState>>)->Result<String,String>{Ok(s.model.lock().await.as_ref().map(|m|m.id.clone()).unwrap_or_default())}
#[tauri::command]async fn import_model(s:State<'_,Arc<AppState>>,path:String)->Result<Model,String>{let p=Path::new(&path);valid(p).map_err(|e|e.to_string())?;fs::create_dir_all(&s.dir).map_err(|e|e.to_string())?;let name=p.file_name().ok_or("Nom invalide").map_err(String::from)?;let d=s.dir.join(name);fs::copy(p,&d).map_err(|e|e.to_string())?;models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.path==d.to_string_lossy()).ok_or_else(||"Import introuvable".into())}
#[tauri::command]async fn set_model(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,id:String)->Result<(),String>{let m=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==id).ok_or("Modèle introuvable")?;*s.model.lock().await=Some(m);start(&app,&s).await.map_err(|e|e.to_string())}
#[tauri::command]async fn chat(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,messages:Vec<Msg>)->Result<(),String>{if s.model.lock().await.is_none(){return Err("Aucun modèle local sélectionné.".into())}let c=reqwest::Client::new();if !c.get("http://127.0.0.1:18280/health").send().await.map(|r|r.status().is_success()).unwrap_or(false){start(&app,&s).await.map_err(|e|e.to_string())?}let model=s.model.lock().await.as_ref().unwrap().id.clone();let body=serde_json::json!({"model":model,"messages":messages,"temperature":0.7,"max_tokens":1024,"stream":true});let r=c.post("http://127.0.0.1:18280/v1/chat/completions").json(&body).send().await.map_err(|e|e.to_string())?.error_for_status().map_err(|e|e.to_string())?;let mut st=r.bytes_stream();let mut buf=String::new();while let Some(chunk)=st.next().await{buf.push_str(&String::from_utf8_lossy(&chunk.map_err(|e|e.to_string())?));while let Some(i)=buf.find("\n\n"){let frame=buf[..i].to_string();buf.drain(..i+2);for line in frame.lines(){if !line.starts_with("data:"){continue}let p=line.trim_start_matches("data:").trim();if p=="[DONE]"{continue}if let Ok(v)=serde_json::from_str::<serde_json::Value>(p){if let Some(d)=v["choices"][0]["delta"]["content"].as_str(){if !d.is_empty(){app.emit("chat://chunk",serde_json::json!({"delta":d})).map_err(|e|e.to_string())?}}}}}}app.emit("chat://chunk",serde_json::json!({"done":true})).map_err(|e|e.to_string())?;Ok(())}

fn run()->Result<()>{tauri::Builder::default().plugin(tauri_plugin_shell::init()).plugin(tauri_plugin_dialog::init()).setup(|app|{let d=app.path().app_data_dir()?.join("models");fs::create_dir_all(&d)?;let initial=models(&d)?.first().cloned();let s=Arc::new(AppState{model:Mutex::new(initial),child:Mutex::new(None),dir:d});app.manage(s.clone());if s.model.blocking_lock().is_some(){let h=app.handle().clone();let ss=s.clone();tauri::async_runtime::spawn(async move{let _=start(&h,&ss).await;});}Ok(())}).invoke_handler(tauri::generate_handler![list_models,current_model,import_model,set_model,chat]).run(tauri::generate_context!()).map_err(|e|anyhow!(e.to_string()))?;Ok(())}
fn main(){run().expect("Vanelle Local failed");}
'@ | Set-Content "$root\src-tauri\src\main.rs" -Encoding utf8

Push-Location $root

git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$env:RUNNER_TEMP\llama.cpp"
cmake -S "$env:RUNNER_TEMP\llama.cpp" -B "$env:RUNNER_TEMP\llama-build" -DGGML_NATIVE=OFF -DGGML_VULKAN=OFF -DGGML_METAL=OFF -DLLAMA_BUILD_SERVER=ON -DLLAMA_CURL=OFF -DGGML_BACKEND_DL=OFF
cmake --build "$env:RUNNER_TEMP\llama-build" --config Release --target llama-server -j 2
Copy-Item "$env:RUNNER_TEMP\llama-build\bin\Release\llama-server.exe" "$root\src-tauri\binaries\llama-server-x86_64-pc-windows-msvc.exe"
if (!(Test-Path "$root\src-tauri\binaries\llama-server-x86_64-pc-windows-msvc.exe")) { throw "llama-server.exe manquant après compilation" }

npm install --no-audit --no-fund
npm run build
npm run tauri:build -- --target x86_64-pc-windows-msvc
Pop-Location

Write-Host "BUILD_OK";
