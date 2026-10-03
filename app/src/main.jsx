import {invoke} from "@tauri-apps/api/core";
import {open} from "@tauri-apps/plugin-dialog";
import {useEffect,useMemo,useState} from "react";
import {createRoot} from "react-dom/client";
import "./style.css";

const KEY="vanelle-state-v2";
const uid=()=>Date.now().toString(36)+"-"+Math.random().toString(36).slice(2,8);
const defaults={temperature:.7,max_tokens:1024,context_size:4096,threads:0,gpu_mode:"auto",gpu_layers:"auto",system_prompt:"Tu es Vanelle, un assistant local utile, précis et honnête."};

function load(){try{return JSON.parse(localStorage.getItem(KEY)||"{}")}catch{return {}}}
function save(x){localStorage.setItem(KEY,JSON.stringify(x))}
function initialSession(){return {id:uid(),title:"Nouvelle conversation",messages:[],updated:Date.now()}}

function App(){
 const st=load();
 const [models,setModels]=useState([]),[model,setModel]=useState(st.model||""),[sessions,setSessions]=useState(st.sessions||[initialSession()]);
 const [activeId,setActiveId]=useState((st.sessions&&st.sessions[0]?.id)||""),[input,setInput]=useState(""),[busy,setBusy]=useState(false);
 const [status,setStatus]=useState("Initialisation…"),[hardware,setHardware]=useState(null),[settings,setSettings]=useState({...defaults,...(st.settings||{})});
 const [showSettings,setShowSettings]=useState(false),[docs,setDocs]=useState(st.docs||[]),[memory,setMemory]=useState(st.memory||[]);
 const [search,setSearch]=useState("");
 const active=useMemo(()=>sessions.find(x=>x.id===activeId)||sessions[0]||initialSession(),[sessions,activeId]);

 function persist(nextSessions=sessions,nextSettings=settings,nextDocs=docs,nextMemory=memory,nextModel=model){
   save({sessions:nextSessions,settings:nextSettings,docs:nextDocs,memory:nextMemory,model:nextModel});
   setSessions(nextSessions);setSettings(nextSettings);setDocs(nextDocs);setMemory(nextMemory);setModel(nextModel);
 }
 async function refresh(){
   try{
     const m=await invoke("list_models"); setModels(m);
     const cur=await invoke("current_model"); setModel(cur||model);
     const ds=await invoke("list_documents"); setDocs(ds);
     const hw=await invoke("hardware_info"); setHardware(hw);
     setStatus(cur?("Modèle actif · "+cur):"Importez un modèle GGUF pour commencer");
   }catch(e){setStatus(String(e))}
 }
 useEffect(()=>{refresh()},[]);
 useEffect(()=>{
   let off;
   import("@tauri-apps/api/event").then(({listen})=>listen("chat://chunk",e=>{
     const p=e.payload||{};
     if(p.delta){
       setSessions(old=>old.map(s=>s.id===active.id?{...s,messages:s.messages.map((m,i)=>i===s.messages.length-1?{...m,content:m.content+p.delta}:m),updated:Date.now()}:s));
     }
     if(p.error){setStatus(p.error);setBusy(false)}
     if(p.engine){setStatus(p.engine)}
     if(p.done){setBusy(false);setStatus(p.engine||("Modèle actif · "+model))}
   })).then(x=>off=x);
   return()=>off?.();
 },[active.id,model]);

 async function importModel(){
   const p=await open({multiple:false,filters:[{name:"Modèle GGUF",extensions:["gguf"]}]});
   if(typeof p!=="string")return;
   try{const m=await invoke("import_model",{path:p});await invoke("set_model",{id:m.id});await refresh()}
   catch(e){setStatus(String(e))}
 }
 async function removeModel(id){
   try{await invoke("remove_model",{id});if(id===model){setModel("");await invoke("stop_engine")}await refresh()}catch(e){setStatus(String(e))}
 }
 function newChat(){const s=initialSession();const next=[s,...sessions];persist(next,settings,docs,memory,model);setActiveId(s.id)}
 function renameCurrent(title){
   const next=sessions.map(s=>s.id===active.id?{...s,title:title.slice(0,60)||"Conversation",updated:Date.now()}:s);
   persist(next,settings,docs,memory,model)
 }
 async function send(){
   const text=input.trim();if(!text||busy)return;
   if(!model){setStatus("Importez d’abord un modèle GGUF.");return}
   let context="";
   try{const found=await invoke("search_documents",{query:text,limit:4});context=found.map(x=>"["+x.name+"]\n"+x.snippet).join("\n\n")}catch{}
   const sys=[settings.system_prompt,memory.length?("Mémoire locale utilisateur :\n"+memory.map(x=>"- "+x).join("\n")):"",context?("Documents locaux pertinents :\n"+context):""].filter(Boolean).join("\n\n");
   const msg=[...(active.messages||[]),{role:"user",content:text}];
   const withSystem=sys?[{role:"system",content:sys},...msg]:msg;
   const next=sessions.map(s=>s.id===active.id?{...s,title:s.title==="Nouvelle conversation"?text.slice(0,48)||"Conversation":s.title,messages:[...msg,{role:"assistant",content:""}],updated:Date.now()}:s);
   persist(next,settings,docs,memory,model);setInput("");setBusy(true);
   try{await invoke("chat",{messages:withSystem,config:settings})}
   catch(e){setStatus(String(e));setSessions(old=>old.map(s=>s.id===active.id?{...s,messages:s.messages.slice(0,-1)}:s));setBusy(false)}
 }
 async function importDoc(){
   const p=await open({multiple:false,filters:[{name:"Documents",extensions:["txt","md","markdown","json","csv","pdf","docx"]}]});
   if(typeof p!=="string")return;
   try{const d=await invoke("import_document",{path:p});const next=[d,...docs.filter(x=>x.name!==d.name)].slice(0,30);persist(sessions,settings,next,memory,model);setStatus("Document importé · "+d.name)}
   catch(e){setStatus(String(e))}
 }
 function addMemory(){const v=prompt("Ajouter une mémoire locale :");if(v?.trim()){persist(sessions,settings,docs,[...memory,v.trim()].slice(-100),model)}}
 function deleteMemory(i){persist(sessions,settings,docs,memory.filter((_,n)=>n!==i),model)}
 async function deleteDocument(name){try{await invoke("remove_document",{name});await refresh();setStatus("Document supprimé · "+name)}catch(e){setStatus(String(e))}}
 function deleteChat(){
   if(!active)return;
   if(sessions.length<=1){const s=initialSession();persist([s],settings,docs,memory,model);setActiveId(s.id);return}
   const next=sessions.filter(s=>s.id!==active.id);persist(next,settings,docs,memory,model);setActiveId(next[0].id)
 }
 async function stopGeneration(){try{await invoke("stop_engine");setBusy(false);setStatus("Génération arrêtée · le moteur sera relancé au prochain message")}catch(e){setStatus(String(e))}}
 async function saveSettings(){
   try{persist(sessions,settings,docs,memory,model);if(model){await invoke("set_model",{id:model})}setShowSettings(false);setStatus("Réglages enregistrés")}
   catch(e){setStatus(String(e))}
 }
 function exportChat(){
   const data=JSON.stringify({title:active.title,messages:active.messages,exported_at:new Date().toISOString()},null,2);
   const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([data],{type:"application/json"}));a.download=((active.title||"conversation").replace(/[^a-z0-9-_]+/gi,"_")||"conversation")+".json";a.click();URL.revokeObjectURL(a.href)
 }
 function handleKeyDown(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}}
 const filtered=sessions.filter(s=>!search||s.title.toLowerCase().includes(search.toLowerCase()));
 const recentDocs=docs.slice(0,3);
 const activeModel=models.find(m=>m.id===model);

 return <div className="app">
  <aside>
   <div className="brand">
    <div className="brand-mark">V</div>
    <div className="brand-copy"><strong>Vanelle</strong><span>LOCAL AI</span></div>
   </div>

   <button className="primary" onClick={newChat}>+ Nouvelle conversation</button>
   <input className="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Rechercher…" />

   <div className="sidebar-section">
    <div className="label">Conversations</div>
    <div className="list">
     {filtered.map(s=><button key={s.id} className={"session "+(s.id===active.id?"selected":"")} onClick={()=>setActiveId(s.id)}>
      <div className="session-main"><span className="session-title">{s.title}</span><span className="session-meta">{new Date(s.updated).toLocaleDateString()}</span></div>
     </button>)}
    </div>
   </div>

   <div className="sidebar-card">
    <div className="sidebar-card-title">Modèle local</div>
    {models.length?models.map(m=><div className="model-row" key={m.id}>
      <button className={"model-button "+(m.id===model?"active":"")} onClick={async()=>{try{await invoke("set_model",{id:m.id});setModel(m.id);persist(sessions,settings,docs,memory,m.id);setStatus("Modèle actif · "+m.id)}catch(e){setStatus(String(e))}}}>
       <span className="model-name">{m.id}</span><span className="model-size">{(m.size_bytes/1073741824).toFixed(2)} Go</span>
      </button>
      <button className="mini" onClick={()=>removeModel(m.id)} aria-label="Supprimer">×</button>
    </div>):<div className="muted">Aucun modèle importé.</div>}
   </div>

   <div className="sidebar-card">
    <div className="sidebar-card-title">Documents locaux</div>
    {recentDocs.length?recentDocs.map(d=><div className="doc-row" key={d.name}>
      <button className="doc-button" onClick={()=>setStatus(d.name+" est indexé localement")}><span className="doc-name">{d.name}</span><span className="doc-size">{(d.size_bytes/1024).toFixed(1)} Ko</span></button>
      <button className="mini" onClick={()=>deleteDocument(d.name)} aria-label="Supprimer le document">×</button>
    </div>):<div className="muted">Aucun document indexé.</div>}
   </div>

   <div className="spacer"/>
   <div className="side-actions">
    <button onClick={importModel}>Importer GGUF</button>
    <button onClick={importDoc}>Ajouter un document</button>
    <button onClick={addMemory}>Mémoire locale</button>
   </div>
   <div className="privacy">Traitement local. Aucun fournisseur IA externe obligatoire.</div>
  </aside>

  <main>
   <header>
    <div className="header-title">
     <h1>{active.title}</h1>
     <div className="header-sub">
      <span>{activeModel?.id||"Aucun modèle actif"}</span>
      <span className="status-pill">{status}</span>
     </div>
    </div>
    <div className="header-actions">
     <button onClick={exportChat}>Exporter</button>
     <button onClick={deleteChat}>Supprimer</button>
     <button className="accent" onClick={()=>setShowSettings(true)}>Réglages</button>
    </div>
   </header>

   <section className="messages">
    {!active.messages.length&&<div className="empty">
      <div className="empty-shell">
       <div className="hero-kicker">Vanelle Local</div>
       <h2>Une IA qui reste<br/>sur votre ordinateur.</h2>
       <p>Choisissez un modèle GGUF, ajoutez vos sources locales et démarrez une conversation dans un espace de travail pensé pour le bureau.</p>
       <div className="home-actions">
        <button className="home-card" onClick={importModel}><strong>Importer un modèle</strong><span>Ajoutez votre fichier GGUF et sélectionnez-le comme moteur local.</span></button>
        <button className="home-card" onClick={importDoc}><strong>Ajouter des sources</strong><span>Indexez vos documents pour les utiliser comme contexte local.</span></button>
        <button className="home-card" onClick={()=>setShowSettings(true)}><strong>Configurer Vanelle</strong><span>Ajustez CPU, GPU, contexte, température et prompt système.</span></button>
       </div>
       <div className="cap-row">
        <span className="cap">GGUF</span><span className="cap">llama.cpp</span><span className="cap">CPU + Vulkan</span><span className="cap">Documents locaux</span><span className="cap">Mémoire locale</span>
       </div>
      </div>
     </div>}
    {!!active.messages.length&&<div className="message-stack">
      {active.messages.map((m,i)=><article key={i} className={"message "+m.role}>
       <div className="who">{m.role==="user"?"Vous":m.role==="assistant"?"Vanelle":"Contexte"}</div>
       <div className="message-body">{m.content||(busy&&i===active.messages.length-1?"Génération…":"")}</div>
      </article>)}
    </div>}
   </section>

   <footer>
    <div className="composer">
     <textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder={model?"Écrivez votre message…":"Importez un modèle GGUF pour commencer…"} />
     <div className="footerbar">
      <span>{hardware?.gpu||"GPU : détection en cours"} · Entrée pour envoyer</span>
      <div className="footer-actions">
       {busy&&<button onClick={stopGeneration}>Arrêter</button>}
       <button className="send" disabled={busy||!input.trim()} onClick={send}>Envoyer</button>
      </div>
     </div>
    </div>
   </footer>
  </main>

  {showSettings&&<div className="modal"><div className="card">
   <div className="card-head"><h2>Réglages locaux</h2><button onClick={()=>setShowSettings(false)}>Fermer</button></div>
   <label>Mode matériel<select value={settings.gpu_mode} onChange={e=>setSettings({...settings,gpu_mode:e.target.value})}><option value="auto">Auto : GPU puis CPU</option><option value="gpu">GPU Vulkan</option><option value="cpu">CPU uniquement</option></select></label>
   <label>Couches GPU<select value={settings.gpu_layers} onChange={e=>setSettings({...settings,gpu_layers:e.target.value})}><option value="auto">Auto</option><option value="all">Toutes</option><option value="0">0</option></select></label>
   <label>Contexte<input type="number" min="1024" max="131072" value={settings.context_size} onChange={e=>setSettings({...settings,context_size:Number(e.target.value)||4096})}/></label>
   <label>Température<input type="number" min="0" max="2" step=".05" value={settings.temperature} onChange={e=>setSettings({...settings,temperature:Number(e.target.value)||0})}/></label>
   <label>Threads CPU (0 = automatique)<input type="number" min="0" max="256" value={settings.threads} onChange={e=>setSettings({...settings,threads:Math.max(0,Number(e.target.value)||0)})}/></label>
   <label>Max tokens<input type="number" min="32" max="8192" value={settings.max_tokens} onChange={e=>setSettings({...settings,max_tokens:Number(e.target.value)||1024})}/></label>
   <label>Prompt système<textarea value={settings.system_prompt} onChange={e=>setSettings({...settings,system_prompt:e.target.value})}/></label>
   <div className="card-head"><h3>Mémoire locale</h3><span>{memory.length} élément(s)</span></div>
   <div className="memory">{memory.map((x,i)=><div key={i}><span>{x}</span><button onClick={()=>deleteMemory(i)}>Supprimer</button></div>)}</div>
   <div className="hardware"><b>Machine</b><div>{hardware?.cpu||"CPU : —"}</div><div>{hardware?.ram||"RAM : —"}</div><div>{hardware?.gpu||"GPU : —"}</div><div>{hardware?.vram||"VRAM : —"}</div><div>{hardware?.vulkan||"Vulkan : détection —"}</div></div>
   <button className="primary wide" onClick={saveSettings}>Enregistrer les réglages</button>
  </div></div>}
 </div>
}
createRoot(document.getElementById("root")).render(<App/>);
