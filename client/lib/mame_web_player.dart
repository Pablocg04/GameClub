import 'dart:convert';
import 'gamepad_script.dart';
import 'player_host.dart' show PlayerSession;

String mameWebHtml(PlayerSession session) {
  String js(Object? value) => jsonEncode(value).replaceAll('<', r'\u003c');
  final driver = session.mameDriver!;
  final code = (session.game['filename'] as String)
      .replaceFirst(RegExp(r'\.zip$', caseSensitive: false), '');
  final base = '/session/${session.id}';
  final fastTv = session.television && session.fastTelevision;
  return '''<!doctype html><html lang="es"><head><meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>html,body{margin:0;width:100%;height:100%;background:#10111c;color:white;font-family:sans-serif;overflow:hidden}
  #canvas{width:100%;height:${session.television ? '100%' : '85%'};object-fit:contain;display:block}
  #start{position:absolute;inset:35% 25%;font-size:22px;background:#8c7aff;color:white;border:0;border-radius:16px}
  #controls{position:absolute;bottom:0;width:100%;display:${session.television ? 'none' : 'flex'};gap:4px;flex-wrap:wrap;justify-content:center}
  #controls button{background:#25273d;color:white;border:1px solid #8c7aff;border-radius:8px;padding:10px;touch-action:none}
  #status{position:absolute;top:0;left:0;right:0;text-align:center;background:#10111c}</style></head><body>
  <canvas id="canvas" tabindex="0"></canvas><div id="status"></div><button id="start" class="ejs_start_button">Iniciar juego</button>
  <div id="controls"></div><script>
  const send=(event,message)=>{
    const data=JSON.stringify({event,message,session:${js(session.id)}});
    if(window.GameClub) window.GameClub.postMessage(data);else window.chrome?.webview?.postMessage(data);
  };
  const status=text=>document.getElementById('status').textContent=text;
  const canvas=document.getElementById('canvas');
  let starting=false,loaded=false,failed=false,configuring=false;
  window.__mameLogs=[];
  // Retropad → teclas estándar de apuestas, cartas y navegación MAME.
  const keys={0:27,1:25,2:34,3:30,4:82,5:81,6:80,7:79,8:29,9:6,10:5,11:31,12:17,13:16,14:20,15:19};
  function key(index,value) {
    if(!loaded||!window.JSMAME)return;
    let scan=keys[index];
    if(configuring && index===8)scan=40;
    if(configuring && index===0)scan=41;
    if(scan!==undefined) JSMAME.sdl_sendkeyboardkey(value?1:0,scan);
  }
  window.EJS_emulator={started:false,paused:false,gameManager:{
    simulateInput:(_,index,value)=>key(index,value),
    screenshot:()=>new Promise(resolve=>requestAnimationFrame(()=>{
      const data=canvas.toDataURL('image/png').split(',')[1];
      resolve(Uint8Array.from(atob(data),value=>value.charCodeAt(0)));
    })),
    toggleMainLoop:active=>{if(active)Module.resumeMainLoop();else Module.pauseMainLoop();}
  }};
  ${session.nativeGamepad ? nativeGamepadJavascript(analogConsole: false) : ''}
  window.gameclubConfigureControls=()=>{
    if(!loaded)return;
    window.gameclubReleaseControllers?.();configuring=!configuring;
    JSMAME.sdl_sendkeyboardkey(1,43);setTimeout(()=>JSMAME.sdl_sendkeyboardkey(0,43),100);
    status(configuring?'Controles MAME: cruceta para navegar, A para aceptar y B para retroceder. Pulsa Configurar otra vez para volver.':'');
    canvas.focus();
  };
  function encode(bytes) {
    let text='';for(let i=0;i<bytes.length;i+=8192)text+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(text);
  }
  function saveFiles() {
    const output={};
    const walk=path=>{
      for(const name of FS.readdir('/'+path)) {
        if(name==='.'||name==='..')continue;
        const relative=path+'/'+name,full='/'+relative;
        if(FS.isDir(FS.stat(full).mode))walk(relative);else output[relative]=encode(FS.readFile(full));
      }
    };
    for(const directory of ['nvram','cfg','sta']) {try{walk(directory);}catch(_){} }
    return output;
  }
  window.gameclubExit=async()=>{
    if(window.gameclubLeaving)return;
    window.gameclubLeaving=true;window.gameclubReleaseControllers?.();
    try {
      if(loaded) {
        Module.resumeMainLoop();JSMAME.exit();
        await new Promise(resolve=>setTimeout(resolve,1000));
        const response=await fetch(${js('$base/mame-save')},{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(saveFiles())});
        if(!response.ok)throw new Error('No se pudo guardar MAME');
      }
      send('exit','');
    }catch(error){window.gameclubLeaving=false;send('save-error',String(error));}
  };
  const log=text=>{
    window.__mameLogs.push(String(text));
    if(/NOT FOUND|Required files are missing|Fatal error|Unknown system|Error loading ROM|incorrect checksum/i.test(String(text))) {
      failed=true;status(String(text));send('core-failed',String(text));
    }
  };
  async function start() {
    if(starting)return;starting=true;document.getElementById('start').remove();
    status('Preparando MAME web…');send('core-loading','');
    try {
      const response=await fetch(${js('$base/rom/${Uri.encodeComponent(session.game['filename'] as String)}')});
      if(!response.ok)throw new Error('No se pudo descargar la ROM');
      const rom=new Uint8Array(await response.arrayBuffer());
      const saved=await (await fetch(${js('$base/mame-save')})).json();
      window.Module={canvas,arguments:[${js(code)},'-rompath','/roms','-nvram_directory','/nvram','-cfg_directory','/cfg','-state_directory','/sta','-window','-nokeepaspect','-resolution',${js(fastTv ? '512x224' : '1024x448')},'-skip_gameinfo','-video','soft'${fastTv ? ",'-frameskip','2','-samplerate','22050','-nowaitvsync','-throttle'" : ''}],
        locateFile:name=>${js('/engine/mame-web/$driver/')}+name,print:log,printErr:log,
        preRun:[()=>{
          for(const path of ['/roms','/nvram','/cfg','/sta']) {try{FS.mkdir(path);}catch(_){} }
          FS.writeFile(${js('/roms/${session.game['filename']}')},rom);
          for(const [path,data] of Object.entries(saved)) {
            const parts=path.split('/');let parent='';
            for(const part of parts.slice(0,-1)){parent+='/'+part;try{FS.mkdir(parent);}catch(_){} }
            FS.writeFile('/'+path,Uint8Array.from(atob(data),value=>value.charCodeAt(0)));
          }
        }],onAbort:error=>{if(!window.gameclubLeaving){failed=true;send('core-failed',String(error));}},
        onExit:value=>{if(value && !window.gameclubLeaving){failed=true;send('core-failed','MAME no pudo iniciar la máquina ('+value+')');}}};
      const script=document.createElement('script');script.src=${js('/engine/mame-web/$driver/mame$driver.js')};
      script.onerror=()=>{failed=true;send('core-failed','No se pudo descargar el motor MAME');};document.body.appendChild(script);
      let checks=0;
      const probe=setInterval(()=>{
        if(failed||window.gameclubLeaving){clearInterval(probe);return;}
        try {
          if(window.JSMAME?.get_machine() && ++checks>=4) {
            clearInterval(probe);loaded=true;EJS_emulator.started=true;status('');canvas.focus();
            ${fastTv ? 'JSMAME.ui_set_show_fps(JSMAME.get_ui(),1);' : ''}
            ${session.television ? """
            let presentation=0,last=0,time=performance.now();
            const tick=()=>{if(window.gameclubLeaving)return;presentation++;requestAnimationFrame(tick);};requestAnimationFrame(tick);
            setInterval(()=>{if(window.gameclubLeaving||EJS_emulator.paused)return;
              const now=performance.now(),fps=Math.round((presentation-last)*1000/(now-time));last=presentation;time=now;
              send('performance',JSON.stringify({system:'mame_web',fps:'—',presentationFps:fps}));
            },3000);
            """ : ''}
            window.gameclubRefreshControllers?.();send('started','mame_web');
          }
        }catch(_){}
      },500);
    }catch(error){failed=true;status(String(error));send('core-failed',String(error));}
  }
  const controls=document.getElementById('controls');
  for(const [label,index] of [['↑',4],['↓',5],['←',6],['→',7],['Moneda',2],['Inicio',3],['Apuesta',11],['Hold 1',8],['Hold 2',0],['Hold 3',9],['Hold 4',1],['Hold 5',10]]) {
    const button=document.createElement('button');button.textContent=label;
    button.onpointerdown=event=>{event.preventDefault();button.setPointerCapture(event.pointerId);key(index,1);};
    button.onpointerup=()=>key(index,0);button.onpointercancel=()=>key(index,0);controls.appendChild(button);
  }
  document.getElementById('start').onclick=start;
  send('ready','Pulsa Iniciar juego. MAME usa 5 para moneda, 1 para inicio, Z/X/C/V/B para cartas y Tab para configurar controles.');
   start();
  </script></body></html>''';
}
