#![cfg_attr(not(debug_assertions),windows_subsystem="windows")]

use anyhow::{anyhow, Result};
use futures_util::StreamExt;
use std::{fs, io::Read, path::{Path, PathBuf}, process::{Command, Stdio}, sync::Arc, time::Duration};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command as TokioCommand;
use tauri::{Emitter, Manager, State};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};
use tokio::sync::{Mutex, RwLock};

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Model {
    id: String,
    path: String,
    size_bytes: u64,
    format: String,
    family: String,
    architecture: String,
    backend: String,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Msg {
    role: String,
    content: String,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Config {
    temperature: f32,
    max_tokens: u32,
    context_size: u32,
    threads: u32,
    gpu_mode: String,
    gpu_layers: String,
    system_prompt: String,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            temperature: 0.7,
            max_tokens: 1024,
            context_size: 4096,
            threads: 0,
            gpu_mode: "auto".into(),
            gpu_layers: "auto".into(),
            system_prompt: "Tu es Vanelle, un assistant local utile, précis et honnête.".into(),
        }
    }
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Project {
    id: String,
    name: String,
    objective: String,
    model_id: String,
    dataset_path: Option<String>,
    adapter_path: Option<String>,
    merged_model_path: Option<String>,
    status: String,
    created_at: String,
    updated_at: String,
    examples: usize,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct DatasetInfo {
    project_id: String,
    path: String,
    examples: usize,
    chat_examples: usize,
    text_examples: usize,
    invalid_lines: usize,
    bytes: u64,
}


#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct VisionInfo {
    project_id: String,
    dataset_path: Option<String>,
    classes: Vec<String>,
    images: usize,
    checkpoint_path: Option<String>,
    best_accuracy: Option<f64>,
    status: String,
}

fn vision_file(dir:&Path,id:&str)->PathBuf{dir.join(format!("{id}-vision.json"))}
fn load_vision_info(dir:&Path,id:&str)->VisionInfo{
    fs::read_to_string(vision_file(dir,id)).ok()
        .and_then(|s|serde_json::from_str(&s).ok())
        .unwrap_or_else(||VisionInfo{project_id:id.into(),dataset_path:None,classes:Vec::new(),images:0,checkpoint_path:None,best_accuracy:None,status:"Aucun dataset vision".into()})
}
fn save_vision_info(dir:&Path,v:&VisionInfo)->Result<()>{fs::write(vision_file(dir,&v.project_id),serde_json::to_vec_pretty(v)?)?;Ok(())}
fn is_image_file(p:&Path)->bool{matches!(p.extension().and_then(|x|x.to_str()).unwrap_or("").to_lowercase().as_str(),"jpg"|"jpeg"|"png"|"bmp"|"webp"|"tif"|"tiff")}
fn image_count(root:&Path)->usize{fs::read_dir(root).map(|it|it.flatten().map(|e|{let p=e.path();if p.is_dir(){image_count(&p)}else if is_image_file(&p){1}else{0}}).sum()).unwrap_or(0)}
fn copy_images_only(src:&Path,dst:&Path)->Result<usize>{
    fs::create_dir_all(dst)?; let mut count=0usize;
    for e in fs::read_dir(src)?{
        let e=e?;let from=e.path();let to=dst.join(e.file_name());
        if from.is_dir(){count+=copy_images_only(&from,&to)?;} else if is_image_file(&from){
            if let Some(parent)=to.parent(){fs::create_dir_all(parent)?;} fs::copy(&from,&to)?;count+=1;
        }
    }
    Ok(count)
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Advisor {
    model: String,
    model_size_gb: f64,
    detected_family: String,
    training_mode: String,
    context: u32,
    batch: u32,
    ubatch: u32,
    rank: u32,
    alpha: u32,
    modules: String,
    gpu_layers: String,
    reasons: Vec<String>,
    warnings: Vec<String>,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct EvalTest {
    name: String,
    persona: String,
    prompt: String,
    must_contain: Vec<String>,
    must_not_contain: Vec<String>,
    min_chars: usize,
    max_chars: usize,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct EvalResult {
    name: String,
    response: String,
    passed: bool,
    score: u32,
    reasons: Vec<String>,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct ProjectEvaluation {
    project_id: String,
    passed: usize,
    failed: usize,
    average_score: u32,
    results: Vec<EvalResult>,
}

#[derive(Clone, serde::Serialize)]
struct Document {
    name: String,
    size_bytes: u64,
    snippet: String,
}

struct AppState {
    model: RwLock<Option<Model>>,
    adapter: RwLock<Option<PathBuf>>,
    config: RwLock<Config>,
    child: Mutex<Option<CommandChild>>,
    training_child: Mutex<Option<CommandChild>>,
    training_python_pid: Mutex<Option<u32>>,
    training_running: Mutex<bool>,
    dir: PathBuf,
    docs_path: PathBuf,
    model_state_path: PathBuf,
    docs: RwLock<Vec<(String, String)>>,
    projects_dir: PathBuf,
}

fn model_size_bytes(path: &Path) -> Result<u64> {
    if path.is_file() { return Ok(fs::metadata(path)?.len()); }
    let mut total=0u64;
    for entry in fs::read_dir(path)? {
        let p=entry?.path();
        if p.is_dir() { total=total.saturating_add(model_size_bytes(&p)?); }
        else if p.is_file() { total=total.saturating_add(fs::metadata(p)?.len()); }
    }
    Ok(total)
}

fn hf_metadata(path: &Path) -> Result<(String,String)> {
    let cfg_path=path.join("config.json");
    let cfg: serde_json::Value=serde_json::from_slice(&fs::read(cfg_path)?)?;
    let family=cfg["model_type"].as_str().unwrap_or("Transformers").to_string();
    let architecture=cfg["architectures"].as_array()
        .and_then(|a|a.first()).and_then(|v|v.as_str()).unwrap_or("unknown").to_string();
    Ok((family,architecture))
}

fn model_from_path(path: &Path) -> Result<Model> {
    let id=path.file_stem().or_else(||path.file_name()).and_then(|x|x.to_str()).unwrap_or("model").to_string();
    if path.is_file() {
        if path.extension().and_then(|x|x.to_str()).map(|x|x.eq_ignore_ascii_case("gguf")) != Some(true) {
            return Err(anyhow!("Fichier modèle non pris en charge. Utilisez GGUF ou un dossier Transformers."));
        }
        let mut f=fs::File::open(path)?;
        let mut m=[0u8;4];
        f.read_exact(&mut m)?;
        if &m != b"GGUF" { return Err(anyhow!("Fichier GGUF invalide : signature absente.")); }
        let family=guess_family(&id);
        Ok(Model{id,path:path.to_string_lossy().into_owned(),size_bytes:fs::metadata(path)?.len(),
            format:"gguf".into(),family,architecture:"llama.cpp-compatible".into(),backend:"llama.cpp".into()})
    } else if path.is_dir() {
        if !path.join("config.json").is_file() { return Err(anyhow!("Dossier modèle invalide : config.json introuvable.")); }
        fn has_model_weights(p:&Path)->bool {
            if let Ok(entries)=fs::read_dir(p) {
                for e in entries.flatten() {
                    let q=e.path();
                    if q.is_file() && matches!(q.extension().and_then(|x|x.to_str()).unwrap_or("").to_lowercase().as_str(),
                        "safetensors"|"bin"|"pt"|"pth"|"ckpt") { return true; }
                    if q.is_dir() && has_model_weights(&q) { return true; }
                }
            }
            false
        }
        if !has_model_weights(path) { return Err(anyhow!("Dossier modèle invalide : aucun fichier de poids détecté.")); }
        let (family,architecture)=hf_metadata(path)?;
        Ok(Model{id,path:path.to_string_lossy().into_owned(),size_bytes:model_size_bytes(path)?,
            format:"transformers".into(),family,architecture,backend:"Transformers + PEFT".into()})
    } else {
        Err(anyhow!("Modèle introuvable."))
    }
}

fn models(dir: &Path) -> Result<Vec<Model>> {
    fs::create_dir_all(dir)?;
    let mut v=Vec::new();
    for e in fs::read_dir(dir)? {
        let p=e?.path();
        if let Ok(m)=model_from_path(&p) { v.push(m); }
    }
    v.sort_by(|a,b|a.id.cmp(&b.id));
    Ok(v)
}

fn copy_dir_all(src: &Path, dst: &Path) -> Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry=entry?;
        let from=entry.path();
        let to=dst.join(entry.file_name());
        if from.is_dir() { copy_dir_all(&from,&to)?; }
        else { fs::copy(&from,&to)?; }
    }
    Ok(())
}

fn valid(p: &Path) -> Result<()> {
    let _=model_from_path(p)?;
    Ok(())
}


fn load_docs(path: &Path) -> Vec<(String, String)> {
    fs::read_to_string(path).ok().and_then(|s| serde_json::from_str(&s).ok()).unwrap_or_default()
}

fn save_docs(path: &Path, docs: &[(String, String)]) -> Result<()> {
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, serde_json::to_vec(docs)?)?;
    if path.exists() { fs::remove_file(path)?; }
    fs::rename(tmp, path)?;
    Ok(())
}

fn load_model_id(path: &Path) -> Option<String> {
    fs::read_to_string(path).ok().map(|s| s.trim().to_string()).filter(|s| !s.is_empty())
}

fn save_model_id(path: &Path, id: &str) -> Result<()> {
    fs::write(path, id.as_bytes())?;
    Ok(())
}

fn now_iso() -> String {
    chrono_now()
}

fn chrono_now() -> String {
    // UTC timestamp without bringing a full datetime dependency into the engine.
    let output = Command::new("powershell")
        .args(["-NoProfile", "-Command", "(Get-Date).ToUniversalTime().ToString('o')"])
        .output();
    if let Ok(o) = output {
        let s = String::from_utf8_lossy(&o.stdout).trim().to_string();
        if !s.is_empty() { return s; }
    }
    "unknown".into()
}

fn extract_doc(path: &Path) -> Result<String> {
    let ext = path.extension().and_then(|x| x.to_str()).unwrap_or("").to_lowercase();
    match ext.as_str() {
        "txt" | "md" | "markdown" | "json" | "csv" => Ok(fs::read_to_string(path)?),
        "pdf" => Ok(pdf_extract::extract_text(path).map_err(|e| anyhow!("PDF : {e}"))?),
        "docx" => {
            let f = fs::File::open(path)?;
            let mut z = zip::ZipArchive::new(f)?;
            let mut s = String::new();
            let mut x = z.by_name("word/document.xml")?;
            x.read_to_string(&mut s)?;
            let mut out = String::new();
            let mut in_tag = false;
            for c in s.chars() {
                if c == '<' { in_tag = true; if !out.ends_with(' ') { out.push(' '); } }
                else if c == '>' { in_tag = false; }
                else if !in_tag { out.push(c); }
            }
            Ok(out.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))
        }
        _ => Err(anyhow!("Format non pris en charge. Utilisez TXT, Markdown, JSON, CSV, PDF ou DOCX.")),
    }
}

async fn vulkan_available(app: &tauri::AppHandle) -> bool {
    let out = match app.shell().sidecar("llama-server-vulkan") {
        Ok(c) => match c.args(["--list-devices"]).output().await {
            Ok(o) => String::from_utf8_lossy(&o.stdout).to_string() + &String::from_utf8_lossy(&o.stderr),
            Err(_) => return false,
        },
        Err(_) => return false,
    };
    let low = out.to_lowercase();
    low.contains("vulkan") && !low.contains("no devices") && !low.contains("failed to initialize")
}

async fn start(app:&tauri::AppHandle,s:&AppState)->Result<String>{
    if let Some(c)=s.child.lock().await.take(){let _=c.kill();}
    let m=s.model.read().await.clone().ok_or_else(||anyhow!("Aucun modèle sélectionné."))?;
    if m.format!="gguf" { return Ok("Modèle Transformers sélectionné · moteur local Python utilisé pour l'inférence et l'entraînement.".into()); }
    let cfg=s.config.read().await.clone();
    let adapter=s.adapter.read().await.clone();
    let use_gpu=match cfg.gpu_mode.as_str(){ "cpu"=>false, "gpu"=>true, _=>vulkan_available(app).await };
    let bin=if use_gpu{"llama-server-vulkan"}else{"llama-server-cpu"};
    let mut args=vec![
        "--model".into(),m.path.clone(),"--alias".into(),m.id.clone(),"--host".into(),"127.0.0.1".into(),
        "--port".into(),"18280".into(),"--ctx-size".into(),cfg.context_size.to_string(),"--n-gpu-layers".into(),
        if use_gpu {if cfg.gpu_layers=="auto"{"999".into()}else{cfg.gpu_layers.clone()}} else {"0".into()},
        "--jinja".into()
    ];
    if let Some(a)=adapter{args.push("--lora".into());args.push(a.to_string_lossy().into_owned());}
    if cfg.threads>0{args.extend(["--threads".into(),cfg.threads.to_string()]);}
    let (_events,child)=app.shell().sidecar(bin)?.args(args).spawn()?;
    *s.child.lock().await=Some(child);
    let client=reqwest::Client::new();
    for _ in 0..160{
        if client.get("http://127.0.0.1:18280/health").send().await.map(|r|r.status().is_success()).unwrap_or(false){
            let msg=if use_gpu{"Moteur local : GPU Vulkan".to_string()}else{"Moteur local : CPU".to_string()};
            let _=app.emit("chat://chunk",serde_json::json!({"engine":msg}));return Ok(msg);
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
    Err(anyhow!("Le moteur local n'a pas démarré. Vérifiez le modèle, l'adaptateur et la mémoire."))
}

fn python_runner()->Result<(String,Vec<String>)>{
    let candidates=if cfg!(target_os="windows"){
        vec![("python".to_string(),vec![]),("py".to_string(),vec!["-3".into()])]
    } else { vec![("python3".to_string(),vec![]),("python".to_string(),vec![])] };
    for (program,prefix) in candidates{
        let mut cmd=Command::new(&program);
        let mut args=prefix.clone();args.push("--version".into());
        if cmd.args(args).stdout(Stdio::null()).stderr(Stdio::null()).status().is_ok(){return Ok((program,prefix));}
    }
    Err(anyhow!("Python 3 est requis pour les modèles Transformers. Installez Python puis réessayez."))
}

fn resource_script(app:&tauri::AppHandle,name:&str)->Result<PathBuf>{
    let p=app.path().resource_dir()?.join("universal_engine").join(name);
    if !p.is_file(){return Err(anyhow!("Ressource Vanelle manquante: {}",p.display()));}
    Ok(p)
}

async fn run_python(app:&tauri::AppHandle,script:&str,args:&[String])->Result<std::process::Output>{
    let (program,prefix)=python_runner()?;
    let script_path=resource_script(app,script)?;
    let mut cmd=TokioCommand::new(program);
    cmd.args(prefix).arg(script_path).args(args);
    cmd.output().await.map_err(|e|anyhow!("Impossible de lancer Python: {e}"))
}


fn projects_file(dir: &Path, id: &str) -> PathBuf { dir.join(format!("{id}.json")) }

fn load_projects(dir: &Path) -> Vec<Project> {
    let mut out = Vec::new();
    if fs::create_dir_all(dir).is_err() { return out; }
    if let Ok(entries) = fs::read_dir(dir) {
        for e in entries.flatten() {
            let p = e.path();
            if p.extension().and_then(|x| x.to_str()) != Some("json") { continue; }
            if let Ok(v) = fs::read_to_string(&p).ok().and_then(|s| serde_json::from_str::<Project>(&s).ok()).ok_or(()) {
                out.push(v);
            }
        }
    }
    out.sort_by(|a, b| b.updated_at.cmp(&a.updated_at));
    out
}

fn save_project(dir: &Path, p: &Project) -> Result<()> {
    fs::create_dir_all(dir)?;
    fs::write(projects_file(dir, &p.id), serde_json::to_vec_pretty(p)?)?;
    Ok(())
}

fn load_project(dir: &Path, id: &str) -> Result<Project> {
    let p = projects_file(dir, id);
    let text = fs::read_to_string(p).map_err(|e| anyhow!("Projet introuvable : {e}"))?;
    Ok(serde_json::from_str(&text)?)
}

fn parse_dataset_line(v: &serde_json::Value) -> Option<(Option<String>, Option<String>, String)> {
    if let Some(arr) = v.get("messages").and_then(|x| x.as_array()) {
        let mut user = None;
        let mut assistant = None;
        for m in arr {
            let role = m.get("role").and_then(|x| x.as_str()).unwrap_or("");
            let c = m.get("content").and_then(|x| x.as_str()).unwrap_or("").trim().to_string();
            if role == "user" && !c.is_empty() && user.is_none() { user = Some(c); }
            else if role == "assistant" && !c.is_empty() { assistant = Some(c); }
        }
        let text = arr.iter().filter_map(|m| m.get("content").and_then(|x| x.as_str())).collect::<Vec<_>>().join("\n");
        if !text.trim().is_empty() { return Some((user, assistant, text)); }
    }
    let input = ["instruction", "prompt", "question", "input", "user"].iter()
        .find_map(|k| v.get(*k).and_then(|x| x.as_str()).map(|s| s.trim().to_string()));
    let output = ["output", "response", "answer", "assistant"].iter()
        .find_map(|k| v.get(*k).and_then(|x| x.as_str()).map(|s| s.trim().to_string()));
    let text = v.get("text").and_then(|x| x.as_str()).map(|s| s.trim().to_string())
        .or_else(|| Some(v.to_string()));
    text.filter(|s| !s.is_empty()).map(|t| (input, output, t))
}

fn prepare_dataset(path: &Path, output: &Path) -> Result<DatasetInfo> {
    let bytes = fs::read(path)?;
    let bytes_len = bytes.len() as u64;
    let ext = path.extension().and_then(|x| x.to_str()).unwrap_or("").to_lowercase();
    let mut records: Vec<serde_json::Value> = Vec::new();
    let mut invalid = 0usize;

    if ext == "jsonl" || ext == "ndjson" {
        for line in String::from_utf8_lossy(&bytes).lines() {
            if line.trim().is_empty() { continue; }
            match serde_json::from_str::<serde_json::Value>(line) {
                Ok(v) => { if let Some((u,a,t)) = parse_dataset_line(&v) {
                    if u.is_some() && a.is_some() {
                        records.push(serde_json::json!({"messages":[{"role":"user","content":u.unwrap()},{"role":"assistant","content":a.unwrap()}]}));
                    } else { records.push(serde_json::json!({"text":t})); }
                }},
                Err(_) => invalid += 1,
            }
        }
    } else if ext == "json" {
        let value: serde_json::Value = serde_json::from_slice(&bytes)?;
        let arr = value.as_array().cloned().unwrap_or_else(|| vec![value]);
        for v in arr {
            if let Some((u,a,t)) = parse_dataset_line(&v) {
                if u.is_some() && a.is_some() {
                    records.push(serde_json::json!({"messages":[{"role":"user","content":u.unwrap()},{"role":"assistant","content":a.unwrap()}]}));
                } else { records.push(serde_json::json!({"text":t})); }
            } else { invalid += 1; }
        }
    } else if ext == "csv" {
        let mut rdr = csv::Reader::from_reader(bytes.as_slice());
        let headers = rdr.headers()?.clone();
        for row in rdr.records() {
            let row = row?;
            let find = |keys: &[&str]| -> Option<String> {
                keys.iter().find_map(|k| headers.iter().position(|h| h.eq_ignore_ascii_case(k)).and_then(|i| row.get(i)).map(|s| s.trim().to_string()).filter(|s| !s.is_empty()))
            };
            let u = find(&["instruction","prompt","question","input","user"]);
            let a = find(&["output","response","answer","assistant"]);
            let text = if let Some(ref x) = u {
                format!("{}\n{}", x, a.clone().unwrap_or_default()).trim().to_string()
            } else {
                row.iter().filter(|x| !x.trim().is_empty()).collect::<Vec<_>>().join("\n")
            };
            if text.is_empty() { invalid += 1; } else if u.is_some() && a.is_some() {
                records.push(serde_json::json!({"messages":[{"role":"user","content":u.unwrap()},{"role":"assistant","content":a.unwrap()}]}));
            } else { records.push(serde_json::json!({"text":text})); }
        }
    } else {
        let text = String::from_utf8_lossy(&bytes).to_string();
        for paragraph in text.split("\n\n").map(str::trim).filter(|x| !x.is_empty()) {
            records.push(serde_json::json!({"text": paragraph}));
        }
    }

    if records.is_empty() { return Err(anyhow!("Aucun exemple exploitable trouvé dans le dataset.")); }
    let mut file = String::new();
    for r in &records { file.push_str(&serde_json::to_string(r)?); file.push('\n'); }
    fs::write(output, file)?;
    let chat_examples = records.iter().filter(|v| v.get("messages").is_some()).count();
    Ok(DatasetInfo {
        project_id: output.parent().and_then(|p| p.file_name()).and_then(|x| x.to_str()).unwrap_or("").into(),
        path: output.to_string_lossy().into_owned(),
        examples: records.len(),
        chat_examples,
        text_examples: records.len().saturating_sub(chat_examples),
        invalid_lines: invalid,
        bytes: bytes_len,
    })
}

fn guess_family(id: &str) -> String {
    let x = id.to_lowercase();
    if x.contains("qwen") { "Qwen".into() }
    else if x.contains("gemma") { "Gemma".into() }
    else if x.contains("llama") { "Llama".into() }
    else if x.contains("mistral") { "Mistral".into() }
    else if x.contains("phi") { "Phi".into() }
    else { "Architecture non déterminée par le nom du fichier".into() }
}

async fn advisor_for(app: &tauri::AppHandle, s: &AppState, model_id: &str, objective: &str) -> Result<Advisor> {
    let m = models(&s.dir)?.into_iter().find(|x| x.id == model_id).ok_or_else(|| anyhow!("Modèle introuvable"))?;
    let model_id_owned = m.id.clone();
    let detected_family = guess_family(&model_id_owned);
    let size = m.size_bytes as f64 / 1073741824.0;
    let gpu = vulkan_available(app).await;
    let (context, batch, rank, modules) = if size >= 12.0 {
        (256, 1, 8, "attn_q,attn_k,attn_v,attn_o")
    } else if size >= 6.0 {
        (384, 1, 8, "attn_q,attn_k,attn_v,attn_o,ffn_gate,ffn_up,ffn_down")
    } else if size >= 2.0 {
        (512, 2, 16, "attn_q,attn_k,attn_v,attn_o,ffn_gate,ffn_up,ffn_down")
    } else {
        (512, 4, 16, "attn_q,attn_k,attn_v,attn_o")
    };
    let mut reasons = vec![
        format!("Taille réelle du fichier : {:.2} Go.", size),
        format!("Famille détectée : {}.", detected_family),
        format!("Objectif fourni : {}.", objective.trim()),
        if gpu { "Vulkan est disponible sur cette machine ; Vanelle peut proposer l'offload GPU.".into() }
        else { "Aucun GPU Vulkan détecté ; Vanelle propose le CPU pour rester exécutable localement.".into() },
    ];
    if objective.to_lowercase().contains("image") || objective.to_lowercase().contains("vision") {
        reasons.push("Objectif multimodal détecté : un modèle textuel GGUF seul ne suffit pas ; un modèle vision-compatible devra être importé.".into());
    }
    let mut warnings = Vec::new();
    if size > 10.0 { warnings.push("Ce modèle est volumineux : l'entraînement LoRA peut nécessiter beaucoup de RAM/VRAM.".into()); }
    if size > 20.0 { warnings.push("Le modèle est très volumineux pour une machine personnelle ; utilisez un contexte et un rank faibles au départ.".into()); }
    warnings.push("L'adaptation LoRA est recommandée pour conserver le modèle de base intact et limiter les ressources d'entraînement.".into());
    Ok(Advisor {
        model: model_id_owned,
        model_size_gb: size,
        detected_family,
        training_mode: "LoRA / SFT".into(),
        context,
        batch,
        ubatch: batch,
        rank,
        alpha: rank * 2,
        modules: modules.into(),
        gpu_layers: if gpu { "999".into() } else { "0".into() },
        reasons: std::mem::take(&mut reasons),
        warnings,
    })
}

async fn chat_once(messages: Vec<Msg>, config: Config) -> Result<String> {
    let c = reqwest::Client::new();
    let body = serde_json::json!({
        "model":"vanelle",
        "messages":messages,
        "temperature":config.temperature,
        "max_tokens":config.max_tokens,
        "stream":false
    });
    let r = c.post("http://127.0.0.1:18280/v1/chat/completions").json(&body).send().await?.error_for_status()?;
    let v: serde_json::Value = r.json().await?;
    Ok(v["choices"][0]["message"]["content"].as_str().unwrap_or("").to_string())
}

#[tauri::command]
async fn list_models(s: State<'_, Arc<AppState>>) -> Result<Vec<Model>, String> { models(&s.dir).map_err(|e| e.to_string()) }

#[tauri::command]
async fn current_model(s: State<'_, Arc<AppState>>) -> Result<String, String> { Ok(s.model.read().await.as_ref().map(|m| m.id.clone()).unwrap_or_default()) }

#[tauri::command]
async fn current_adapter(s: State<'_, Arc<AppState>>) -> Result<String, String> { Ok(s.adapter.read().await.as_ref().map(|p| p.to_string_lossy().into_owned()).unwrap_or_default()) }

#[tauri::command]
async fn hardware_info(app: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let cpu = std::thread::available_parallelism().map(|x| x.get()).unwrap_or(1);
    #[cfg(target_os="windows")]
    let ps = Command::new("powershell").args(["-NoProfile","-Command","$g=Get-CimInstance Win32_VideoController | Where-Object {$_.Name}; $names=($g|ForEach-Object {$_.Name}) -join ' | '; $v=($g|ForEach-Object {[uint64]$_.AdapterRAM}|Measure-Object -Maximum).Maximum; $m=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; [pscustomobject]@{gpu=$names;vram=$v;ram=$m}|ConvertTo-Json -Compress"]).output();
    #[cfg(not(target_os="windows"))]
    let ps: Result<std::process::Output,std::io::Error> = Err(std::io::Error::new(std::io::ErrorKind::Other,"not windows"));
    let (gpu,ram,vram)=match ps {
        Ok(o)=>match serde_json::from_slice::<serde_json::Value>(&o.stdout) {
            Ok(v)=>(
                v["gpu"].as_str().unwrap_or("GPU non détecté").to_string(),
                v["ram"].as_u64().map(|x|format!("{:.1} Go",x as f64/1073741824.0)).unwrap_or_else(||"RAM non détectée".into()),
                v["vram"].as_u64().map(|x|format!("{:.1} Go",x as f64/1073741824.0)).unwrap_or_else(||"VRAM non détectée".into())
            ),
            Err(_)=>("GPU non détecté".into(),"RAM non détectée".into(),"VRAM non détectée".into())
        },
        Err(_)=>("GPU non détecté".into(),"RAM non détectée".into(),"VRAM non détectée".into())
    };
    let vk=if vulkan_available(&app).await{"Vulkan disponible"}else{"Vulkan non disponible"};
    Ok(serde_json::json!({"cpu":format!("{} threads CPU disponibles",cpu),"ram":ram,"gpu":gpu,"vram":vram,"vulkan":vk}))
}

#[tauri::command]
async fn import_model(s: State<'_,Arc<AppState>>, path:String)->Result<Model,String>{
    let p=Path::new(&path);
    let src=model_from_path(p).map_err(|e|e.to_string())?;
    fs::create_dir_all(&s.dir).map_err(|e|e.to_string())?;
    let name=p.file_name().ok_or("Nom invalide").map_err(String::from)?;
    let d=s.dir.join(name);
    if d.exists(){return Err("Un modèle portant ce nom existe déjà.".into());}
    if p.is_dir(){copy_dir_all(p,&d).map_err(|e|e.to_string())?;} else {fs::copy(p,&d).map_err(|e|e.to_string())?;}
    let imported=model_from_path(&d).map_err(|e|e.to_string())?;
    if imported.id!=src.id {return Err("Identifiant de modèle incohérent après import.".into());}
    Ok(imported)
}

#[tauri::command]
async fn remove_model(s:State<'_,Arc<AppState>>,id:String)->Result<(),String>{
    let m=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==id).ok_or("Modèle introuvable")?;
    let p=Path::new(&m.path);
    if p.is_dir(){fs::remove_dir_all(p).map_err(|e|e.to_string())?;}else{fs::remove_file(p).map_err(|e|e.to_string())?;}
    if load_model_id(&s.model_state_path).as_deref()==Some(id.as_str()){let _=fs::remove_file(&s.model_state_path);}
    Ok(())
}

#[tauri::command]
async fn set_model(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,id:String)->Result<(),String>{
    let m=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==id).ok_or("Modèle introuvable")?;
    save_model_id(&s.model_state_path,&m.id).map_err(|e|e.to_string())?;
    *s.model.write().await=Some(m.clone());
    *s.adapter.write().await=None;
    if m.format=="gguf" {
        start(&app,&s).await.map_err(|e|e.to_string()).map(|_|())
    } else {
        if let Some(c)=s.child.lock().await.take(){let _=c.kill();}
        Ok(())
    }
}

#[tauri::command]
async fn set_active_adapter(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,path:String)->Result<(),String>{
    let p=PathBuf::from(&path);
    if !p.is_file(){return Err("Adaptateur introuvable".into());}
    *s.adapter.write().await=Some(p);
    start(&app,&s).await.map_err(|e|e.to_string()).map(|_|())
}

#[tauri::command]
async fn activate_project_adapter(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String)->Result<(),String>{
    let p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    let model=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==p.model_id).ok_or("Modèle introuvable.")?;
    match (model.format.as_str(),p.adapter_path){
        ("transformers",Some(path))=>{
            let adapter=PathBuf::from(path);
            if !adapter.is_dir(){return Err("Adaptateur Transformers introuvable.".into());}
            *s.adapter.write().await=Some(adapter);
            if let Some(child)=s.child.lock().await.take(){let _=child.kill();}
            Ok(())
        },
        ("transformers",None)=>{
            *s.adapter.write().await=None;
            if let Some(child)=s.child.lock().await.take(){let _=child.kill();}
            Ok(())
        },
        ("gguf",Some(path))=>set_active_adapter(app,s,path).await,
        ("gguf",None)=>{
            *s.adapter.write().await=None;
            start(&app,&s).await.map_err(|e|e.to_string()).map(|_|())
        },
        _=>Err("Backend de modèle non pris en charge.".into())
    }
}

#[tauri::command]
async fn stop_engine(s:State<'_,Arc<AppState>>)->Result<(),String>{if let Some(c)=s.child.lock().await.take(){let _=c.kill();}Ok(())}

#[tauri::command]
async fn import_document(s:State<'_,Arc<AppState>>,path:String)->Result<Document,String>{
    let p=Path::new(&path);
    let md=fs::metadata(p).map_err(|e|e.to_string())?;
    if md.len()>100*1024*1024{return Err("Document trop volumineux (limite 100 Mo).".into());}
    let text=extract_doc(p).map_err(|e|e.to_string())?;
    let name=p.file_name().and_then(|x|x.to_str()).unwrap_or("document").to_string();
    let snippet=text.chars().take(500).collect::<String>();
    {let mut docs=s.docs.write().await;docs.retain(|(n,_)|n!=&name);docs.push((name.clone(),text.clone()));save_docs(&s.docs_path,&docs).map_err(|e|e.to_string())?;}
    Ok(Document{name,size_bytes:md.len(),snippet})
}

#[tauri::command]
async fn list_documents(s:State<'_,Arc<AppState>>)->Result<Vec<Document>,String>{let docs=s.docs.read().await;Ok(docs.iter().map(|(n,t)|Document{name:n.clone(),size_bytes:t.len() as u64,snippet:t.chars().take(500).collect()}).collect())}

#[tauri::command]
async fn remove_document(s:State<'_,Arc<AppState>>,name:String)->Result<(),String>{let mut docs=s.docs.write().await;let before=docs.len();docs.retain(|(n,_)|n!=&name);if docs.len()==before{return Err("Document introuvable".into())}save_docs(&s.docs_path,&docs).map_err(|e|e.to_string())?;Ok(())}

#[tauri::command]
async fn search_documents(s:State<'_,Arc<AppState>>,query:String,limit:usize)->Result<Vec<Document>,String>{
    let q=query.to_lowercase();let terms=q.split_whitespace().filter(|x|x.len()>2).collect::<Vec<_>>();
    let mut scored=s.docs.read().await.iter().cloned().map(|(n,t)|{let low=t.to_lowercase();let score=terms.iter().map(|x|low.matches(x).count()).sum::<usize>();(score,n,t)}).filter(|x|x.0>0).collect::<Vec<_>>();
    scored.sort_by(|a,b|b.0.cmp(&a.0));
    Ok(scored.into_iter().take(limit.max(1)).map(|(_,n,t)|{let low=t.to_lowercase();let pos=terms.first().and_then(|x|low.find(x)).unwrap_or(0);let start=pos.saturating_sub(180);let sn=t.chars().skip(start).take(900).collect::<String>();Document{name:n.clone(),size_bytes:t.len() as u64,snippet:sn}}).collect())
}

#[tauri::command]
async fn chat(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,messages:Vec<Msg>,config:Config)->Result<(),String>{
    *s.config.write().await=config.clone();
    let model=s.model.read().await.clone().ok_or("Aucun modèle local sélectionné.")?;
    if model.format=="transformers"{
        let dir=s.projects_dir.join("_runtime");fs::create_dir_all(&dir).map_err(|e|e.to_string())?;
        let msg_file=dir.join(format!("chat-{}.json",uuid_like()));
        fs::write(&msg_file,serde_json::to_vec(&messages).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
        let adapter=s.adapter.read().await.clone().map(|p|p.to_string_lossy().into_owned()).unwrap_or_default();
        let args=vec![
            "--model".into(),model.path.clone(),
            "--adapter".into(),adapter,
            "--messages".into(),msg_file.to_string_lossy().into_owned(),
            "--max-new-tokens".into(),config.max_tokens.to_string()
        ];
        let out=run_python(&app,"hf_chat.py",&args).await.map_err(|e|e.to_string())?;
        let _=fs::remove_file(&msg_file);
        if !out.status.success(){return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());}
        let answer=String::from_utf8_lossy(&out.stdout).trim().to_string();
        if answer.is_empty(){return Err("Le modèle Transformers n'a produit aucune réponse.".into());}
        app.emit("chat://chunk",serde_json::json!({"delta":answer,"engine":"Inference Transformers / PEFT"})).map_err(|e|e.to_string())?;
        app.emit("chat://chunk",serde_json::json!({"done":true})).map_err(|e|e.to_string())?;
        return Ok(());
    }
    let cc=reqwest::Client::new();
    if !cc.get("http://127.0.0.1:18280/health").send().await.map(|r|r.status().is_success()).unwrap_or(false){start(&app,&s).await.map_err(|e|e.to_string())?;}
    let model_id=model.id.clone();
    let body=serde_json::json!({"model":model_id,"messages":messages,"temperature":config.temperature,"max_tokens":config.max_tokens,"stream":true});
    let r=cc.post("http://127.0.0.1:18280/v1/chat/completions").json(&body).send().await.map_err(|e|e.to_string())?.error_for_status().map_err(|e|e.to_string())?;
    let mut st=r.bytes_stream();let mut buf=String::new();
    while let Some(chunk)=st.next().await{
        buf.push_str(&String::from_utf8_lossy(&chunk.map_err(|e|e.to_string())?));
        while let Some(i)=buf.find("\n\n"){
            let frame=buf[..i].to_string();buf.drain(..i+2);
            for line in frame.lines(){if !line.starts_with("data:"){continue}let p=line.trim_start_matches("data:").trim();if p=="[DONE]"{continue}
                if let Ok(v)=serde_json::from_str::<serde_json::Value>(p){if let Some(d)=v["choices"][0]["delta"]["content"].as_str(){if !d.is_empty(){app.emit("chat://chunk",serde_json::json!({"delta":d})).map_err(|e|e.to_string())?;}}}
            }
        }
    }
    app.emit("chat://chunk",serde_json::json!({"done":true})).map_err(|e|e.to_string())?;Ok(())
}

#[tauri::command]
async fn list_projects(s:State<'_,Arc<AppState>>)->Result<Vec<Project>,String>{Ok(load_projects(&s.projects_dir))}

#[tauri::command]
async fn create_project(s:State<'_,Arc<AppState>>,name:String,objective:String,model_id:String)->Result<Project,String>{
    if name.trim().is_empty() || objective.trim().is_empty(){return Err("Nom et objectif obligatoires.".into());}
    let id=format!("project-{}",uuid_like());
    let now=now_iso();
    let p=Project{id:id.clone(),name:name.trim().into(),objective:objective.trim().into(),model_id,dataset_path:None,adapter_path:None,merged_model_path:None,status:"Brouillon".into(),created_at:now.clone(),updated_at:now,examples:0};
    save_project(&s.projects_dir,&p).map_err(|e|e.to_string())?;
    Ok(p)
}

fn uuid_like()->String{format!("{}-{}",std::process::id(),now_iso().replace(|c:char|!c.is_ascii_alphanumeric(),"" ).chars().rev().take(10).collect::<String>().chars().rev().collect::<String>())}

#[tauri::command]
async fn import_project_dataset(s:State<'_,Arc<AppState>>,project_id:String,path:String)->Result<DatasetInfo,String>{
    let p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    let src=Path::new(&path);
    if !src.is_file(){return Err("Dataset introuvable".into());}
    let dir=s.projects_dir.join(&project_id);fs::create_dir_all(&dir).map_err(|e|e.to_string())?;
    let output=dir.join("dataset.jsonl");
    let mut info=prepare_dataset(src,&output).map_err(|e|e.to_string())?;
    info.project_id=project_id.clone();
    let mut p2=p;
    p2.dataset_path=Some(output.to_string_lossy().into_owned());
    p2.examples=info.examples;
    p2.status="Dataset prêt".into();
    p2.updated_at=now_iso();
    save_project(&s.projects_dir,&p2).map_err(|e|e.to_string())?;
    Ok(info)
}

#[tauri::command]
async fn model_advisor(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String)->Result<Advisor,String>{
    let p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    advisor_for(&app,&s,&p.model_id,&p.objective).await.map_err(|e|e.to_string())
}

#[tauri::command]
async fn model_inspection(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,model_id:String)->Result<serde_json::Value,String>{
    let m=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|x|x.id==model_id).ok_or("Modèle introuvable")?;
    if m.format=="transformers"{
        let cfg_path=Path::new(&m.path).join("config.json");
        let cfg:serde_json::Value=serde_json::from_slice(&fs::read(cfg_path).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
        return Ok(serde_json::json!({
            "id":m.id,"path":m.path,"size_bytes":m.size_bytes,"format":m.format,
            "family":m.family,"architecture":m.architecture,"backend":m.backend,
            "model_type":cfg["model_type"],"torch_dtype":cfg["torch_dtype"],
            "architectures":cfg["architectures"],"chat_template":Path::new(&m.path).join("tokenizer_config.json").is_file()
        }));
    }
    let port="18283";
    let bin=if vulkan_available(&app).await{"llama-server-vulkan"}else{"llama-server-cpu"};
    let cmd=app.shell().sidecar(bin).map_err(|e|e.to_string())?.args(["--model",m.path.as_str(),"--host","127.0.0.1","--port",port,"--ctx-size","256","--n-gpu-layers","0"]);
    let (mut rx,child)=cmd.spawn().map_err(|e|e.to_string())?;
    let client=reqwest::Client::new();let mut result=None;
    for _ in 0..120{
        if let Ok(resp)=client.get("http://127.0.0.1:18283/props").send().await{if resp.status().is_success(){result=resp.json::<serde_json::Value>().await.ok();break;}}
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
    let _=child.kill();while let Ok(Some(event))=tokio::time::timeout(Duration::from_millis(30),rx.recv()).await{if matches!(event,CommandEvent::Terminated(_)){break;}}
    let props=result.unwrap_or_else(||serde_json::json!({}));
    Ok(serde_json::json!({"id":m.id,"path":m.path,"size_bytes":m.size_bytes,"format":m.format,"family":m.family,
        "architecture":m.architecture,"backend":m.backend,"model_path":props["model_path"],
        "chat_template":props["chat_template"],"modalities":props["modalities"],"model_ftype":props["model_ftype"]}))
}



#[tauri::command]
async fn vision_info(s:State<'_,Arc<AppState>>,project_id:String)->Result<VisionInfo,String>{Ok(load_vision_info(&s.projects_dir,&project_id))}

#[tauri::command]
async fn import_vision_dataset(s:State<'_,Arc<AppState>>,project_id:String,path:String)->Result<VisionInfo,String>{
    let p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    if !Path::new(&path).is_dir(){return Err("Sélectionnez un dossier contenant un dossier par classe.".into());}
    let src=Path::new(&path);
    let classes=fs::read_dir(src).map_err(|e|e.to_string())?.flatten().filter(|e|e.path().is_dir()).map(|e|e.file_name().to_string_lossy().into_owned()).collect::<Vec<_>>();
    if classes.len()<2{return Err("Le dataset vision doit contenir au moins deux classes, chacune dans son propre dossier.".into());}
    let total=classes.iter().map(|c|image_count(&src.join(c))).sum::<usize>();
    if total<10{return Err(format!("Dataset trop petit : {total} images. Ajoutez davantage d'images avant l'entraînement."));}
    let dir=s.projects_dir.join(&project_id);fs::create_dir_all(&dir).map_err(|e|e.to_string())?;
    let target=dir.join("vision_dataset");if target.exists(){fs::remove_dir_all(&target).map_err(|e|e.to_string())?;}fs::create_dir_all(&target).map_err(|e|e.to_string())?;
    for class in &classes{copy_images_only(&src.join(class),&target.join(class)).map_err(|e|e.to_string())?;}
    let v=VisionInfo{project_id:project_id.clone(),dataset_path:Some(target.to_string_lossy().into_owned()),classes:classes.clone(),images:total,checkpoint_path:None,best_accuracy:None,status:"Dataset vision prêt".into()};
    save_vision_info(&s.projects_dir,&v).map_err(|e|e.to_string())?;
    let mut p2=p;p2.status=format!("Dataset vision prêt · {total} images · {} classes",classes.len());p2.updated_at=now_iso();save_project(&s.projects_dir,&p2).map_err(|e|e.to_string())?;
    Ok(v)
}

#[tauri::command]
async fn start_vision_training(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String)->Result<(),String>{
    if *s.training_running.lock().await{return Err("Un entraînement est déjà en cours.".into());}
    let mut v=load_vision_info(&s.projects_dir,&project_id);let dataset=v.dataset_path.clone().ok_or("Importez d'abord un dataset vision.")?;
    if v.classes.len()<2||v.images<10{return Err("Dataset vision insuffisant pour commencer.".into());}
    let dir=s.projects_dir.join(&project_id);let output=dir.join("vision-training");if output.exists(){fs::remove_dir_all(&output).map_err(|e|e.to_string())?;}fs::create_dir_all(&output).map_err(|e|e.to_string())?;
    let args=vec!["--dataset".into(),dataset,"--output".into(),output.to_string_lossy().into_owned(),"--epochs".into(),"3".into(),"--batch-size".into(),"16".into()];
    let (program,prefix)=python_runner().map_err(|e|e.to_string())?;let script=resource_script(&app,"vision_train.py").map_err(|e|e.to_string())?;
    let mut child=TokioCommand::new(program);child.args(prefix).arg(script).args(args).stdout(Stdio::piped()).stderr(Stdio::piped());let mut child=child.spawn().map_err(|e|format!("Impossible de lancer l'entraînement vision : {e}"))?;
    let pid=child.id().ok_or("PID Python introuvable.")?;*s.training_python_pid.lock().await=Some(pid);*s.training_running.lock().await=true;
    v.status="Entraînement vision en cours".into();save_vision_info(&s.projects_dir,&v).map_err(|e|e.to_string())?;
    let handle=app.clone();let state=Arc::clone(&*s);let projects_dir=s.projects_dir.clone();let project_name=project_id.clone();let out_path=output.clone();
    let stdout=child.stdout.take();let stderr=child.stderr.take();
    let h1=handle.clone();let pr1=project_name.clone();tokio::spawn(async move{if let Some(out)=stdout{let mut lines=BufReader::new(out).lines();while let Ok(Some(line))=lines.next_line().await{let _=h1.emit("vision://log",serde_json::json!({"project_id":pr1,"line":line}));}}});
    let h2=handle.clone();let pr2=project_name.clone();tokio::spawn(async move{if let Some(out)=stderr{let mut lines=BufReader::new(out).lines();while let Ok(Some(line))=lines.next_line().await{let _=h2.emit("vision://log",serde_json::json!({"project_id":pr2,"line":line}));}}});
    tokio::spawn(async move{let code=child.wait().await.ok().and_then(|x|x.code()).unwrap_or(-1);let _=handle.emit("vision://done",serde_json::json!({"project_id":project_name,"code":code}));let mut vv=load_vision_info(&projects_dir,&project_name);if code==0&&out_path.join("best.pt").is_file(){
        vv.checkpoint_path=Some(out_path.join("best.pt").to_string_lossy().into_owned());vv.status="Entraînement vision terminé".into();if let Ok(t)=fs::read_to_string(out_path.join("training_summary.json")){if let Ok(j)=serde_json::from_str::<serde_json::Value>(&t){vv.best_accuracy=j.get("best_val_accuracy").and_then(|x|x.as_f64());}}
    }else{vv.status=format!("Entraînement vision échoué (code {code})");}let _=save_vision_info(&projects_dir,&vv);*state.training_running.lock().await=false;*state.training_python_pid.lock().await=None;});
    Ok(())
}

#[tauri::command]
async fn evaluate_vision_project(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String)->Result<serde_json::Value,String>{
    let v=load_vision_info(&s.projects_dir,&project_id);let dataset=v.dataset_path.clone().ok_or("Aucun dataset vision.")?;let checkpoint=v.checkpoint_path.clone().ok_or("Entraînez d'abord le modèle vision.")?;
    let out=s.projects_dir.join(&project_id).join("vision-evaluation.json");let args=vec!["--dataset".into(),dataset,"--checkpoint".into(),checkpoint,"--output".into(),out.to_string_lossy().into_owned()];
    let r=run_python(&app,"vision_eval.py",&args).await.map_err(|e|e.to_string())?;if !r.status.success(){return Err(String::from_utf8_lossy(&r.stderr).trim().to_string());}
    let val:serde_json::Value=serde_json::from_slice(&fs::read(&out).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;let mut vv=v;vv.best_accuracy=val.get("accuracy").and_then(|x|x.as_f64());vv.status="Évaluation vision terminée".into();save_vision_info(&s.projects_dir,&vv).map_err(|e|e.to_string())?;Ok(val)
}

#[tauri::command]
async fn predict_vision_image(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String,image_path:String)->Result<serde_json::Value,String>{
    let v=load_vision_info(&s.projects_dir,&project_id);let checkpoint=v.checkpoint_path.ok_or("Entraînez d'abord le modèle vision.")?;let img=Path::new(&image_path);if !img.is_file()||!is_image_file(img){return Err("Image introuvable ou format non supporté.".into());}
    let args=vec!["--checkpoint".into(),checkpoint,"--image".into(),image_path,"--top-k".into(),"5".into()];let r=run_python(&app,"vision_predict.py",&args).await.map_err(|e|e.to_string())?;if !r.status.success(){return Err(String::from_utf8_lossy(&r.stderr).trim().to_string());}
    serde_json::from_str::<serde_json::Value>(String::from_utf8_lossy(&r.stdout).trim()).map_err(|e|format!("Résultat vision invalide : {e}"))
}

#[tauri::command]
async fn vision_runtime_info(app:tauri::AppHandle)->Result<serde_json::Value,String>{
    let (program,prefix)=python_runner().map_err(|e|e.to_string())?;let code="import torch,PIL,torchvision; print('torch='+torch.__version__); print('torchvision='+torchvision.__version__); print('cuda='+str(torch.cuda.is_available()))";let mut args=prefix.clone();args.extend(["-c".into(),code.into()]);let out=TokioCommand::new(program).args(args).output().await.map_err(|e|e.to_string())?;
    if !out.status.success(){return Ok(serde_json::json!({"ready":false,"detail":String::from_utf8_lossy(&out.stderr)}));}Ok(serde_json::json!({"ready":true,"detail":String::from_utf8_lossy(&out.stdout).trim(),"scripts":resource_script(&app,"vision_train.py").is_ok()}))
}

#[tauri::command]
async fn start_training(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String)->Result<(),String>{
    if *s.training_running.lock().await{return Err("Un entraînement est déjà en cours.".into())}
    let mut p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    let dataset=p.dataset_path.clone().ok_or("Ajoutez un dataset avant l'entraînement.")?;
    let model=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==p.model_id).ok_or("Modèle du projet introuvable.")?;
    let dir=s.projects_dir.join(&project_id);fs::create_dir_all(&dir).map_err(|e|e.to_string())?;

    if model.format=="transformers"{
        let output=dir.join("transformers-training");
        if output.exists(){let _=fs::remove_dir_all(&output);}
        fs::create_dir_all(&output).map_err(|e|e.to_string())?;
        let args=vec![
            "--model".into(),model.path.clone(),"--dataset".into(),dataset.clone(),
            "--output".into(),output.to_string_lossy().into_owned(),"--objective".into(),p.objective.clone(),
            "--epochs".into(),"1".into(),"--batch-size".into(),"1".into()
        ];
        let (program,prefix)=python_runner().map_err(|e|e.to_string())?;
        let script=resource_script(&app,"hf_train.py").map_err(|e|e.to_string())?;
        let mut cmd=TokioCommand::new(program);
        cmd.args(prefix).arg(script).args(args).stdout(Stdio::piped()).stderr(Stdio::piped());
        let mut child=cmd.spawn().map_err(|e|format!("Impossible de lancer l'entraînement Transformers : {e}"))?;
        let pid=child.id().ok_or("PID Python introuvable.")?;
        *s.training_python_pid.lock().await=Some(pid);
        *s.training_running.lock().await=true;
        p.status="Entraînement Transformers en cours".into();
        p.updated_at=now_iso();
        save_project(&s.projects_dir,&p).map_err(|e|e.to_string())?;

        let handle=app.clone();
        let state=Arc::clone(&*s);
        let projects_dir=s.projects_dir.clone();
        let project_name=project_id.clone();
        let adapter_dir=output.join("adapter");
        let stdout=child.stdout.take();
        let stderr=child.stderr.take();

        let out_handle=handle.clone();
        let out_project=project_name.clone();
        tokio::spawn(async move{
            if let Some(out)=stdout{
                let mut lines=BufReader::new(out).lines();
                while let Ok(Some(line))=lines.next_line().await{
                    let _=out_handle.emit("training://log",serde_json::json!({"project_id":out_project,"line":line}));
                }
            }
        });

        let err_handle=handle.clone();
        let err_project=project_name.clone();
        tokio::spawn(async move{
            if let Some(out)=stderr{
                let mut lines=BufReader::new(out).lines();
                while let Ok(Some(line))=lines.next_line().await{
                    let _=err_handle.emit("training://log",serde_json::json!({"project_id":err_project,"line":line}));
                }
            }
        });

        tokio::spawn(async move{
            let status=child.wait().await;
            let code=status.ok().and_then(|x|x.code()).unwrap_or(-1);
            let _=handle.emit("training://done",serde_json::json!({"project_id":project_name,"code":code}));
            if let Ok(mut project)=load_project(&projects_dir,&project_name){
                if code==0 && adapter_dir.is_dir(){
                    project.adapter_path=Some(adapter_dir.to_string_lossy().into_owned());
                    project.status="Entraînement Transformers terminé".into();
                }else{
                    project.status=format!("Entraînement Transformers échoué (code {code})");
                }
                project.updated_at=now_iso();
                let _=save_project(&projects_dir,&project);
            }
            *state.training_running.lock().await=false;
            *state.training_python_pid.lock().await=None;
        });
        return Ok(());
    }

    let advisor=advisor_for(&app,&s,&p.model_id,&p.objective).await.map_err(|e|e.to_string())?;
    let output=dir.join("trained-adapter.gguf");
    let checkpoints=dir.join("checkpoints");
    fs::create_dir_all(&checkpoints).map_err(|e|e.to_string())?;
    let use_gpu=advisor.gpu_layers!="0";
    let mut args=vec!["-m".into(),model.path.clone(),"-f".into(),dataset,
        "--output-adapter".into(),output.to_string_lossy().into_owned(),
        "--lora-rank".into(),advisor.rank.to_string(),"--lora-alpha".into(),advisor.alpha.to_string(),
        "--lora-modules".into(),advisor.modules,"--learning-rate".into(),"1e-5".into(),
        "--lr-min".into(),"1e-8".into(),"--lr-scheduler".into(),"cosine".into(),
        "--warmup-ratio".into(),"0.1".into(),"--checkpoint-save-steps".into(),"50".into(),
        "--checkpoint-save-dir".into(),checkpoints.to_string_lossy().into_owned(),
        "--num-epochs".into(),"2".into(),"-c".into(),advisor.context.to_string(),
        "-b".into(),advisor.batch.to_string(),"-ub".into(),advisor.ubatch.to_string(),
        "-ngl".into(),if use_gpu{"999".into()}else{"0".into()},"-fa".into(),"off".into()];
    if p.examples>0{args.extend(["--lora-seed".into(),"42".into()]);}
    if let Some(dataset_path)=p.dataset_path.clone(){
        if let Ok(text)=fs::read_to_string(dataset_path){
            if text.lines().take(5).all(|l|l.contains("\"messages\"")){args.push("--assistant-loss-only".into());}
        }
    }
    if output.exists(){let _=fs::remove_file(&output);}
    let trainer=if use_gpu{"llama-finetune-lora-vulkan"}else{"llama-finetune-lora"};
    let (mut rx,child)=app.shell().sidecar(trainer).map_err(|e|e.to_string())?.args(args).spawn().map_err(|e|e.to_string())?;
    *s.training_child.lock().await=Some(child);*s.training_running.lock().await=true;
    p.status="Entraînement en cours".into();p.updated_at=now_iso();save_project(&s.projects_dir,&p).map_err(|e|e.to_string())?;
    let handle=app.clone();let state=Arc::clone(&*s);let projects_dir=s.projects_dir.clone();
    tokio::spawn(async move{
        while let Some(event)=rx.recv().await{
            match event{
                CommandEvent::Stdout(line)|CommandEvent::Stderr(line)=>{
                    let text=String::from_utf8_lossy(&line).replace("\n","");
                    let _=handle.emit("training://log",serde_json::json!({"project_id":project_id,"line":text}));
                },
                CommandEvent::Terminated(payload)=>{
                    let code=payload.code.unwrap_or(-1);
                    let _=handle.emit("training://done",serde_json::json!({"project_id":project_id,"code":code}));
                    if let Ok(mut project)=load_project(&projects_dir,&project_id){
                        if code==0&&output.is_file(){project.adapter_path=Some(output.to_string_lossy().into_owned());project.status="Entraînement terminé".into();}
                        else{project.status=format!("Entraînement échoué (code {code})");}
                        project.updated_at=now_iso();let _=save_project(&projects_dir,&project);
                    }
                    *state.training_running.lock().await=false;
                    *state.training_child.lock().await=None;
                    break;
                },_=>{}
            }
        }
    });
    Ok(())
}

#[tauri::command]
async fn stop_training(s:State<'_,Arc<AppState>>)->Result<(),String>{
    if let Some(c)=s.training_child.lock().await.take(){let _=c.kill();}
    if let Some(pid)=s.training_python_pid.lock().await.take(){
        #[cfg(target_os="windows")]
        { let _=Command::new("taskkill").args(["/PID",&pid.to_string(),"/T","/F"]).status(); }
        #[cfg(not(target_os="windows"))]
        { let _=Command::new("kill").args(["-TERM",&pid.to_string()]).status(); }
    }
    *s.training_running.lock().await=false;
    Ok(())
}

#[tauri::command]
async fn evaluate_project(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String,tests:Vec<EvalTest>)->Result<ProjectEvaluation,String>{
    let p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    if tests.is_empty(){return Err("Ajoutez au moins un scénario de test.".into())}
    let model=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==p.model_id).ok_or("Modèle introuvable.")?;
    if model.format=="transformers"{
        let dir=s.projects_dir.join(&project_id);fs::create_dir_all(&dir).map_err(|e|e.to_string())?;
        let tests_path=dir.join("evaluation_tests.json");
        let out_path=dir.join("evaluation.json");
        fs::write(&tests_path,serde_json::to_vec_pretty(&tests).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
        let adapter=p.adapter_path.clone().unwrap_or_default();
        if adapter.is_empty(){ *s.adapter.write().await=None; } else { *s.adapter.write().await=Some(PathBuf::from(adapter.clone())); }
        let args=vec!["--model".into(),model.path.clone(),"--adapter".into(),adapter,"--tests".into(),tests_path.to_string_lossy().into_owned(),"--output".into(),out_path.to_string_lossy().into_owned(),"--max-new-tokens".into(),"128".into()];
        let out=run_python(&app,"hf_eval.py",&args).await.map_err(|e|e.to_string())?;
        if !out.status.success(){return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());}
        let value:ProjectEvaluation=serde_json::from_slice(&fs::read(&out_path).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
        let mut pp=p;pp.status=if value.failed==0{"Évaluation réussie".into()}else{"Échecs détectés — amélioration possible".into()};pp.updated_at=now_iso();save_project(&s.projects_dir,&pp).map_err(|e|e.to_string())?;
        return Ok(value);
    }
    if s.model.read().await.as_ref().map(|m|m.id.as_str())!=Some(p.model_id.as_str()){
        set_model(app.clone(),s.clone(),p.model_id.clone()).await?;
    } else if let Some(a)=p.adapter_path.clone(){set_active_adapter(app.clone(),s.clone(),a).await?;}
    let cfg=s.config.read().await.clone();
    let mut results=Vec::new();
    for t in tests {
        let system=format!("Tu es l'agent d'évaluation. Persona: {}\nObjectif du projet: {}\nRéponds au scénario comme un utilisateur réel, sans expliquer que tu es un testeur.",t.persona,p.objective);
        let answer=chat_once(vec![Msg{role:"system".into(),content:system},Msg{role:"user".into(),content:t.prompt.clone()}],cfg.clone()).await.map_err(|e|e.to_string())?;
        let lower=answer.to_lowercase();
        let mut reasons=Vec::new();
        let mut points=0u32;let mut total=0u32;
        if t.min_chars>0{total+=1;if answer.chars().count()>=t.min_chars{points+=1}else{reasons.push(format!("Réponse trop courte : {} caractères.",answer.chars().count()));}}
        if t.max_chars>0{total+=1;if answer.chars().count()<=t.max_chars{points+=1}else{reasons.push(format!("Réponse trop longue : {} caractères.",answer.chars().count()));}}
        for k in &t.must_contain{total+=1;if lower.contains(&k.to_lowercase()){points+=1}else{reasons.push(format!("Élément attendu absent : {}",k));}}
        for k in &t.must_not_contain{total+=1;if !lower.contains(&k.to_lowercase()){points+=1}else{reasons.push(format!("Élément interdit détecté : {}",k));}}
        if total==0{total=1;points=1;}
        let score=((points*100)/total) as u32;
        results.push(EvalResult{name:t.name,response:answer,passed:score>=80,score,reasons});
    }
    let passed=results.iter().filter(|x|x.passed).count();
    let failed=results.len()-passed;
    let average=if results.is_empty(){0}else{results.iter().map(|x|x.score).sum::<u32>()/(results.len() as u32)};
    let report=ProjectEvaluation{project_id,passed,failed,average_score:average,results};
    let mut pp=p;
    pp.status=if failed==0{"Évaluation réussie".into()}else{"Échecs détectés — amélioration possible".into()};
    pp.updated_at=now_iso();let _=save_project(&s.projects_dir,&pp);
    Ok(report)
}

#[tauri::command]
async fn merge_project_model(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String)->Result<String,String>{
    let p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    let model=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==p.model_id).ok_or("Modèle introuvable.")?;
    let adapter=PathBuf::from(p.adapter_path.clone().ok_or("Aucun adaptateur entraîné.")?);
    let dir=s.projects_dir.join(&project_id);fs::create_dir_all(&dir).map_err(|e|e.to_string())?;
    if model.format=="transformers"{
        if !adapter.is_dir(){return Err("Adaptateur Transformers introuvable.".into());}
        let output=dir.join("merged-model");
        if output.exists(){let _=fs::remove_dir_all(&output);}
        let args=vec!["--model".into(),model.path.clone(),"--adapter".into(),adapter.to_string_lossy().into_owned(),"--output".into(),output.to_string_lossy().into_owned()];
        let out=run_python(&app,"hf_merge.py",&args).await.map_err(|e|e.to_string())?;
        if !out.status.success(){return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());}
        let mut pp=p;pp.merged_model_path=Some(output.to_string_lossy().into_owned());pp.status="Modèle final fusionné".into();pp.updated_at=now_iso();
        save_project(&s.projects_dir,&pp).map_err(|e|e.to_string())?;
        return Ok(output.to_string_lossy().into_owned());
    }
    if !adapter.is_file(){return Err("Adaptateur GGUF introuvable.".into());}
    let output=dir.join("merged-model.gguf");
    if output.exists(){let _=fs::remove_file(&output);}
    let exporter=if vulkan_available(&app).await{"llama-export-lora-vulkan"}else{"llama-export-lora"};
    let args=vec!["-m".into(),model.path.clone(),"--lora".into(),adapter.to_string_lossy().into_owned(),"-o".into(),output.to_string_lossy().into_owned()];
    let (mut rx,child)=app.shell().sidecar(exporter).map_err(|e|e.to_string())?.args(args).spawn().map_err(|e|e.to_string())?;
    let mut exit_code=None;
    while let Some(event)=rx.recv().await{if let CommandEvent::Terminated(payload)=event{exit_code=Some(payload.code.unwrap_or(-1));break;}}
    let _=child.kill();
    if exit_code!=Some(0){return Err(format!("Fusion GGUF échouée (code {}).",exit_code.unwrap_or(-1)));}
    if !output.is_file(){return Err("Le modèle fusionné GGUF n'a pas été généré.".into());}
    let mut pp=p;pp.merged_model_path=Some(output.to_string_lossy().into_owned());pp.status="Modèle final fusionné".into();pp.updated_at=now_iso();
    save_project(&s.projects_dir,&pp).map_err(|e|e.to_string())?;
    Ok(output.to_string_lossy().into_owned())
}

#[tauri::command]
async fn generate_corrections(app:tauri::AppHandle,s:State<'_,Arc<AppState>>,project_id:String,failures:Vec<EvalResult>)->Result<DatasetInfo,String>{
    let p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    let dataset=p.dataset_path.clone().ok_or("Ajoutez d'abord un dataset.")?;
    let model=models(&s.dir).map_err(|e|e.to_string())?.into_iter().find(|m|m.id==p.model_id).ok_or("Modèle introuvable.")?;
    let failures:Vec<_>=failures.into_iter().filter(|x|!x.passed).take(20).collect();
    if failures.is_empty(){return Err("Aucun échec à corriger.".into());}
    let cfg=s.config.read().await.clone();
    let mut new_lines=Vec::new();

    for f in failures {
        let user_prompt=format!("Projet: {}\nObjectif: {}\nRéponse actuelle: {}\nProblèmes détectés: {}\nProduis uniquement une réponse de référence améliorée pour l'utilisateur. Ne parle pas du test.",p.name,p.objective,f.response,f.reasons.join("; "));
        let answer=if model.format=="transformers"{
            let runtime=s.projects_dir.join("_runtime");
            fs::create_dir_all(&runtime).map_err(|e|e.to_string())?;
            let msg_file=runtime.join(format!("correction-{}.json",uuid_like()));
            let msgs=vec![
                Msg{role:"system".into(),content:"Tu es un correcteur local de données d'entraînement. Produis une réponse de référence claire, exacte et conforme à l'objectif.".into()},
                Msg{role:"user".into(),content:user_prompt},
            ];
            fs::write(&msg_file,serde_json::to_vec(&msgs).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
            let adapter=p.adapter_path.clone().unwrap_or_default();
            let args=vec!["--model".into(),model.path.clone(),"--adapter".into(),adapter,"--messages".into(),msg_file.to_string_lossy().into_owned(),"--max-new-tokens".into(),cfg.max_tokens.to_string()];
            let out=run_python(&app,"hf_chat.py",&args).await.map_err(|e|e.to_string())?;
            let _=fs::remove_file(&msg_file);
            if !out.status.success(){return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());}
            String::from_utf8_lossy(&out.stdout).trim().to_string()
        }else{
            if s.model.read().await.as_ref().map(|m|m.id.as_str())!=Some(p.model_id.as_str()){set_model(app.clone(),s.clone(),p.model_id.clone()).await?;}
            else if let Some(a)=p.adapter_path.clone(){set_active_adapter(app.clone(),s.clone(),a).await?;}
            chat_once(vec![
                Msg{role:"system".into(),content:"Tu es un correcteur local de données d'entraînement. Produis une réponse de référence claire, exacte et conforme à l'objectif.".into()},
                Msg{role:"user".into(),content:user_prompt},
            ],cfg.clone()).await.map_err(|e|e.to_string())?
        };
        if !answer.trim().is_empty(){
            new_lines.push(serde_json::json!({"messages":[{"role":"user","content":format!("Cas à corriger: {}",f.name)},{"role":"assistant","content":answer}]}));
        }
    }
    if new_lines.is_empty(){return Err("Aucune correction exploitable n'a été générée.".to_string());}

    let path=PathBuf::from(dataset);
    let mut file=fs::read_to_string(&path).unwrap_or_default();
    for x in &new_lines{file.push_str(&serde_json::to_string(x).map_err(|e|e.to_string())?);file.push('\n');}
    fs::write(&path,file).map_err(|e|e.to_string())?;

    let mut p2=p;
    p2.examples=p2.examples.saturating_add(new_lines.len());
    p2.status=format!("Dataset enrichi · {} corrections ajoutées",new_lines.len());
    p2.updated_at=now_iso();
    save_project(&s.projects_dir,&p2).map_err(|e|e.to_string())?;
    let md=fs::metadata(&path).map_err(|e|e.to_string())?;
    Ok(DatasetInfo{project_id:project_id.clone(),path:path.to_string_lossy().into_owned(),examples:p2.examples,
        chat_examples:p2.examples,text_examples:0,invalid_lines:0,bytes:md.len()})
}


#[tauri::command]
async fn export_project(s:State<'_,Arc<AppState>>,project_id:String,destination:String)->Result<String,String>{
    let p=load_project(&s.projects_dir,&project_id).map_err(|e|e.to_string())?;
    let src=s.projects_dir.join(&project_id);let zip_path=PathBuf::from(destination);
    if let Some(parent)=zip_path.parent(){if !parent.as_os_str().is_empty(){fs::create_dir_all(parent).map_err(|e|e.to_string())?;}}
    let file=fs::File::create(&zip_path).map_err(|e|e.to_string())?;
    let mut z=zip::ZipWriter::new(file);
    let options=zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    fn add_dir(z:&mut zip::ZipWriter<fs::File>,root:&Path,cur:&Path,options:zip::write::SimpleFileOptions)->Result<()>{
        for e in fs::read_dir(cur)?{let p=e?.path();if p.is_dir(){add_dir(z,root,&p,options)?;continue}
            let rel=p.strip_prefix(root)?.to_string_lossy().replace('\\',"/");let data=fs::read(&p)?;z.start_file(rel,options)?;use std::io::Write;z.write_all(&data)?;}
        Ok(())
    }
    add_dir(&mut z,&src,&src,options).map_err(|e|e.to_string())?;
    let manifest=serde_json::json!({
        "vanelle_project_version":1,"name":p.name,"objective":p.objective,"model_id":p.model_id,
        "status":p.status,"dataset":p.dataset_path,"adapter":p.adapter_path,"merged_model":p.merged_model_path,
        "portable_model_support":["gguf","transformers"],"training_backends":["llama.cpp","transformers+peft"]
    });
    z.start_file("vanelle_project_manifest.json",options).map_err(|e|e.to_string())?;
    {use std::io::Write;z.write_all(serde_json::to_string_pretty(&manifest).unwrap().as_bytes()).map_err(|e|e.to_string())?;}
    let readme=format!("# {}\n\nObjectif : {}\nModèle : {}\nFormat entraînable : GGUF ou Transformers selon le modèle importé.\nStatut : {}\n\nLe projet contient les données préparées, checkpoints, évaluations et adaptateurs générés réellement par Vanelle.\n",p.name,p.objective,p.model_id,p.status);
    z.start_file("README.md",options).map_err(|e|e.to_string())?;
    {use std::io::Write;z.write_all(readme.as_bytes()).map_err(|e|e.to_string())?;}
    z.finish().map_err(|e|e.to_string())?;Ok(zip_path.to_string_lossy().into_owned())
}


#[tauri::command]
async fn hf_runtime_info(app:tauri::AppHandle)->Result<serde_json::Value,String>{
    let (program,prefix)=python_runner().map_err(|e|e.to_string())?;
    let code="import torch,transformers,peft; print(transformers.__version__); print('cuda='+str(torch.cuda.is_available()))";
    let mut args=prefix.clone();args.extend(["-c".into(),code.into()]);
    let out=TokioCommand::new(program).args(args).output().await.map_err(|e|e.to_string())?;
    if !out.status.success(){return Ok(serde_json::json!({"ready":false,"detail":String::from_utf8_lossy(&out.stderr)}));}
    let stdout=String::from_utf8_lossy(&out.stdout).trim().to_string();
    Ok(serde_json::json!({"ready":true,"detail":stdout,"scripts":resource_script(&app,"hf_train.py").is_ok()}))
}

fn run()->Result<()>{
    tauri::Builder::default()
      .plugin(tauri_plugin_shell::init())
      .plugin(tauri_plugin_dialog::init())
      .setup(|app|{
        let app_data=app.path().app_data_dir()?;
        let d=app_data.join("models");fs::create_dir_all(&d)?;
        let docs_path=app_data.join("documents.json");
        let model_state_path=app_data.join("current-model.txt");
        let initial_models=models(&d)?;
        let saved_id=load_model_id(&model_state_path);
        let initial=saved_id.as_deref().and_then(|id|initial_models.iter().find(|m|m.id==id).cloned()).or_else(||initial_models.first().cloned());
        let initial_docs=load_docs(&docs_path);
        let projects_dir=app_data.join("projects");fs::create_dir_all(&projects_dir)?;
        let s=Arc::new(AppState{
          model:RwLock::new(initial),adapter:RwLock::new(None),config:RwLock::new(Config::default()),
          child:Mutex::new(None),training_child:Mutex::new(None),training_python_pid:Mutex::new(None),training_running:Mutex::new(false),
          dir:d,docs_path,model_state_path,docs:RwLock::new(initial_docs),projects_dir
        });
        app.manage(s.clone());
        if s.model.blocking_read().is_some(){let h=app.handle().clone();let ss=s.clone();tauri::async_runtime::spawn(async move{let _=start(&h,&ss).await;});}
        Ok(())
      })
      .invoke_handler(tauri::generate_handler![
        list_models,current_model,current_adapter,hardware_info,import_model,remove_model,set_model,set_active_adapter,stop_engine,
        import_document,list_documents,remove_document,search_documents,chat,
        list_projects,create_project,import_project_dataset,model_advisor,model_inspection,
        start_training,stop_training,evaluate_project,generate_corrections,merge_project_model,export_project,activate_project_adapter,hf_runtime_info,vision_info,import_vision_dataset,start_vision_training,evaluate_vision_project,predict_vision_image,vision_runtime_info
      ])
      .run(tauri::generate_context!()).map_err(|e|anyhow!(e.to_string()))?;
    Ok(())
}

fn main(){run().expect("Vanelle Local failed");}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn dataset_parser_supports_chat_records(){
        let v=serde_json::json!({"messages":[{"role":"user","content":"Bonjour"},{"role":"assistant","content":"Salut"}]});
        let (u,a,_) = parse_dataset_line(&v).expect("chat record");
        assert_eq!(u.as_deref(),Some("Bonjour")); assert_eq!(a.as_deref(),Some("Salut"));
    }
    #[test]
    fn model_family_detection_is_deterministic(){
        assert_eq!(guess_family("Qwen3-0.6B-Q8_0"),"Qwen");
        assert_eq!(guess_family("mistral-7b"),"Mistral");
        assert!(guess_family("custom-model").contains("Architecture"));
    }
}