const API=window.KINOA_API||"http://localhost:8000";
const $=id=>document.getElementById(id);
$("projectForm").addEventListener("submit",async e=>{
 e.preventDefault(); $("status").textContent="CREATING"; $("result").textContent="Création et sauvegarde du projet...";
 try{
  const r=await fetch(API+"/api/projects",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
   idea:$("idea").value,title:$("title").value||null,genre:$("genre").value,duration_minutes:Number($("duration").value),visual_style:$("style").value
  })});
  const data=await r.json(); if(!r.ok) throw new Error(data.detail||"API error");
  $("status").textContent="READY"; $("result").textContent=JSON.stringify({id:data.id,title:data.title,status:data.status,film_bible:data.film_bible},null,2);
 }catch(err){$("status").textContent="ERROR";$("result").textContent=err.message}
});