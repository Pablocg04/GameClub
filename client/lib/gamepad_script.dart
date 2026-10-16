/// Adaptador de mandos Android al Retropad de EmulatorJS 4.2.3.
String nativeGamepadJavascript({required bool analogConsole}) => '''
const nativePads=new Map();
function sendNativePad(pad,release=false) {
  const emulator=window.EJS_emulator;
  if(!emulator?.started || !emulator.gameManager) return;
  const values=Array(24).fill(0), axes=pad.axes;
  if(!release) {
    for(const index of pad.buttons) values[index]=1;
    const digitalStick=${!analogConsole};
    if(axes[5]<-.4 || (digitalStick && axes[1]<-.4)) values[4]=1;
    if(axes[5]>.4 || (digitalStick && axes[1]>.4)) values[5]=1;
    if(axes[4]<-.4 || (digitalStick && axes[0]<-.4)) values[6]=1;
    if(axes[4]>.4 || (digitalStick && axes[0]>.4)) values[7]=1;
    if(axes[6]>.3) values[12]=1;
    if(axes[7]>.3) values[13]=1;
    for(const [axis,positive,negative] of [[0,16,17],[1,18,19],[2,20,21],[3,22,23]]) {
      values[positive]=Math.round(Math.max(0,axes[axis])*32767);
      values[negative]=Math.round(Math.max(0,-axes[axis])*32767);
    }
  }
  values.forEach((value,index)=>{
    if(pad.last[index]!==value) emulator.gameManager.simulateInput(pad.slot,index,value);
  });
  pad.last=values;
}
window.gameclubReleaseControllers=()=>{
  for(const pad of nativePads.values()) sendNativePad(pad,true);
  nativePads.clear();
};
window.gameclubControllerInput=events=>{
  for(const event of events) {
    if(event.type==='reset') {window.gameclubReleaseControllers();continue;}
    if(event.type==='disconnect') {
      const pad=nativePads.get(event.device);
      if(pad) sendNativePad(pad,true);
      nativePads.delete(event.device);continue;
    }
    if(!nativePads.has(event.device)) {
      const used=new Set([...nativePads.values()].map(pad=>pad.slot));
      const slot=[0,1,2,3].find(value=>!used.has(value));
      if(slot===undefined) continue;
      nativePads.set(event.device,{slot,buttons:new Set(),axes:Array(8).fill(0),last:[]});
    }
    const pad=nativePads.get(event.device);
    if(event.type==='button' && Number.isInteger(event.index) && event.index>=0 && event.index<16) {
      if(event.pressed) pad.buttons.add(event.index);else pad.buttons.delete(event.index);
    }
    if(event.type==='axes') pad.axes=event.axes.map(value=>Math.max(-1,Math.min(1,Number(value)||0)));
    sendNativePad(pad);
  }
};
window.gameclubRefreshControllers=()=>{
  for(const pad of nativePads.values()) {pad.last=[];sendNativePad(pad);}
};
window.addEventListener('blur',()=>window.gameclubReleaseControllers());
window.addEventListener('pagehide',()=>window.gameclubReleaseControllers());
try {Object.defineProperty(navigator,'getGamepads',{configurable:true,value:()=>[]});}catch(_){}
''';
