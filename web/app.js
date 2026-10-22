const $ = id => document.getElementById(id);
const labels = {front:'Front',left:'Left side',back:'Back',right:'Right side'};
const files = new Map(), objectURLs = new Map();
const extras = [];
let nextExtra = 1;
let jobs = [], selected = null, loadedMesh = null, viewer = null, autoSelect = true;
const token = document.querySelector('meta[name="local3d-token"]').content;
const text = (tag, value, className) => {const node = document.createElement(tag); node.textContent = value; if(className) node.className=className; return node;};
function toast(message){$('toast').textContent=message;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,4500);}
function error(message){$('form-error').textContent=message;$('form-error').hidden=!message;}
function updateModelNote(){const count=files.size+extras.length;$('candidate-count').textContent=`${count} / 16 images`;$('model-note').textContent=count ? `${count} uploaded candidate${count===1?'':'s'} → at most ${Math.min(count,4)} selected model inputs. See the job's selection report.` : 'Up to 16 candidate photos → at most 4 selected model inputs';if(!$('generate').disabled)$('generate').replaceChildren(document.createTextNode(extras.length?'Select views & generate ':'Generate asset '),text('span','↗'));}
function fileError(file,replacingView=null){
  if(file.size>12*1024*1024)return 'Please use images smaller than 12 MB each.';
  if(!['image/jpeg','image/png','image/webp'].includes(file.type))return 'Choose a JPEG, PNG or WebP image.';
  const count=files.size+extras.length-(replacingView&&files.has(replacingView)?1:0);
  if(count>=16)return 'Upload at most 16 photos in total.';
  const bytes=[...files].reduce((sum,[view,item])=>sum+(view===replacingView?0:item.size),0)+extras.reduce((sum,item)=>sum+item.file.size,0)+file.size;
  if(bytes>48*1024*1024)return 'Combined image size must be at most 48 MB.';
  return null;
}
function setFile(view,file){
  const problem=fileError(file,view);if(problem){error(problem);return;}
  files.set(view,file);if(objectURLs.has(view))URL.revokeObjectURL(objectURLs.get(view));
  objectURLs.set(view,URL.createObjectURL(file));renderSlot(view);updateModelNote();error('');
}
function renderSlot(view){
  const slot=$(`slot-${view}`);slot.replaceChildren();
  const input=document.createElement('input');input.type='file';input.accept='image/jpeg,image/png,image/webp';input.id=`file-${view}`;input.setAttribute('aria-label',`Upload ${labels[view]} view`);
  input.onchange=()=>{if(input.files[0])setFile(view,input.files[0]);};slot.append(input);
  if(files.has(view)){
    const image=document.createElement('img');image.src=objectURLs.get(view);image.alt=`${labels[view]} reference`;slot.append(image);
    const remove=text('button','×','remove-view');remove.type='button';remove.setAttribute('aria-label',`Remove ${labels[view]} view`);remove.onclick=e=>{e.preventDefault();e.stopPropagation();files.delete(view);URL.revokeObjectURL(objectURLs.get(view));objectURLs.delete(view);renderSlot(view);updateModelNote();};slot.append(remove,text('span',labels[view],'image-label'));
  }else slot.append(text('span',view==='front'?'REQUIRED':'OPTIONAL','tag'),text('span','＋','add'),text('strong',`${labels[view]} view`),text('small','Drop image or click to upload'));
  slot.onclick=e=>{if(e.target!==input&&e.target.tagName!=='BUTTON')input.click();};
  slot.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();input.click();}};
  slot.ondragover=e=>{e.preventDefault();slot.classList.add('dragging');};slot.ondragleave=()=>slot.classList.remove('dragging');slot.ondrop=e=>{e.preventDefault();slot.classList.remove('dragging');if(e.dataTransfer.files[0])setFile(view,e.dataTransfer.files[0]);};
}
for(const view of Object.keys(labels)){const slot=document.createElement('div');slot.className='view-slot';slot.id=`slot-${view}`;slot.tabIndex=0;slot.setAttribute('role','button');slot.setAttribute('aria-label',`Upload ${labels[view]} view`);$('view-grid').append(slot);renderSlot(view);}
function renderExtras(){
  $('extra-list').replaceChildren();
  for(const item of extras){const row=text('div','','extra-row');const image=document.createElement('img');image.src=item.url;image.alt=item.file.name;const info=text('div','','extra-info');info.append(text('strong',item.file.name),text('small','View detected automatically from your references'));const remove=text('button','Remove','secondary');remove.type='button';remove.setAttribute('aria-label',`Remove extra photo ${item.file.name}`);remove.onclick=()=>{extras.splice(extras.indexOf(item),1);URL.revokeObjectURL(item.url);renderExtras();updateModelNote();};row.append(image,info,remove);$('extra-list').append(row);}
}
$('add-extras').onclick=()=>$('extra-input').click();
function addExtras(incoming){let problem=null;for(const file of incoming){const issue=fileError(file);if(issue){problem=issue;break;}extras.push({id:nextExtra++,file,url:URL.createObjectURL(file)});}renderExtras();updateModelNote();error(problem||'');}
$('extra-input').onchange=()=>{addExtras($('extra-input').files);$('extra-input').value='';};
const extraDrop=$('extra-drop');
extraDrop.onclick=e=>{if(e.target!==$('add-extras'))$('extra-input').click();};
extraDrop.onkeydown=e=>{if(e.target===extraDrop&&(e.key==='Enter'||e.key===' ')){e.preventDefault();$('extra-input').click();}};
extraDrop.ondragover=e=>{e.preventDefault();extraDrop.classList.add('dragging');};
extraDrop.ondragleave=()=>extraDrop.classList.remove('dragging');
extraDrop.ondrop=e=>{e.preventDefault();extraDrop.classList.remove('dragging');addExtras(e.dataTransfer.files);};
function base64(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});}
async function api(path,data){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Local3D-Token':token},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result;}
$('create-form').onsubmit=async event=>{
  event.preventDefault();error('');if(!files.has('front')){error('Add a front view before generating.');$('slot-front').focus();return;}
  $('generate').disabled=true;$('generate').textContent='Adding to queue…';
  try{const views={};for(const [view,file] of files)views[view]=await base64(file);
    const extra_views=[];for(const item of extras)extra_views.push({image:await base64(item.file),name:item.file.name.slice(0,80)});
    const result=await api('/api/jobs',{name:$('name').value,views,extra_views,view_strategy:'hybrid_vision_v1',settings:{quality:$('quality').value,background:$('background').value,planner:$('planner').value,max_attempts:Number($('attempts').value),triangles:Number($('triangles').value),height:Number($('height').value),allow_flat:$('allow-flat').checked}});
    selected=result.id;await refresh();$('result').scrollIntoView({behavior:'smooth',block:'start'});toast('Added to the local generation queue.');
  }catch(e){error(e.message);}finally{$('generate').disabled=false;updateModelNote();}
};
$('demo').onclick=async()=>{try{for(const url of objectURLs.values())URL.revokeObjectURL(url);files.clear();objectURLs.clear();for(const item of extras)URL.revokeObjectURL(item.url);extras.length=0;renderExtras();for(const view of Object.keys(labels))renderSlot(view);updateModelNote();for(const view of ['front','left','back']){const response=await fetch(`/api/demo/${view}`);if(!response.ok)throw new Error('Example images are not installed.');setFile(view,new File([await response.blob()],`${view}.png`,{type:'image/png'}));}$('name').value='Example · multi-view asset';$('background').value='keep';toast('Three official example views loaded. Click Generate asset.');}catch(e){error(e.message);}};
$('new-project').onclick=()=>{selected=null;autoSelect=false;$('result').hidden=true;$('name').focus();window.scrollTo({top:0,behavior:'smooth'});renderHistory();};
$('cancel').onclick=async()=>{if(!selected)return;try{await api(`/api/jobs/${selected}/cancel`,{});toast('Cancellation requested.');await refresh();}catch(e){toast(e.message);}};
function renderHistory(){const history=$('history');history.replaceChildren();$('job-count').textContent=jobs.length;
  if(!jobs.length)history.append(text('p','Your generations will appear here.','muted small'));
  for(const job of jobs){const button=document.createElement('button');if(job.id===selected)button.className='selected';button.append(text('strong',job.name),text('small',`${job.state==='running'?(job.progress?.stage||'starting'):job.state} · ${new Date(job.created_at*1000).toLocaleDateString()}`));button.onclick=()=>{selected=job.id;renderHistory();renderResult();$('result').scrollIntoView({behavior:'smooth',block:'start'});};history.append(button);}
}
function renderResult(){const job=jobs.find(j=>j.id===selected);if(!job){$('result').hidden=true;return;}$('result').hidden=false;$('result-name').textContent=job.name;$('status-pill').textContent=job.state;$('status-pill').className=`status-pill ${job.state}`;
  const names=[['preparing','Prepare views'],['generating','Generate geometry'],['exporting','Export and validate FBX'],['completed','Ready for Unity']];
  const stage=job.progress?.stage;const rank={queued:-1,preparing:0,selecting:0,planning:0,generating:1,checking:1,exporting:2,completed:4}[stage]??-1;
  $('stages').replaceChildren();for(let i=0;i<names.length;i++){const row=text('div','','stage-item');if(job.state==='completed'||i<rank)row.classList.add('done');else if(i===rank&&job.state==='running')row.classList.add('active');row.append(text('span',job.state==='completed'||i<rank?'✓':String(i+1)),document.createTextNode(names[i][1]));$('stages').append(row);}
  $('job-message').textContent=job.error||(job.state==='cancelled'?'Generation cancelled.':job.progress?.message)||(job.state==='queued'?'Waiting for the local worker…':'Starting…');
  $('job-time').textContent=job.report?`${Math.round(job.report.seconds)} seconds · ${job.report.views_used.length} conditioned / ${job.report.submitted_view_count??job.report.views_used.length} submitted photos · ${job.report.export.exported.triangles.toLocaleString()} triangles · ${job.report.export.height_meters} m tall`:`Submitted ${new Date(job.created_at*1000).toLocaleTimeString()}.${['queued','running'].includes(job.state)?' You can close this tab; processing continues.':''}`;
  $('cancel').hidden=!['queued','running'].includes(job.state);$('downloads').replaceChildren();
  if(job.state==='completed')for(const [key,label] of [['fbx','Download FBX ↓'],['package','Unity ZIP ↓'],['blend','Blender'],['report','Report']])if(job.downloads.includes(key)){const link=text('a',label);link.href=`/api/jobs/${job.id}/files/${key}`;$('downloads').append(link);}
  const selectedViews=job.selection?Object.keys(job.selection.selected):job.report?.views_used||job.job?.views||[];
  const viewsKey=job.id+(rank>=1?'ready':'waiting')+JSON.stringify(selectedViews);if($('prepared-views').dataset.key!==viewsKey){$('prepared-views').dataset.key=viewsKey;$('prepared-views').replaceChildren();if(rank>=1)for(const view of selectedViews){const image=document.createElement('img');image.src=`/api/jobs/${job.id}/views/${view}`;image.alt=`Selected ${labels[view]} view`;image.title=labels[view];image.onerror=()=>image.remove();$('prepared-views').append(image);}}
  renderSelection(job);
  const meshKey=job.state==='completed'&&job.downloads.includes('glb')?job.id:null;
  if(meshKey!==loadedMesh){loadedMesh=meshKey;if(meshKey)loadMesh(job.id);else resetViewer();}
}
function renderSelection(job){
  $('selection-details').hidden=!job.selection;if(!job.selection)return;
  const selection=job.selection;$('selection-heading').textContent=`${selection.selected_count} selected / ${selection.submitted_count} submitted photos`;
  $('selection-download').href=`/api/jobs/${job.id}/files/selection`;
  const key=job.id+JSON.stringify(selection.selected);if($('selection-list').dataset.key===key)return;$('selection-list').dataset.key=key;$('selection-list').replaceChildren();
  for(const item of selection.candidates){const row=text('div','',`selection-row ${item.selected_as?'chosen':''}`);if(item.sha256){const image=document.createElement('img');image.src=`/api/jobs/${job.id}/candidates/${item.id}`;image.alt=`Candidate ${item.name}`;row.append(image);}const detail=text('div');const viewpoint=item.direction?labels[item.direction]||item.direction:`${item.azimuth}°`;detail.append(text('strong',`${item.name} · ${viewpoint}`),text('span',item.selected_as?`Selected for ${labels[item.selected_as]}: ${item.reason}`:`Retained, not conditioned: ${item.reason}`));row.append(detail);$('selection-list').append(row);}
}
function resetViewer(){if(viewer)viewer.clear();$('canvas').hidden=true;$('viewer-empty').hidden=false;$('viewer-controls').hidden=true;$('fallback-preview').hidden=true;}
async function loadMesh(jobID){resetViewer();$('viewer-empty').querySelector('p').textContent='Loading mesh…';try{if(!viewer){const module=await import('/viewer.js');viewer=new module.MeshViewer($('canvas'));}await viewer.load(`/api/jobs/${jobID}/files/glb`);if(loadedMesh!==jobID)return;$('canvas').hidden=false;$('viewer-empty').hidden=true;$('viewer-controls').hidden=false;viewer.resize();}catch(e){if(loadedMesh!==jobID)return;$('viewer-empty').hidden=true;$('fallback-preview').src=`/api/jobs/${jobID}/files/preview`;$('fallback-preview').hidden=false;toast('Interactive viewer unavailable; showing the rendered preview.');}}
$('wireframe').onclick=()=>{if(viewer){const enabled=viewer.toggleWireframe();$('wireframe').textContent=enabled?'Solid':'Wireframe';}};
async function refresh(){try{const response=await fetch('/api/jobs');if(!response.ok)throw new Error();jobs=await response.json();if(!selected&&jobs.length&&autoSelect)selected=jobs[0].id;renderHistory();renderResult();$('connection').replaceChildren(text('i','','dot'),document.createTextNode('Local engine connected'));}catch(e){$('connection').textContent='Local app disconnected';}}
await refresh();setInterval(refresh,2000);
