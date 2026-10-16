/// EmulatorJS 4.2.3 entrega el lápiz DeSmuME por ratón; el WebView móvil no
/// sintetiza mousedown mientras se mantiene un dedo. Adaptamos un solo contacto.
const ndsTouchJavascript = r'''
(() => {
  if (window.gameclubNdsTouchInstalled) return;
  window.gameclubNdsTouchInstalled = true;
  const canvas = EJS_emulator.canvas;
  EJS_emulator.gameManager.functions.setVariable('desmume_pointer_type', 'mouse');
  canvas.style.touchAction = 'none';
  let active = null, last = null;
  const mouse = (type, touch) => canvas.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, clientX: touch.clientX, clientY: touch.clientY,
    button: 0, buttons: type === 'mouseup' ? 0 : 1
  }));
  const release = () => {
    if (active !== null && last) mouse('mouseup', last);
    active = null; last = null;
  };
  canvas.addEventListener('touchstart', event => {
    if (active !== null || !event.changedTouches.length) return;
    event.preventDefault();
    last = event.changedTouches[0]; active = last.identifier;
    mouse('mousemove', last); mouse('mousedown', last);
  }, {passive: false});
  canvas.addEventListener('touchmove', event => {
    const touch = Array.from(event.changedTouches).find(t => t.identifier === active);
    if (!touch) return;
    event.preventDefault(); last = touch; mouse('mousemove', touch);
  }, {passive: false});
  for (const type of ['touchend', 'touchcancel']) canvas.addEventListener(type, event => {
    if (!Array.from(event.changedTouches).some(t => t.identifier === active)) return;
    event.preventDefault(); release();
  }, {passive: false});
  window.addEventListener('blur', release);
  document.addEventListener('visibilitychange', () => {if (document.hidden) release();});
  const previous = window.gameclubReleaseControllers;
  window.gameclubReleaseControllers = () => {previous?.(); release();};
})();
''';
