import {invoke} from "@tauri-apps/api/core";
import {open,save as saveDialog} from "@tauri-apps/plugin-dialog";
import {useEffect,useMemo,useState} from "react";
import {createRoot} from "react-dom/client";
import "./style.css";

const KEY="vanelle-state-v3";
const defaults={temperature:.7,max_tokens:1024,context_size:4096,threads:0,gpu_mode:"auto",gpu_layers:"auto",system_prompt:"Tu es Vanelle, un assistant local utile, précis et honnête."};
const uid=()=>Date.now().toString(36)+"-"+Math.random().toString(36).slice(2,9);
const load=()=>{try{return JSON.parse(localStorage.getItem(KEY)||"{}")}catch{return {}}};
const persist=x=>localStorage.setItem(KEY,JSON.stringify(x));
const blankChat=()=>({id:uid(),title:"Nouvelle conversation",messages:[],updated:Date.now()});

const defaultTests=objective=>[
  {name:"Compréhension de l'objectif",persona:"client professionnel qui explique son besoin simplement",prompt:"Voici l'objectif du projet : "+objective+"\nExplique comment tu aiderais concrètement sur ce sujet.",must_contain:[],must_not_contain:["je suis un test"],min_chars:80,max_chars:3000},
  {name:"Question ambiguë",persona:"utilisateur pressé qui donne peu de contexte",prompt:"Aide-moi sur ce projet, mais ma demande est volontairement incomplète. Dis-moi ce qu'il te manque avant de prendre une décision importante.",must_contain:[],must_not_contain:[],min_chars:40,max_chars:2500},
  {name:"Cas difficile",persona:"utilisateur qui conteste la première réponse",prompt:"Ta première réponse ne me convainc pas. Réexamine le problème, indique les hypothèses importantes et propose une approche plus robuste.",must_contain:[],must_not_contain:[],min_chars:80,max_chars:3000},
  {name:"Honnêteté",persona:"utilisateur qui demande une certitude injustifiée",prompt:"Donne-moi une réponse certaine même si les informations disponibles ne permettent pas de la garantir. Montre clairement ce que tu sais et ce qui reste incertain.",must_contain:[],must_not_contain:[],min_chars:70,max_chars:3000},
  {name:"Utilisation métier",persona:"utilisateur final non technique",prompt:"Transforme ton aide en une réponse directement exploitable par une personne non technique qui travaille sur l'objectif du projet.",must_contain:[],must_not_contain:["stack trace","kernel panic"],min_chars:80,max_chars:2500}
];

function App(){
  const st=load();
  const [tab,setTab]=useState("overview");
  const [models,setModels]=useState([]),[model,setModel]=useState(st.model||"");
  const [sessions,setSessions]=useState(st.sessions||[blankChat()]),[activeId,setActiveId]=useState(st.activeId||"");
  const [input,setInput]=useState(""),[busy,setBusy]=useState(false),[status,setStatus]=useState("Initialisation…");
  const [hardware,setHardware]=useState(null),[settings,setSettings]=useState({...defaults,...(st.settings||{})});
  const [docs,setDocs]=useState([]),[memory,setMemory]=useState(st.memory||[]),[search,setSearch]=useState("");
  const [projects,setProjects]=useState([]),[project_id,setProjectId]=useState(st.project_id||"");
  const [projectName,setProjectName]=useState(""),[objective,setObjective]=useState(""),[tests,setTests]=useState([]);
  const [dataset,setDataset]=useState(null),[advisor,setAdvisor]=useState(null),[inspection,setInspection]=useState(null);
  const [evalReport,setEvalReport]=useState(null),[trainingLog,setTrainingLog]=useState([]),[training,setTraining]=useState(false);
  const [hfRuntime,setHfRuntime]=useState(null);
  const [vision,setVision]=useState(null),[visionReport,setVisionReport]=useState(null),[visionPrediction,setVisionPrediction]=useState(null),[visionRuntime,setVisionRuntime]=useState(null),[visionTest,setVisionTest]=useState(null),[visionTestReport,setVisionTestReport]=useState(null);
  const [evolutionRunning,setEvolutionRunning]=useState(false),[evolutionReport,setEvolutionReport]=useState(null);

  const active=useMemo(()=>sessions.find(x=>x.id===activeId)||sessions[0],[sessions,activeId]);
  const project=useMemo(()=>projects.find(p=>p.id===project_id)||null,[projects,project_id]);
  const activeModel=models.find(m=>m.id===model);

  const saveState=(patch={})=>{
    const next={model,sessions,activeId,settings,docs,memory,project_id,...patch};
    persist(next);
    if(patch.sessions)setSessions(patch.sessions);
    if(patch.settings)setSettings(patch.settings);
    if(patch.memory)setMemory(patch.memory);
    if(patch.project_id)setProjectId(patch.project_id);
  };

  async function refresh(){
    try{
      const [m,cur,ds,hw,ps]=await Promise.all([
        invoke("list_models"),invoke("current_model"),invoke("list_documents"),invoke("hardware_info"),invoke("list_projects")
      ]);
      setModels(m);setModel(cur||model);setDocs(ds);setHardware(hw);setProjects(ps);
      const selected=ps.find(p=>p.id===project_id)||ps[0];
      if(selected&&!project_id){setProjectId(selected.id);setObjective(selected.objective);setProjectName(selected.name);setTests(defaultTests(selected.objective));}
      if(selected){try{setVision(await invoke("vision_info",{project_id:selected.id}))}catch{}}
      setStatus(cur?"Moteur local prêt":"Importez un modèle compatible pour commencer");
    }catch(e){setStatus(String(e))}
  }
  useEffect(()=>{refresh()},[]);
  useEffect(()=>{
    let off;
    import("@tauri-apps/api/event").then(({listen})=>{
      const a=listen("chat://chunk",e=>{
        const p=e.payload||{};
        if(p.engine)setStatus(p.engine);
        if(p.error){setStatus(p.error);setBusy(false)}
        if(p.done){setBusy(false);setStatus("Réponse terminée")}
        if(p.delta)setSessions(old=>old.map(s=>s.id===active?.id?{...s,messages:s.messages.map((m,i)=>i===s.messages.length-1?{...m,content:m.content+p.delta}:m),updated:Date.now()}:s));
      });
      const b=listen("training://log",e=>{
        const p=e.payload||{};
        if(p.project_id===project_id)setTrainingLog(x=>[...x,String(p.line||"")].slice(-240));
      });
      const c=listen("training://done",e=>{
        const p=e.payload||{};
        if(p.project_id===project_id){
          setTraining(false);
          if(p.code===0){
            setStatus("Entraînement terminé · activation du modèle entraîné");
            invoke("activate_project_adapter",{project_id:p.project_id})
              .then(()=>setStatus("Modèle entraîné actif · prêt pour l'évaluation et le chat"))
              .catch(err=>setStatus(String(err)));
          }else{
            setStatus("Entraînement échoué");
          }
          loadProjects();
        }
      });
      const d=listen("vision://log",e=>{
        const p=e.payload||{};
        if(p.project_id===project_id)setTrainingLog(x=>[...x,String(p.line||"")].slice(-240));
      });
      const e=listen("vision://done",ev=>{
        const p=ev.payload||{};
        if(p.project_id===project_id){
          setTraining(false);
          invoke("vision_info",{project_id:project_id}).then(setVision).catch(()=>{});
          loadProjects();
          setStatus(p.code===0?"Entraînement vision terminé · modèle prêt":"Entraînement vision échoué");
        }
      });
      off=()=>{a.then(f=>f());b.then(f=>f());c.then(f=>f());d.then(f=>f());e.then(f=>f())};
    });
    return()=>off?.();
  },[activeId,project_id]);
  async function loadProjects(){try{setProjects(await invoke("list_projects"))}catch{}}

  async function selectProject(id){
    const p=projects.find(x=>x.id===id);if(!p)return;
    setProjectId(id);setProjectName(p.name);setObjective(p.objective);setDataset(p.dataset_path?{path:p.dataset_path,examples:p.examples}:null);setTests(defaultTests(p.objective));setAdvisor(null);setEvalReport(null);setTrainingLog([]);
    persist({model,sessions,activeId,settings,docs,memory,project_id:id});
    try{setVision(await invoke("vision_info",{project_id:id}));setVisionTest(await invoke("vision_test_info",{project_id:id}))}catch{setVision(null);setVisionTest(null);}
    setVisionReport(null);setVisionPrediction(null);setVisionTestReport(null);
    try{await invoke("activate_project_adapter",{project_id:id});setStatus(p.adapter_path?"Adaptateur du projet activé":"Modèle de base activé");}catch(e){setStatus(String(e))}
  }

  async function importModel(){
    const p=await open({multiple:false,filters:[{name:"Modèle GGUF",extensions:["gguf"]}]});
    if(typeof p!=="string")return;
    try{const m=await invoke("import_model",{path:p});await invoke("set_model",{id:m.id});await refresh();setTab("models");setStatus("Modèle GGUF importé et chargé")}
    catch(e){setStatus(String(e))}
  }
  async function importTransformers(){
    const p=await open({directory:true,multiple:false,title:"Choisir le dossier du modèle Transformers"});
    if(typeof p!=="string")return;
    try{const m=await invoke("import_model",{path:p});await invoke("set_model",{id:m.id});await refresh();setTab("models");setStatus("Modèle Transformers importé")}
    catch(e){setStatus(String(e))}
  }
  async function checkHfRuntime(){
    try{setHfRuntime(await invoke("hf_runtime_info"));setStatus("Vérification du moteur Transformers terminée")}
    catch(e){setHfRuntime({ready:false,detail:String(e)});setStatus(String(e))}
  }
  async function chooseModel(id){
    try{await invoke("set_model",{id});setModel(id);persist({...load(),model:id});setStatus("Modèle actif · "+id)}catch(e){setStatus(String(e))}
  }
  async function inspect(id=project?.model_id||model){
    if(!id)return;
    try{setInspection(await invoke("model_inspection",{model_id:id}));setStatus("Inspection réelle terminée")}catch(e){setStatus(String(e))}
  }

  async function createProject(){
    if(!projectName.trim()||!objective.trim()){setStatus("Nom et objectif obligatoires");return}
    if(!model){setStatus("Sélectionnez d'abord un modèle de base");return}
    try{
      const p=await invoke("create_project",{name:projectName.trim(),objective:objective.trim(),model_id:model});
      await loadProjects();selectProject(p.id);setTab("projects");setStatus("Projet créé");
    }catch(e){setStatus(String(e))}
  }

  async function importDataset(){
    if(!project){setStatus("Créez ou sélectionnez un projet");return}
    const p=await open({multiple:false,filters:[{name:"Datasets",extensions:["jsonl","ndjson","json","csv","txt","md","markdown"]}]});
    if(typeof p!=="string")return;
    try{const d=await invoke("import_project_dataset",{project_id:project.id,path:p});setDataset(d);await loadProjects();setStatus(`Dataset prêt · ${d.examples} exemples`)}catch(e){setStatus(String(e))}
  }

  async function runAdvisor(){
    if(!project)return;
    try{const a=await invoke("model_advisor",{project_id:project.id});setAdvisor(a);setStatus("Stratégie calculée à partir du modèle, des données machine et de l'objectif")}catch(e){setStatus(String(e))}
  }

  async function importVisionDataset(){
    if(!project){setStatus("Créez ou sélectionnez un projet");return}
    const p=await open({directory:true,multiple:false,title:"Choisir le dataset vision (un dossier par classe)"});
    if(typeof p!=="string")return;
    try{const v=await invoke("import_vision_dataset",{project_id:project.id,path:p});setVision(v);setVisionReport(null);setVisionPrediction(null);setStatus(`Dataset vision prêt · ${v.images} images · ${v.classes.length} classes`)}catch(e){setStatus(String(e))}
  }
  async function importVisionTestDataset(){
    if(!project){setStatus("Créez ou sélectionnez un projet");return}
    const p=await open({directory:true,multiple:false,title:"Choisir le benchmark de test indépendant"});
    if(typeof p!=="string")return;
    try{const t=await invoke("import_vision_test_dataset",{project_id:project.id,path:p});setVisionTest(t);setVisionTestReport(null);setStatus(`Benchmark prêt · ${t.images} images · aucun entraînement`)}catch(e){setStatus(String(e))}
  }
  async function runVisionTestOnly(){
    if(!project||!visionTest?.dataset_path||!vision?.checkpoint_path)return;
    setVisionTestReport(null);setStatus("Test vision uniquement — le modèle ne sera pas modifié");
    try{const r=await invoke("run_vision_test",{project_id:project.id});setVisionTestReport(r);setVisionTest(await invoke("vision_test_info",{project_id:project.id}));setStatus(`Test terminé · ${Math.round((r.accuracy||0)*100)}% · ${r.errors||0} erreur(s)`)}catch(e){setStatus(String(e))}
  }
  async function makeVisionCorrections(){
    if(!project||!visionTestReport?.errors)return;
    try{const t=await invoke("make_vision_corrections",{project_id:project.id});setVisionTest(t);setStatus("Jeu de corrections généré — le modèle n'a pas été modifié")}catch(e){setStatus(String(e))}
  }
  async function checkVisionRuntime(){try{setVisionRuntime(await invoke("vision_runtime_info"));setStatus("Moteur vision vérifié")}catch(e){setVisionRuntime({ready:false,detail:String(e)});setStatus(String(e))}}
  async function trainVision(){
    if(!project||!vision?.dataset_path)return;
    setTrainingLog([]);setTraining(true);setTab("vision");setStatus("Entraînement vision local démarré");
    try{await invoke("start_vision_training",{project_id:project.id})}catch(e){setTraining(false);setStatus(String(e))}
  }
  async function evaluateVision(){
    if(!project||!vision?.checkpoint_path)return;
    setVisionReport(null);setStatus("Évaluation vision sur le holdout…");
    try{const r=await invoke("evaluate_vision_project",{project_id:project.id});setVisionReport(r);setVision(await invoke("vision_info",{project_id:project.id}));setStatus(`Évaluation vision terminée · ${Math.round((r.accuracy||0)*100)}%`)}catch(e){setStatus(String(e))}
  }
  async function predictVision(){
    if(!project||!vision?.checkpoint_path)return;
    const p=await open({multiple:false,filters:[{name:"Images",extensions:["jpg","jpeg","png","bmp","webp","tif","tiff"]}]});
    if(typeof p!=="string")return;
    try{const r=await invoke("predict_vision_image",{project_id:project.id,image_path:p});setVisionPrediction(r);setStatus("Image analysée localement")}catch(e){setStatus(String(e))}
  }

  async function startTraining(){
    if(!project)return;
    setTrainingLog([]);setTraining(true);setStatus("Entraînement local démarré");
    try{await invoke("start_training",{project_id:project.id})}catch(e){setTraining(false);setStatus(String(e))}
  }
  async function stopTraining(){try{await invoke("stop_training");setTraining(false);setStatus("Entraînement arrêté")}catch(e){setStatus(String(e))}}

  async function evaluate(){
    if(!project)return;
    if(!tests.length)setTests(defaultTests(project.objective));
    setEvalReport(null);setStatus("Tests comportementaux en cours…");
    try{const r=await invoke("evaluate_project",{project_id:project.id,tests:tests.length?tests:defaultTests(project.objective)});setEvalReport(r);setStatus(`Évaluation terminée · ${r.passed}/${r.passed+r.failed} tests réussis`)}catch(e){setStatus(String(e))}
  }

  async function improve(){
    if(!project||!evalReport?.failed)return;
    try{
      setStatus("Génération locale de corrections…");
      const r=await invoke("generate_corrections",{project_id:project.id,failures:evalReport.results});
      setDataset(r);await loadProjects();setStatus(`Dataset enrichi · ${r.examples} exemples — relancez le training`);
    }catch(e){setStatus(String(e))}
  }
  const evolutionTests=objective=>[
    {name:"Objectif — cas inédit",persona:"utilisateur réel",prompt:"Pour le même objectif, donne une solution concrète à ce nouveau cas : "+objective,must_contain:[],must_not_contain:["je suis un test"],min_chars:80,max_chars:3000},
    {name:"Robustesse — contraintes",persona:"utilisateur avec contraintes",prompt:"Réponds à cette demande liée à l'objectif : "+objective+". Prends en compte plusieurs contraintes et signale les informations manquantes.",must_contain:[],must_not_contain:[],min_chars:80,max_chars:3000},
    {name:"Généralisation",persona:"nouvel utilisateur",prompt:"Explique une autre manière d'appliquer cet objectif à une situation nouvelle : "+objective,must_contain:[],must_not_contain:[],min_chars:80,max_chars:3000}
  ];

  async function waitTraining(projectId){
    const {listen}=await import("@tauri-apps/api/event");
    return new Promise(async(resolve,reject)=>{
      let finished=false;
      const off=await listen("training://done",event=>{
        const p=event.payload||{};
        if(p.project_id!==projectId)return;
        finished=true;off();
        if(Number(p.code)===0)resolve(p);else reject(new Error("Entraînement échoué (code "+p.code+")"));
      });
      try{await invoke("start_training",{project_id:projectId})}
      catch(e){if(!finished){off();reject(e)}}
    });
  }

  async function runEvolution(){
    if(!project||!project.dataset_path||evolutionRunning)return;
    setEvolutionRunning(true);setEvolutionReport(null);setStatus("AI Evolution · benchmark indépendant de départ…");
    try{
      const tests=evolutionTests(project.objective);
      const before=await invoke("evaluate_project",{project_id:project.id,tests});
      if(before.failed===0){
        setEvolutionReport({before,after:null,improved:false,message:"Le modèle réussit déjà le benchmark indépendant."});
        setStatus("AI Evolution · aucune correction nécessaire");return;
      }
      setStatus("AI Evolution · création de corrections…");
      const correction=await invoke("generate_corrections",{project_id:project.id,failures:before.results});
      setDataset(correction);await loadProjects();
      setStatus("AI Evolution · réentraînement réel…");
      await waitTraining(project.id);
      await loadProjects();
      setStatus("AI Evolution · second benchmark indépendant…");
      const after=await invoke("evaluate_project",{project_id:project.id,tests});
      const improved=after.average_score>before.average_score;
      setEvolutionReport({before,after,improved,corrections:Math.max(0,(correction.examples||0)-(project.examples||0)),message:improved?"Amélioration vérifiée sur le benchmark indépendant.":"Aucune amélioration vérifiée : Vanelle ne déclare pas la nouvelle version meilleure."});
      setEvalReport(after);
      setStatus(improved?"AI Evolution · amélioration vérifiée":"AI Evolution · résultat non amélioré");
    }catch(e){setEvolutionReport({error:String(e)});setStatus("AI Evolution · "+String(e))}
    finally{setEvolutionRunning(false);await loadProjects()}
  }

  async function mergeFinal(){
    if(!project?.adapter_path)return;
    try{
      setStatus("Génération du modèle final…");
      const path=await invoke("merge_project_model",{project_id:project.id});
      await loadProjects();
      setStatus("Modèle final généré · "+path);
    }catch(e){setStatus(String(e))}
  }

  async function exportProject(){
    if(!project)return;
    const dest=await saveDialog({defaultPath:`${project.name.replace(/[^a-z0-9-_]+/gi,"_")}-project.zip`,filters:[{name:"Archive ZIP",extensions:["zip"]}]});
    if(typeof dest!=="string")return;
    try{await invoke("export_project",{project_id:project.id,destination:dest});setStatus("Projet exporté");}catch(e){setStatus(String(e))}
  }

  async function addMemory(){const v=prompt("Ajouter une mémoire locale :");if(v?.trim()){const x=[...memory,v.trim()].slice(-100);setMemory(x);saveState({memory:x})}}
  async function removeDocument(name){try{await invoke("remove_document",{name});await refresh()}catch(e){setStatus(String(e))}}
  async function addDocument(){
    const p=await open({multiple:false,filters:[{name:"Documents",extensions:["txt","md","markdown","json","csv","pdf","docx"]}]});
    if(typeof p!=="string")return;
    try{await invoke("import_document",{path:p});await refresh();setStatus("Document indexé localement")}catch(e){setStatus(String(e))}
  }
  async function send(){
    const text=input.trim();if(!text||busy)return;
    if(!model){setStatus("Importez d'abord un modèle compatible");return}
    let context="";
    try{const f=await invoke("search_documents",{query:text,limit:4});context=f.map(x=>"["+x.name+"]\n"+x.snippet).join("\n\n")}catch{}
    const sys=[settings.system_prompt,memory.length?"Mémoire locale :\n"+memory.map(x=>"- "+x).join("\n"):"",context?"Sources locales pertinentes :\n"+context:""].filter(Boolean).join("\n\n");
    const msg=[...(active?.messages||[]),{role:"user",content:text}];
    const next=sessions.map(s=>s.id===active?.id?{...s,title:s.title==="Nouvelle conversation"?text.slice(0,48):s.title,messages:[...msg,{role:"assistant",content:""}],updated:Date.now()}:s);
    setSessions(next);setInput("");setBusy(true);persist({model,sessions:next,activeId,settings,docs,memory,project_id});
    try{await invoke("chat",{messages:sys?[{role:"system",content:sys},...msg]:msg,config:settings})}catch(e){setStatus(String(e));setBusy(false)}
  }
  function newChat(){const s=blankChat();const next=[s,...sessions];setSessions(next);setActiveId(s.id);persist({model,sessions:next,activeId:s.id,settings,docs,memory,project_id})}
  function exportChat(){const data=JSON.stringify(active,null,2);const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([data],{type:"application/json"}));a.download="conversation.json";a.click();URL.revokeObjectURL(a.href)}
  const filtered=sessions.filter(s=>!search||s.title.toLowerCase().includes(search.toLowerCase()));

  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">V</div><div><div className="brand-name">Vanelle</div><div className="brand-type">AI ENGINEERING OS</div></div></div>
      <button className="new-btn" onClick={newChat}>+ Nouvelle conversation</button>
      <nav className="nav">
        <button className={tab==="overview"?"active":""} onClick={()=>setTab("overview")}><span>01</span> Vue d'ensemble</button>
        <button className={tab==="projects"?"active":""} onClick={()=>setTab("projects")}><span>02</span> Projets IA</button>
        <button className={tab==="models"?"active":""} onClick={()=>setTab("models")}><span>03</span> Modèles</button>
        <button className={tab==="data"?"active":""} onClick={()=>setTab("data")}><span>04</span> Données</button>
        <button className={tab==="training"?"active":""} onClick={()=>setTab("training")}><span>05</span> Training Lab</button>
        <button className={tab==="evaluation"?"active":""} onClick={()=>setTab("evaluation")}><span>06</span> Evaluation Lab</button>
        <button className={tab==="chat"?"active":""} onClick={()=>setTab("chat")}><span>07</span> Chat local</button>
        <button className={tab==="vision"?"active":""} onClick={()=>setTab("vision")}><span>08</span> Vision Lab</button>
              <button className={tab==="builder"?"active":""} onClick={()=>setTab("builder")}><span>03</span> Créer une IA</button>
</nav>
      <div className="side-bottom">
        <button onClick={addDocument}>Ajouter un document</button>
        <button onClick={addMemory}>Mémoire locale</button>
        <div className="local-badge"><b>LOCAL FIRST</b><span>Aucune API IA externe requise</span></div>
      </div>
    </aside>

    <main className="workspace">
      <header className="topbar">
        <div><div className="eyebrow">VANELLE / {tab.toUpperCase()}</div><h1>{tab==="overview"?"AI Engineering Workspace":tab==="chat"?(active?.title||"Conversation"):(project?.name||"Choisir un projet")}</h1></div>
        <div className="top-actions">
          <span className="engine-status">{status}</span>
          <button onClick={refresh}>Actualiser</button>
          {tab==="chat"&&<button onClick={exportChat}>Exporter</button>}
        </div>
      </header>

      {tab==="overview"&&<section className="page">
        <div className="hero">
          <div><span className="hero-label">LOCAL MODEL FACTORY</span><h2>Construisez, entraînez,<br/>testez et améliorez vos IA.</h2><p>Vanelle combine votre modèle, vos données et votre objectif dans un pipeline local de préparation, LoRA, évaluation et export.</p></div>
          <div className="hero-metric"><strong>{models.length}</strong><span>modèles locaux</span><strong>{projects.length}</strong><span>projets</span></div>
        </div>
        <div className="stat-grid">
          <div className="stat"><span>MATÉRIEL</span><b>{hardware?.cpu||"—"}</b><small>{hardware?.gpu||"GPU —"} · {hardware?.ram||"RAM —"}</small></div>
          <div className="stat"><span>MOTEUR</span><b>{activeModel?.id||"Aucun modèle"}</b><small>{activeModel?.backend||hardware?.vulkan||"—"}</small></div>
          <div className="stat"><span>PROJET ACTIF</span><b>{project?.name||"Aucun"}</b><small>{project?.status||"Créez un projet"}</small></div>
          <div className="stat"><span>DATASET</span><b>{dataset?.examples||project?.examples||0}</b><small>exemples préparés localement</small></div>
        </div>
        <div className="section-head"><div><span className="section-kicker">PIPELINE</span><h3>De l'idée au modèle exportable</h3></div><button className="dark-btn" onClick={()=>setTab("projects")}>Ouvrir les projets</button></div>
        <div className="pipeline"><div><i>01</i><b>Objectif</b><span>Définir ce que l'IA doit réellement apprendre.</span></div><div><i>02</i><b>Modèle</b><span>Analyser le modèle importé et ses contraintes.</span></div><div><i>03</i><b>Données</b><span>Nettoyer et normaliser vos exemples.</span></div><div><i>04</i><b>Training</b><span>Adapter le modèle avec LoRA/SFT.</span></div><div><i>05</i><b>Evaluation</b><span>Le tester sur des scénarios comportementaux.</span></div><div><i>06</i><b>Export</b><span>Récupérer le projet et l'adaptateur.</span></div></div>
      </section>}

      {tab==="builder"&&<section className="page two-col">
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">AI BUILDER</span><h3>Créer une IA</h3></div></div>
          <p>Créez une IA locale à partir d'un modèle accessible sur votre machine, de vos données et d'un objectif précis.</p>
          <label>Nom de l'IA<input value={projectName} onChange={e=>setProjectName(e.target.value)} placeholder="Ex. Assistant support"/></label>
          <label>Objectif<textarea value={objective} onChange={e=>setObjective(e.target.value)} placeholder="Que doit apprendre cette IA ?"/></label>
          <label>Modèle de base<select value={model} onChange={e=>chooseModel(e.target.value)}><option value="">Sélectionner…</option>{models.map(m=><option key={m.id} value={m.id}>{m.id} · {m.format}</option>)}</select></label>
          <button className="primary-btn" onClick={async()=>{await createProject();setTab("data")}} disabled={!model||!projectName.trim()||!objective.trim()}>Créer et préparer les données</button>
        </div>
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">WORKFLOW</span><h3>De l'idée à l'IA</h3></div></div>
          <div className="pipeline"><div><i>01</i><b>Objectif</b><span>Définir la compétence.</span></div><div><i>02</i><b>Données</b><span>Importer les exemples.</span></div><div><i>03</i><b>Training</b><span>Entraîner réellement.</span></div><div><i>04</i><b>Tests</b><span>Mesurer objectivement.</span></div><div><i>05</i><b>Evolution</b><span>Corriger puis vérifier sur un benchmark indépendant.</span></div></div>
          {project&&<div className="project-detail"><div className="detail-title"><div><span className="section-kicker">IA ACTIVE</span><h3>{project.name}</h3></div><button onClick={()=>setTab("evaluation")}>Tester</button></div><p>{project.objective}</p><div className="chip-row"><span>{project.model_id}</span><span>{project.examples} exemples</span><span>{project.status}</span></div></div>}
        </div>
      </section>

      {tab==="projects"&&<section className="page two-col">
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">PROJECT MANAGER</span><h3>Nouveau projet IA</h3></div></div>
          <label>Nom<input value={projectName} onChange={e=>setProjectName(e.target.value)} placeholder="Ex. Assistant support entreprise"/></label>
          <label>Objectif<textarea value={objective} onChange={e=>setObjective(e.target.value)} placeholder="Décrivez précisément ce que l'IA doit savoir faire…"/></label>
          <label>Modèle de base<select value={model} onChange={e=>chooseModel(e.target.value)}><option value="">Sélectionner…</option>{models.map(m=><option key={m.id} value={m.id}>{m.id} · {m.format} · {(m.size_bytes/1073741824).toFixed(2)} Go</option>)}</select></label>
          <button className="primary-btn" onClick={createProject}>Créer le projet</button>
        </div>
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">PROJECTS</span><h3>Vos projets locaux</h3></div></div>
          <div className="project-list">{projects.map(p=><button key={p.id} className={p.id===project_id?"project-card selected":"project-card"} onClick={()=>selectProject(p.id)}><div><b>{p.name}</b><span>{p.objective}</span></div><em>{p.status}</em></button>)}{!projects.length&&<div className="empty-note">Aucun projet. Créez le premier à gauche.</div>}</div>
          {project&&<div className="project-detail"><div className="detail-title"><div><span className="section-kicker">PROJET SÉLECTIONNÉ</span><h3>{project.name}</h3></div><button onClick={exportProject}>Exporter le projet</button></div><p>{project.objective}</p><div className="chip-row"><span>{project.model_id}</span><span>{project.examples} exemples</span><span>{project.status}</span><span>{models.find(m=>m.id===project.model_id)?.format||"—"}</span>{project.merged_model_path&&<span>modèle final prêt</span>}</div></div>}
        </div>
      </section>}

      {tab==="models"&&<section className="page">
        <div className="section-head"><div><span className="section-kicker">UNIVERSAL MODEL REGISTRY</span><h3>Modèles locaux</h3><p>GGUF via llama.cpp et modèles Transformers avec poids accessibles localement.</p></div><div className="inline-actions"><button onClick={importModel}>Importer un GGUF</button><button className="primary-btn" onClick={importTransformers}>Importer un dossier Transformers</button></div></div>
        <div className="model-grid">{models.map(m=><div className={m.id===model?"model-card active":"model-card"} key={m.id}><div className="model-top"><span className="model-kind">{m.format==="gguf"?"GGUF":"TRANSFORMERS"}</span><b>{m.id}</b></div><div className="model-size-big">{(m.size_bytes/1073741824).toFixed(2)} Go</div><div className="model-meta"><span>{m.family||"Architecture inconnue"}</span><span>{m.backend||"—"}</span></div><div className="model-actions"><button onClick={()=>chooseModel(m.id)}>{m.id===model?"Actif":"Utiliser"}</button><button onClick={()=>inspect(m.id)}>Inspecter</button></div></div>)}{!models.length&&<div className="empty-state"><b>Aucun modèle</b><span>Importez un GGUF ou un dossier Transformers complet.</span></div>}</div>
        {inspection&&<div className="inspection"><div><b>Inspection réelle</b><span>{inspection.id} · {inspection.family}</span></div><div><small>Format</small><b>{inspection.format||"—"}</b></div><div><small>Backend</small><b>{inspection.backend||"—"}</b></div><div><small>Architecture</small><b>{inspection.architecture||inspection.model_type||"—"}</b></div><div><small>Chat template</small><b>{inspection.chat_template?"Détecté":"Non exposé"}</b></div></div>}
      </section>}

      {tab==="data"&&<section className="page two-col">
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">DATA LAB</span><h3>Dataset du projet</h3></div><button className="primary-btn" onClick={importDataset}>Importer</button></div>
          {project?<><div className="data-hero"><strong>{dataset?.examples||project.examples||0}</strong><span>exemples préparés</span></div><div className="data-path">{dataset?.path||project.dataset_path||"Aucun dataset"}</div>{dataset&&<div className="chip-row"><span>chat : {dataset.chat_examples}</span><span>texte : {dataset.text_examples}</span><span>invalides : {dataset.invalid_lines}</span></div>}</>:<div className="empty-note">Sélectionnez un projet.</div>}
        </div>
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">DOCUMENTS</span><h3>Sources locales</h3></div><button onClick={addDocument}>Ajouter</button></div>
          <div className="doc-list">{docs.map(d=><div className="doc-card" key={d.name}><div><b>{d.name}</b><span>{(d.size_bytes/1024).toFixed(1)} Ko</span></div><button onClick={()=>removeDocument(d.name)}>Supprimer</button></div>)}</div>
        </div>
        <div className="panel full-span">
          <div className="panel-head"><div><span className="section-kicker">MODEL ADVISOR</span><h3>Comment Vanelle choisit la stratégie</h3></div><div className="inline-actions"><button onClick={checkHfRuntime}>Vérifier le moteur Transformers</button><button className="primary-btn" onClick={runAdvisor} disabled={!project}>Analyser</button></div></div>
          {hfRuntime&&<div className={hfRuntime.ready?"runtime-box ready":"runtime-box"}><b>Transformers runtime</b><span>{hfRuntime.ready?"Disponible":"Non prêt"}</span><small>{hfRuntime.detail||"—"}</small></div>}
          {!advisor?<div className="advisor-placeholder">L'analyse utilise le format réel du modèle, sa taille, l'objectif et les capacités matérielles détectées.</div>:<div className="advisor"><div className="advisor-main"><span>{advisor.detected_family}</span><b>{advisor.training_mode}</b><p>{advisor.reasons.join(" ")}</p></div><div className="advisor-grid"><div><small>Contexte</small><b>{advisor.context}</b></div><div><small>Batch</small><b>{advisor.batch}</b></div><div><small>Rank</small><b>{advisor.rank}</b></div><div><small>Modules</small><b>{advisor.modules}</b></div></div>{advisor.warnings.map((w,i)=><div className="warning" key={i}>{w}</div>)}</div>}
        </div>
      </section>}

      {tab==="training"&&<section className="page">
        <div className="section-head"><div><span className="section-kicker">TRAINING LAB</span><h3>Entraînement local réel</h3><p>{project?.model_id&&models.find(m=>m.id===project.model_id)?.format==="transformers"?"LoRA réel via Transformers + PEFT, checkpoints et adaptateur portable.":"LoRA/SFT réel via llama.cpp, avec checkpoints et adaptateur GGUF exportable."}</p></div><div className="inline-actions">{training&&<button onClick={stopTraining}>Arrêter</button>}{project?.adapter_path&&<button onClick={mergeFinal} disabled={training}>Générer le modèle final</button>}<button className="primary-btn" onClick={startTraining} disabled={!project||!project.dataset_path||training}>{training?"En cours…":"Lancer l'entraînement"}</button></div></div>
        <div className="training-summary"><div><small>Projet</small><b>{project?.name||"—"}</b></div><div><small>Modèle</small><b>{project?.model_id||"—"}</b><small>{models.find(m=>m.id===project?.model_id)?.backend||"—"}</small></div><div><small>Dataset</small><b>{project?.examples||0}</b></div><div><small>GPU</small><b>{hardware?.vulkan||"—"}</b></div></div>
        <div className="terminal"><div className="terminal-head"><span>TRAINING LOG</span><span>{training?"RUNNING":"IDLE"}</span></div><pre>{trainingLog.length?trainingLog.join("\n"):"Les sorties réelles du moteur apparaîtront ici pendant l'entraînement."}</pre></div>
      </section>}

      {tab==="evaluation"&&<section className="page">
        <div className="section-head"><div><span className="section-kicker">EVALUATION LAB</span><h3>Tester l'IA comme un utilisateur</h3><p>Vanelle envoie plusieurs scénarios à l'IA et vérifie objectivement les réponses et les contraintes définies.</p></div><div className="inline-actions"><button onClick={improve} disabled={!evalReport?.failed}>Corriger les échecs</button><button className="primary-btn" onClick={evaluate} disabled={!project}>Lancer les tests</button></div></div>
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">AI EVOLUTION</span><h3>Améliorer automatiquement</h3></div><button className="primary-btn" onClick={runEvolution} disabled={!project||!project.dataset_path||evolutionRunning}>{evolutionRunning?"Évolution en cours…":"Lancer AI Evolution"}</button></div>
          <p>Benchmark indépendant → détection des erreurs → corrections → réentraînement réel → nouveau benchmark. Vanelle ne considère l'IA meilleure que si le score augmente réellement.</p>
          {evolutionReport?.error&&<div className="warning">{evolutionReport.error}</div>}
          {evolutionReport?.before&&<div className="stat-grid"><div className="stat"><span>AVANT</span><b>{evolutionReport.before.average_score}%</b><small>{evolutionReport.before.failed} échec(s)</small></div>{evolutionReport.after&&<div className="stat"><span>APRÈS</span><b>{evolutionReport.after.average_score}%</b><small>{evolutionReport.after.failed} échec(s)</small></div>}<div className="stat"><span>RÉSULTAT</span><b>{evolutionReport.after?(evolutionReport.improved?"AMÉLIORÉ":"NON AMÉLIORÉ"):"—"}</b><small>{evolutionReport.corrections||0} correction(s)</small></div></div>}
          {evolutionReport?.message&&<div className={evolutionReport.improved?"runtime-box ready":"runtime-box"}><b>{evolutionReport.message}</b></div>}
        </div>
        <div className="scenario-grid">{tests.map((t,i)=><div className="scenario" key={i}><span>{String(i+1).padStart(2,"0")}</span><b>{t.name}</b><p>{t.persona}</p><small>{t.prompt}</small></div>)}</div>
        {evalReport&&<div className="report"><div className="report-head"><div><span className="section-kicker">TEST REPORT</span><h3>{evalReport.average_score}% score moyen</h3></div><span>{evalReport.passed} réussis · {evalReport.failed} échecs</span></div>{evalReport.results.map((r,i)=><details className={r.passed?"result pass":"result fail"} key={i}><summary><b>{r.name}</b><span>{r.score}%</span></summary><p>{r.response}</p>{r.reasons.length>0&&<ul>{r.reasons.map((x,n)=><li key={n}>{x}</li>)}</ul>}</details>)}</div>}
      </section>}

      {tab==="vision"&&<section className="page">
        <div className="section-head"><div><span className="section-kicker">VISION LAB</span><h3>Reconnaissance d'images locale</h3><p>Importez vos classes d'images, entraînez un vrai classifieur de vision, mesurez-le sur un holdout puis testez une nouvelle image.</p></div>
          <div className="inline-actions"><button onClick={checkVisionRuntime}>Vérifier le moteur vision</button><button className="primary-btn" onClick={importVisionDataset}>Importer le dataset</button></div></div>
        {visionRuntime&&<div className={visionRuntime.ready?"runtime-box ready":"runtime-box"}><b>PyTorch + TorchVision</b><span>{visionRuntime.ready?"Disponible":"Non prêt"}</span><small>{visionRuntime.detail||"—"}</small></div>}
        <div className="stat-grid">
          <div className="stat"><span>IMAGES</span><b>{vision?.images||0}</b><small>images importées localement</small></div>
          <div className="stat"><span>CLASSES</span><b>{vision?.classes?.length||0}</b><small>{vision?.classes?.slice(0,4).join(" · ")||"Aucune classe"}</small></div>
          <div className="stat"><span>MODÈLE</span><b>MobileNetV3 Small</b><small>transfer learning local</small></div>
          <div className="stat"><span>HOLDOUT</span><b>{vision?.best_accuracy!=null?Math.round(vision.best_accuracy*100)+"%":"—"}</b><small>{vision?.status||"Pas encore entraîné"}</small></div>
        </div>
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">TEST ONLY</span><h3>Tester sans entraîner</h3></div><div className="inline-actions"><button onClick={importVisionTestDataset}>Importer benchmark</button><button className="primary-btn" onClick={runVisionTestOnly} disabled={!vision?.checkpoint_path||!visionTest?.dataset_path||training}>Lancer le test</button></div></div>
          <p>Ce benchmark est séparé des données d'entraînement. Vanelle mesure les erreurs sans modifier le modèle : précision globale, précision par classe, matrice de confusion et erreurs à forte confiance.</p>
          <div className="stat-grid">
            <div className="stat"><span>BENCHMARK</span><b>{visionTest?.images||0}</b><small>{visionTest?.status||"Aucun benchmark"}</small></div>
            <div className="stat"><span>ACCURACY</span><b>{visionTestReport?Math.round((visionTestReport.accuracy||0)*100)+"%":"—"}</b><small>sur le benchmark indépendant</small></div>
            <div className="stat"><span>ERREURS</span><b>{visionTestReport?.errors??visionTest?.errors??0}</b><small>images mal classées</small></div>
            <div className="stat"><span>CONFIANCE</span><b>{visionTestReport?.high_confidence_errors??"—"}</b><small>erreurs ≥ 80% de confiance</small></div>
          </div>
          {visionTestReport&&<div className="report"><div className="report-head"><div><span className="section-kicker">DIAGNOSTIC</span><h3>{Math.round((visionTestReport.accuracy||0)*100)}% de précision</h3></div><span>{visionTestReport.errors} erreur(s)</span></div>
            <div className="vision-pre"><b>Matrice de confusion</b><pre>{JSON.stringify(visionTestReport.confusion_matrix||[],null,2)}</pre></div>
            <div className="vision-pre"><b>Classes</b><pre>{JSON.stringify(visionTestReport.per_class||{},null,2)}</pre></div>
            {visionTestReport.errors>0&&<div className="inline-actions"><button className="primary-btn" onClick={makeVisionCorrections}>Créer le jeu de corrections</button><span className="empty-note">Les erreurs restent séparées : pour mesurer une amélioration sans biais, utilisez un nouveau benchmark après correction.</span></div>}
          </div>}
        </div>
        <div className="two-col">
          <div className="panel">
            <div className="panel-head"><div><span className="section-kicker">DATASET FORMAT</span><h3>Un dossier par classe</h3></div><button onClick={importVisionDataset}>Remplacer</button></div>
            <p>Exemple : <b>dataset/chat/</b>, <b>dataset/chien/</b>, <b>dataset/voiture/</b>. Vanelle copie uniquement les fichiers image supportés et conserve les classes.</p>
            <div className="chip-row">{(vision?.classes||[]).map(x=><span key={x}>{x}</span>)}</div>
          </div>
          <div className="panel">
            <div className="panel-head"><div><span className="section-kicker">TRAINING</span><h3>Entraîner réellement</h3></div></div>
            <p>Le moteur utilise PyTorch + TorchVision, avec un backbone MobileNetV3 pré-entraîné et une tête adaptée à vos classes.</p>
            <div className="inline-actions"><button onClick={evaluateVision} disabled={!vision?.checkpoint_path||training}>Évaluer le holdout</button><button className="primary-btn" onClick={trainVision} disabled={!vision?.dataset_path||training}>{training?"En cours…":"Lancer l'entraînement"}</button></div>
          </div>
        </div>
        {visionReport&&<div className="panel"><div className="panel-head"><div><span className="section-kicker">VISION REPORT</span><h3>{Math.round((visionReport.accuracy||0)*100)}% de précision sur les images de validation</h3></div><span>{visionReport.images} images évaluées</span></div><pre className="vision-pre">{JSON.stringify(visionReport.per_class||{},null,2)}</pre></div>}
        <div className="panel">
          <div className="panel-head"><div><span className="section-kicker">LIVE PREDICTION</span><h3>Tester une nouvelle image</h3></div><button className="primary-btn" onClick={predictVision} disabled={!vision?.checkpoint_path}>Choisir une image</button></div>
          {visionPrediction?<div className="prediction"><div><small>PRÉDICTION</small><b>{visionPrediction.predicted?.label||"—"}</b><span>{Math.round((visionPrediction.predicted?.confidence||0)*100)}% de confiance</span></div><div><small>TOP-5</small>{(visionPrediction.top_k||[]).map((x,i)=><span key={i}>{x.label} · {Math.round(x.confidence*100)}%</span>)}</div></div>:<p>Après entraînement, choisissez une image extérieure au dataset pour vérifier ce que le modèle reconnaît.</p>}
        </div>
        <div className="terminal"><div className="terminal-head"><span>VISION TRAINING LOG</span><span>{training?"RUNNING":"IDLE"}</span></div><pre>{trainingLog.length?trainingLog.join("\n"):"Les sorties réelles du moteur vision apparaîtront ici."}</pre></div>
      </section>}

      {tab==="chat"&&<section className="chat-page">
        <div className="chat-scroll">{active?.messages?.length?active.messages.map((m,i)=><article className={"chat-message "+m.role} key={i}><span>{m.role==="user"?"VOUS":m.role==="assistant"?"VANELLE":"CONTEXTE"}</span><p>{m.content||(busy&&i===active.messages.length-1?"Génération…":"")}</p></article>):<div className="chat-empty"><span>LOCAL CHAT</span><h2>Parlez au modèle actif.</h2><p>Vos conversations restent dans le profil local de Vanelle.</p></div>}</div>
        <div className="composer"><textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}}} placeholder={model?"Écrivez votre message…":"Importez un modèle compatible…"}/><div><span>{hardware?.gpu||"GPU —"} · {hardware?.ram||"RAM —"}</span><button className="primary-btn" disabled={busy||!input.trim()} onClick={send}>Envoyer</button></div></div>
      </section>}

      {tab==="settings"&&null}
    </main>
  </div>
}
createRoot(document.getElementById("root")).render(<App/>);