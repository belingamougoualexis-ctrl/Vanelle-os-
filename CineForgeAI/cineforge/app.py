import queue, subprocess, sys, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from .project import new_project, save_project, load_project
from .story import complete_story
from .video import assemble_mp4, ffmpeg_available

class App:
    def __init__(self, root):
        self.root=root; root.title("CineForge AI Studio"); root.geometry("1120x760"); root.configure(bg="#10151f")
        self.project=new_project(); self.path=None; self.clips={}; self.events=queue.Queue()
        style=ttk.Style(); style.theme_use("clam")
        style.configure("TFrame",background="#10151f"); style.configure("TLabel",background="#10151f",foreground="#edf3ff")
        style.configure("TButton",padding=7); style.configure("Treeview",background="#172132",fieldbackground="#172132",foreground="white",rowheight=26)
        header=ttk.Frame(root,padding=14); header.pack(fill="x")
        ttk.Label(header,text="CINEFORGE",font=("Segoe UI",22,"bold")).pack(side="left")
        for label,cmd in [("Nouveau",self.new),("Ouvrir",self.open),("Enregistrer",self.save)]:
            ttk.Button(header,text=label,command=cmd).pack(side="right",padx=3)
        body=ttk.Frame(root,padding=14); body.pack(fill="both",expand=True)
        left=ttk.Frame(body,padding=12); left.pack(side="left",fill="y",padx=(0,12))
        ttk.Label(left,text="1 · TON IDÉE",font=("Segoe UI",13,"bold")).pack(anchor="w")
        self.idea=tk.Text(left,width=37,height=9,wrap="word",bg="#0a1019",fg="white",insertbackground="white",relief="flat")
        self.idea.pack(pady=8); self.idea.insert("1.0","Une jeune mécanicienne découvre un secret dans un vieux cinéma...")
        ttk.Label(left,text="Genre").pack(anchor="w")
        self.genre=ttk.Combobox(left,values=["Drame","Thriller","Science-fiction","Comédie","Aventure","Romance"],state="readonly"); self.genre.set("Drame"); self.genre.pack(fill="x",pady=4)
        ttk.Label(left,text="Durée cible (minutes)").pack(anchor="w")
        self.duration=ttk.Spinbox(left,from_=1,to=120); self.duration.set("3"); self.duration.pack(fill="x",pady=4)
        ttk.Label(left,text="Modèle de texte local Ollama").pack(anchor="w")
        self.model=ttk.Entry(left); self.model.insert(0,"qwen3:4b"); self.model.pack(fill="x",pady=4)
        ttk.Button(left,text="Compléter toute l'histoire",command=self.story).pack(fill="x",pady=5)
        ttk.Separator(left).pack(fill="x",pady=10)
        ttk.Label(left,text="2 · RÉALISATION VIDÉO",font=("Segoe UI",13,"bold")).pack(anchor="w")
        ttk.Button(left,text="Générer la scène sélectionnée",command=self.generate).pack(fill="x",pady=4)
        ttk.Button(left,text="Assembler les clips en MP4",command=self.export).pack(fill="x",pady=4)
        ttk.Label(left,text="Les poids LTX sont volumineux. Aucun clip fictif n'est créé si le modèle échoue.",wraplength=260).pack(anchor="w",pady=6)
        right=ttk.Frame(body); right.pack(side="left",fill="both",expand=True)
        ttk.Label(right,text="SCÈNES",font=("Segoe UI",14,"bold")).pack(anchor="w")
        self.tree=ttk.Treeview(right,columns=("duration","location","status"),show="headings")
        for col,title,width in [("duration","Durée",75),("location","Lieu",200),("status","État vidéo",130)]:
            self.tree.heading(col,text=title); self.tree.column(col,width=width)
        self.tree.pack(fill="both",expand=True,pady=8); self.tree.bind("<<TreeviewSelect>>",self.select)
        ttk.Label(right,text="PROMPT / CONTINUITÉ").pack(anchor="w")
        self.detail=tk.Text(right,height=7,bg="#172132",fg="white",insertbackground="white",relief="flat"); self.detail.pack(fill="x",pady=5)
        ttk.Label(right,text="JOURNAL").pack(anchor="w")
        self.log=tk.Text(right,height=6,bg="#090d14",fg="#b8c8e6",state="disabled"); self.log.pack(fill="x",pady=5)
        self.write("Application prête. FFmpeg: "+("OK" if ffmpeg_available() else "non détecté"))
        self.poll()
    def write(self,msg):
        self.log.configure(state="normal"); self.log.insert("end",str(msg)+"\n"); self.log.see("end"); self.log.configure(state="disabled")
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,s in enumerate(self.project.get("scenes",[])):
            status="Généré" if i in self.clips and Path(self.clips[i]).exists() else "À générer"
            self.tree.insert("","end",iid=str(i),values=(str(s.get("duration_seconds",5))+" s",s.get("location","—"),status))
        if self.project.get("scenes"): self.tree.selection_set("0"); self.select()
    def select(self,_=None):
        sel=self.tree.selection()
        if not sel:return
        s=self.project["scenes"][int(sel[0])]
        text=(s.get("video_prompt") or s.get("action",""))+"\nCaméra: "+str(s.get("camera",""))+"\nLumière: "+str(s.get("lighting",""))+"\nContinuité: "+str(s.get("continuity",""))+"\nDialogue: "+str(s.get("dialogue",""))
        self.detail.delete("1.0","end"); self.detail.insert("1.0",text)
    def story(self):
        try: mins=max(1,min(120,int(self.duration.get())))
        except ValueError: messagebox.showerror("CineForge","Durée invalide"); return
        premise=self.idea.get("1.0","end").strip()
        def work():
            try:self.events.put(("story",complete_story(premise,self.model.get().strip() or "qwen3:4b",self.genre.get(),mins)))
            except Exception as e:self.events.put(("error","Scénario",str(e)))
        self.write("Le modèle local développe le scénario complet…"); threading.Thread(target=work,daemon=True).start()
    def save(self):
        p=self.path or filedialog.asksaveasfilename(defaultextension=".cineforge.json",filetypes=[("CineForge","*.cineforge.json")])
        if not p:return
        save_project(self.project,p); self.path=p; self.write("Projet enregistré: "+p)
    def open(self):
        p=filedialog.askopenfilename(filetypes=[("CineForge","*.cineforge.json *.json")])
        if not p:return
        try:self.project=load_project(p);self.path=p;self.idea.delete("1.0","end");self.idea.insert("1.0",self.project.get("premise",""));self.clips={};self.refresh();self.write("Projet ouvert.")
        except Exception as e:messagebox.showerror("CineForge",str(e))
    def new(self):
        if messagebox.askyesno("CineForge","Créer un nouveau projet ?"):
            self.project=new_project();self.path=None;self.clips={};self.refresh();self.idea.delete("1.0","end");self.detail.delete("1.0","end")
    def generate(self):
        sel=self.tree.selection()
        if not sel:messagebox.showinfo("CineForge","Complète l'histoire et sélectionne une scène.");return
        if not messagebox.askyesno("Téléchargement du modèle","LTX-2.5 peut télécharger plusieurs dizaines de Go. Continuer ?"):return
        idx=int(sel[0]); scene=self.project["scenes"][idx]; prompt=scene.get("video_prompt") or scene.get("action","")
        if not prompt.strip():messagebox.showerror("CineForge","Prompt de scène vide.");return
        outdir=(Path(self.path).parent if self.path else Path.cwd())/"CineForgeRenders";outdir.mkdir(parents=True,exist_ok=True)
        out=outdir/f"scene_{idx+1:03d}.mp4"; script=Path(__file__).resolve().parent.parent/"engine"/"ltx_generate.py"
        def work():
            try:
                cmd=[sys.executable,str(script),"--prompt",prompt,"--output",str(out),"--seconds",str(max(2,min(10,int(scene.get("duration_seconds",5)))))]
                proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace")
                for line in proc.stdout:self.events.put(("log",line.rstrip()))
                code=proc.wait()
                if code or not out.exists() or out.stat().st_size==0:self.events.put(("error","Vidéo",f"Échec du moteur vidéo (code {code})."))
                else:self.events.put(("clip",idx,str(out)))
            except Exception as e:self.events.put(("error","Vidéo",str(e)))
        self.write("Inférence vidéo réelle démarrée…");threading.Thread(target=work,daemon=True).start()
    def export(self):
        clips=[self.clips[i] for i in sorted(self.clips) if Path(self.clips[i]).exists()]
        if not clips:messagebox.showinfo("CineForge","Aucun vrai clip généré.");return
        out=filedialog.asksaveasfilename(defaultextension=".mp4",filetypes=[("MP4","*.mp4")])
        if not out:return
        def work():
            try:self.events.put(("export",str(assemble_mp4(clips,out))))
            except Exception as e:self.events.put(("error","Export MP4",str(e)))
        threading.Thread(target=work,daemon=True).start()
    def poll(self):
        try:
            while True:
                ev=self.events.get_nowait()
                if ev[0]=="story":
                    s=ev[1];self.project.update({"title":s.get("title","Film"),"premise":self.idea.get("1.0","end").strip(),"genre":self.genre.get(),"synopsis":s.get("synopsis",""),"logline":s.get("logline",""),"characters":s.get("characters",[]),"scenes":s["scenes"]});self.clips={};self.refresh();self.write("Histoire complétée: "+self.project["title"]+" — "+str(len(self.project["scenes"]))+" scènes.");self.save()
                elif ev[0]=="clip":self.clips[ev[1]]=ev[2];self.refresh();self.write("Clip vidéo vérifié: "+ev[2])
                elif ev[0]=="export":self.write("Film MP4 exporté: "+ev[1]);messagebox.showinfo("CineForge","Film exporté:\n"+ev[1])
                elif ev[0]=="log":self.write(ev[1])
                elif ev[0]=="error":self.write("ERREUR: "+ev[2]);messagebox.showerror(ev[1],ev[2])
        except queue.Empty:pass
        self.root.after(150,self.poll)

def main():
    root=tk.Tk();App(root);root.mainloop()
