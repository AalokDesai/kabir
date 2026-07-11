// ── Startup: show loader → face auth → main UI ────────────────────────────────
// The Python side controls this via eel calls (hideLoader, showFaceAuth, etc.)
// This file handles the pure JS side: particles on the face-auth screen

window.addEventListener('load', () => {
  // After 1.5s, tell Python we're ready (triggers init())
  setTimeout(() => {
    if (typeof eel !== 'undefined') {
      eel.init()();
    }
  }, 1500);
});

// ── Floating particles on loader ──────────────────────────────────────────────
(function spawnParticles() {
  const loader = document.getElementById('loader');
  if (!loader) return;

  function createParticle() {
    const p = document.createElement('div');
    p.style.cssText = `
      position:absolute;
      width:${2 + Math.random()*3}px;
      height:${2 + Math.random()*3}px;
      background:rgba(0,180,255,${0.2 + Math.random()*0.5});
      border-radius:50%;
      left:${Math.random()*100}%;
      top:${Math.random()*100}%;
      pointer-events:none;
      animation: float-particle ${3 + Math.random()*4}s ease-in-out infinite;
      animation-delay:${Math.random()*3}s;
    `;
    loader.appendChild(p);
    setTimeout(() => p.remove(), 8000);
  }

  // Add keyframes dynamically
  const style = document.createElement('style');
  style.textContent = `
    @keyframes float-particle {
      0%   { opacity:0; transform:translateY(0px); }
      20%  { opacity:1; }
      80%  { opacity:1; }
      100% { opacity:0; transform:translateY(-60px); }
    }
  `;
  document.head.appendChild(style);

  const interval = setInterval(createParticle, 300);
  setTimeout(() => clearInterval(interval), 6000);
})();
