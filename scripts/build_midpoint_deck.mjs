// Build with the presentation runtime's Node and @oai/artifact-tool.
// ARTIFACT_TOOL_MODULE may point to its installed dist/artifact_tool.mjs.
// GROUP_NUMBER remains UNKNOWN until confirmed in Canvas.
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const { Presentation, PresentationFile } = await import(
  process.env.ARTIFACT_TOOL_MODULE || '@oai/artifact-tool'
);
const root = process.cwd();
const out = path.join(root, 'docs/midpoint');
const build = path.join(root, '.aiplatform/presentation-build');
await fs.mkdir(build, { recursive: true });
const p = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const C = { ink: '#152A32', muted: '#51636B', green: '#087E70', pale: '#E7F3EF',
  orange: '#B6601E', amber: '#FFF1DE', gray: '#E4E9EB', white: '#FFFFFF' };
const font = 'Arial';

function text(s, value, x, y, w, h, size=26, color=C.ink, bold=false) {
  const sh = s.shapes.add({ geometry:'textbox', position:{left:x,top:y,width:w,height:h},
    fill:'none', line:{fill:'none',width:0} });
  sh.text = value;
  sh.text.style = { typeface:font, fontSize:size, color, bold, insets:0,
    verticalAlignment:'top', wrap:'square', autoFit:'none' };
  return sh;
}
function base(title, n, dark=false) {
  const s = p.slides.add();
  s.background.fill = dark ? C.ink : C.white;
  text(s,title,64,52,1152,108,44,dark?C.white:C.ink,true);
  text(s,`${n} / 8`,1130,665,86,22,16,dark?'#B7CDC9':C.muted);
  return s;
}
function note(s, timing, narration, sources='') {
  s.speakerNotes.text = `${timing}\n\n${narration}\n\nSources/evidence:\n${sources}`;
}
function block(s,title,body,x,y,w=270,h=98,fill=C.pale) {
  const b=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},
    fill,line:{fill:fill===C.amber?C.orange:C.green,width:1}});
  text(s,title,x+18,y+12,w-36,35,23,C.ink,true);
  if(body) text(s,body,x+18,y+49,w-36,h-55,19,C.muted);
  return b;
}
function connect(s,a,b,from='right',to='left',dash=false) {
  s.shapes.connect(a,b,{kind:'straight',fromSide:from,toSide:to,
    line:{fill:dash?C.orange:C.green,width:2,style:dash?'dashed':'solid'},
    tail:{type:'triangle',width:'med',length:'med'}});
}
function pairs(s,items,x,y,w,step=94) {
  items.forEach(([a,b],i)=>{
    text(s,a,x,y+i*step,w,32,27,C.green,true);
    text(s,b,x,y+37+i*step,w,50,22,C.muted);
  });
}

// 1 — 25 seconds
{
  const s=base('aiplatform',1,true);
  text(s,'Self-service AI infrastructure',64,200,1070,90,54,C.white,true);
  text(s,'Midpoint evaluation\nJohn Cobio',68,345,720,105,29,'#D5E7E1');
  text(s,'A workload configuration becomes a running\nopen-source model with operational visibility.',68,505,1040,100,30,'#D5E7E1');
  note(s,'0:00–0:25 (25 seconds)',
    'My project is aiplatform, a self-service infrastructure platform for open-source model workloads. I am John Cobio. The goal is to give a developer a small configuration file and a repeatable path to deployment, health checks, and operational metrics. Today I will show the implemented prototype, evidence from tests and experiments, and the next cloud milestone.',
    'README.md; docs/ARCHITECTURE.md. Group number needs confirmation for the filename.');
}
// 2 — 35 seconds
{
  const s=base('Problem and developer experience',2);
  pairs(s,[
    ['Repeated infrastructure setup','Model storage, resources and networking differ across deployments.'],
    ['One workload definition','The platform validates the model and its resource requirements.'],
    ['Repeatable operations','Deploy, inspect health, read logs and roll back through a CLI.'],
  ],64,188,568,128);
  const box=block(s,'aiplatform.yaml','',700,185,514,365);
  text(s,'name: document-agent\nmodel: qwen2.5-0.5b-instruct\nengine: llamacpp-server\ncpu: 2\nmemory: 1Gi\nenvironment: dev',724,250,465,265,25,C.ink);
  text(s,'aiplatform deploy --target kind',700,580,520,40,25,C.green,true);
  note(s,'0:25–1:00 (35 seconds)',
    'The problem is the repeated infrastructure work around model serving. A model needs enough memory, an inference engine, storage for its weights, and a way to reach it. This YAML names the model, engine and resource budget. The CLI validates those choices and drives the deployment. The product is the deployment workflow and its operating signals. The language model is a workload the platform manages.',
    'services/qwen-server/aiplatform.yaml; cli/src/aiplatform/config/schema.py; cli/src/aiplatform/targets/kind.py');
}
// 3 — 50 seconds
{
  const s=base('Current prototype architecture',3);
  text(s,'Hosted CI and registry',64,165,530,32,23,C.green,true);
  const ci=block(s,'GitHub Actions','Tests, scans and image build',64,218,300,100);
  const registry=block(s,'GHCR','Published inference images',454,218,300,100);
  connect(s,ci,registry);
  text(s,'Local Kubernetes on kind',64,355,700,32,23,C.green,true);
  const cli=block(s,'CLI + YAML','Validation and deployment',64,414,254,100);
  const deploy=block(s,'Helm / Argo CD','Direct or GitOps delivery',375,414,254,100);
  const model=block(s,'Inference pod','Qwen 0.5B model',686,414,254,100);
  connect(s,cli,deploy); connect(s,deploy,model);connect(s,registry,model,'bottom','top');
  const storage=block(s,'Model cache','Persistent volume',990,414,224,100);
  connect(s,model,storage);
  text(s,'ingress-nginx routes requests to the pod',64,570,700,34,24,C.muted);
  text(s,'Prometheus / Grafana metrics',64,616,550,38,24,C.muted);
  text(s,'OpenTelemetry / Jaeger traces',650,616,560,38,24,C.muted);
  note(s,'1:00–1:50 (50 seconds)',
    'This is the implemented prototype architecture. GitHub Actions runs validation and publishes images to GHCR. Locally, the CLI can deploy directly with Helm or commit desired state for Argo CD to reconcile. Ingress routes requests to an inference pod, which caches model weights on a persistent volume. Prometheus and Grafana expose performance and resource use. The built-in service also exports OpenTelemetry traces to Jaeger. These components have run locally, but Docker is currently stopped on the audit machine, so a live endpoint must be rechecked before the recording.',
    'docs/ARCHITECTURE.md; .github/workflows/ci.yml; .github/workflows/build-image.yml; deploy/helm/llm-workload/; prototype runtime evidence in docs/benchmarks/2026-09-16-v4-observability-baseline.md.');
}
// 4 — 45 seconds
{
  const s=base('AWS midpoint deployment plan',4);
  text(s,'PLANNED — awaiting launch and inference verification',64,165,1140,38,24,C.orange,true);
  const operator=block(s,'Operator IP','Restricted inbound access',64,280,256,108,C.amber);
  const vm=block(s,'EC2 in a public subnet','Permitted t3 instance + Docker',390,280,385,108,C.amber);
  const disk=block(s,'Encrypted EBS','gp2 model cache',884,280,330,108,C.amber);
  connect(s,operator,vm,'right','left',true);connect(s,vm,disk,'right','left',true);
  text(s,'VPC, route table and internet gateway',390,428,700,42,27,C.ink,true);
  text(s,'Public image pull from GHCR\nExisting permitted IAM profile if available',390,489,820,84,25,C.muted);
  text(s,'EKS, ECR, S3 state and GPU nodes remain later milestones',64,612,1135,40,24,C.orange,true);
  note(s,'1:50–2:35 (45 seconds)',
    'The next cloud milestone is deliberately small: an EC2 instance serving a real model, in a public subnet, with a security group limited to my IP and encrypted EBS for the cache. The inspected Academy sandbox restricts IAM to read-only, supports t2 and t3 instances, and requires gp2 storage. ECR and EKS are not listed among its supported services, so the first cloud demo would pull the existing public image from GHCR. This slide shows a plan, not a completed deployment. I will replace that status only after a successful cloud inference request.',
    'Academy Cloud Architecting 3 Sandbox instructions viewed October 15, 2026; docs/midpoint/CLOUD_SETUP.md. Pricing reference https://aws.amazon.com/vpc/pricing/ and https://aws.amazon.com/eks/pricing/.');
}
// 5 — 45 seconds
{
  const s=base('Automation and verification',5);
  text(s,'126',64,190,400,115,100,C.green,true);
  text(s,'Python tests passed in the October 15 audit',64,315,470,100,30,C.ink);
  text(s,'112 CLI tests + 14 service tests',64,445,520,45,25,C.muted);
  pairs(s,[
    ['Infrastructure checks','Terraform formatting and validation across six roots/modules.'],
    ['Deployment checks','Helm render checks for built-in, llama.cpp and vLLM configurations.'],
    ['Security and policy','Conftest suites and image scanning in GitHub Actions.'],
  ],650,194,560,130);
  text(s,'Fresh local checks pass. Remote CI needs rechecking after the zone-selection repair.',64,615,1130,45,21,C.orange);
  note(s,'2:35–3:20 (45 seconds)',
    'The platform has automation beyond the inference endpoint. The fresh audit passed 112 CLI and 14 service tests. Terraform formatting and validation, chart render checks, and policy suites also passed. I found that the most recent remote CI run failed a new Checkov rule because the availability-zone lookup was unfiltered. The repair pins the zone identities and passes the local scan. The lesson is to verify the current pipeline rather than rely on an old green badge. Terraform validation is still distinct from proving a cloud apply.',
    'October 15 make check: 112 CLI + 14 service tests, six Terraform checks, chart checks and policy checks; Checkov reproduced CKV_AWS_394 then passed 83 checks after explicit zone-name filter. Latest inspected run https://github.com/johncobio/aiplatform/actions/runs/35232704084');
}
// 6 — 40 seconds
{
  const s=base('Measured prototype performance',6);
  text(s,'Completion tokens per second at one virtual user',64,170,1120,42,28,C.muted);
  s.charts.add('bar',{
    position:{left:64,top:248,width:710,height:305},
    categories:['Built-in service','Upstream llama.cpp'],
    series:[{name:'Completion tokens/s',values:[16.4,47.6],fill:C.green}],
    hasLegend:false,barOptions:{direction:'bar',grouping:'clustered',gapWidth:90},
    dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:font,fontSize:23}},
    xAxis:{textStyle:{typeface:font,fontSize:20}},
    yAxis:{minimumScale:0,maximumScale:55,textStyle:{typeface:font,fontSize:18}},
  });
  pairs(s,[['0.80 s','Upstream llama.cpp P95 latency'],['12.5 s','Endpoint recovery after a pod kill']],842,260,360,137);
  text(s,'Historical local runs, September 16, 2026. Qwen 0.5B, 2 CPU threads, 32 output tokens.',64,595,1140,43,21,C.muted);
  text(s,'Engine builds differ. These results are not AWS benchmarks or production guarantees.',64,643,1120,30,19,C.muted);
  note(s,'3:20–4:00 (40 seconds)',
    'These are recorded local experiments from September 16. With the Qwen 0.5B model, two CPU threads and one virtual user, the upstream llama.cpp server produced 47.6 completion tokens per second and a P95 response latency of 0.80 seconds. The built-in service recorded 16.4 tokens per second. The engine builds and serving setup differ, so this is an observed comparison, not proof that one specific optimisation caused the gap. A separate pod-deletion experiment measured endpoint recovery at 12.5 seconds.',
    'docs/benchmarks/2026-09-16-v6-engines.md; docs/benchmarks/2026-09-16-v8-reliability.md');
}
// 7 — 35 seconds
{
  const s=base('Challenges and remaining work',7);
  text(s,'Challenge',64,180,500,40,29,C.green,true);
  text(s,'Response and next milestone',610,180,600,40,29,C.green,true);
  const rows=[
    ['Laptop memory and CPU pressure','One workload at a time, pre-pulled images, paused add-ons.'],
    ['Academy service and IAM restrictions','Verify a small EC2 deployment before attempting EKS.'],
    ['Ingress monitoring blind spot','Add an external probe and retest recovery in AWS.'],
    ['Unverified advanced paths','Test GPU serving and a live proposal provider after midpoint.'],
  ];
  rows.forEach(([a,b],i)=>{ text(s,a,64,250+i*82,480,68,25);text(s,b,610,250+i*82,600,68,24,C.muted); });
  note(s,'4:00–4:35 (35 seconds)',
    'The main challenge has been resource pressure on an eight-gigabyte laptop, so the demo uses one workload and pauses unused add-ons. Academy permissions are another constraint, which is why EC2 is the immediate cloud milestone. The reliability work found an ingress blind spot that needs an external probe. EKS, GPU inference, and the live proposal provider remain unverified. After feedback I will prioritise cloud automation and repeat the load and recovery measurements in the selected account. The final deadline still needs confirmation.',
    'PROJECT_STATUS.md; docs/RELIABILITY.md; docs/benchmarks/2026-09-16-v8-reliability.md; Academy Sandbox instructions.');
}
// 8 — 25 seconds
{
  const s=base('Prototype walkthrough',8,true);
  text(s,'Configuration and validation\nActual model response\nMetrics and deployment evidence\nPolicy rejection and remaining work',64,210,1100,300,37,'#D5E7E1');
  text(s,'github.com/johncobio/aiplatform',64,582,1110,55,33,C.white,true);
  note(s,'4:35–5:00 (25 seconds)',
    'The accompanying demo shows the configuration, validation, an actual model response, and operational evidence. It also shows a rejected policy proposal using the file provider, so the approval guardrails are visible without claiming that a live AI call generated the proposal. The repository is public for review. I would especially welcome feedback on which final milestone matters most: EKS deployment, cloud automation, or deeper reliability measurements.',
    'docs/midpoint/DEMO_WALKTHROUGH.md; examples/proposals/rejected-nat-gateway.json.');
}

const group=process.env.GROUP_NUMBER || 'UNKNOWN';
if(!/^[A-Za-z0-9]+$/.test(group)) throw new Error('GROUP_NUMBER must be alphanumeric');
const draft=path.join(build,'midpoint-draft.pptx');
await (await PresentationFile.exportPptx(p)).save(draft);
for(let i=0;i<p.slides.items.length;i++){
  const png=await p.export({slide:p.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
const finalPath=path.join(out,`Group${group}-aiplatform.pptx`);
if(process.env.PRESENTATION_SKILL_DIR){
  const skill=process.env.PRESENTATION_SKILL_DIR;
  const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
  await finalizePresentation({workspaceDir:build,candidatePath:draft,finalPath,
    pythonExecutable:process.env.PRESENTATION_PYTHON || 'python3',
    integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
    layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
    layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],
    explicitTotalSlideCount:8,requiredNativeChartOwnerSlides:[6],
    // New chart authored from the complete recorded literal data above;
    // embed an editable workbook snapshot for PowerPoint compatibility.
    materializeLiteralChartWorkbooks:true,
    fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
    receiptPath:path.join(build,'validation.json')});
}else{
  await fs.copyFile(draft,finalPath);
}
console.log(finalPath);
