/**
 * BookFloatBackground — floating book-cover parallax animation for the home screen.
 *
 * Renders a multi-layer depth parallax of book-cover images using a Canvas 2D context.
 * Mouse drag and scroll-wheel change direction/speed only when the pointer is NOT
 * over any interactive foreground element (input, button, link, etc.).
 *
 * No external dependencies — pure Canvas 2D, no Three.js required.
 */

import { useEffect, useRef } from 'react';


// ── Layer configuration (front → back) ───────────────────────────────────────
const DEPTH_LAYERS = 5;
const MAX_DIM = 160; // px reference size before scale is applied

const LAYER_CONFIG = [
  { scale: 1.50, speed: 80, opacity: 0.95 }, // layer 0 — closest
  { scale: 1.05, speed: 42, opacity: 0.80 },
  { scale: 0.78, speed: 28, opacity: 0.65 },
  { scale: 0.58, speed: 18, opacity: 0.50 },
  { scale: 0.42, speed: 12, opacity: 0.35 }, // layer 4 — furthest
] as const;

// ── Types ─────────────────────────────────────────────────────────────────────
interface Sprite {
  img: HTMLImageElement;
  x: number;
  baseY: number;
  w: number;
  h: number;
  speed: number;
  opacity: number;
  layer: number;
  seed: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function rand(min: number, max: number) {
  return Math.random() * (max - min) + min;
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Tags and ARIA roles that indicate an interactive foreground element.
const INTERACTIVE_TAGS = new Set(['button', 'input', 'a', 'select', 'textarea', 'label']);
const INTERACTIVE_ROLES = new Set([
  'button', 'link', 'menuitem', 'tab', 'textbox', 'combobox',
  'listbox', 'option', 'radio', 'checkbox', 'switch', 'slider',
]);

/**
 * Returns true if (x, y) is over any interactive foreground element.
 * Uses elementsFromPoint which includes pointer-events:none elements, so we
 * only flag elements with interactive semantics — transparent layout divs are ignored.
 */
function isOverForeground(x: number, y: number): boolean {
  const elements = document.elementsFromPoint(x, y);
  for (const el of elements) {
    if (el === document.body || el === document.documentElement) continue;
    const tag = el.tagName?.toLowerCase();
    if (tag && INTERACTIVE_TAGS.has(tag)) return true;
    const role = el.getAttribute('role');
    if (role && INTERACTIVE_ROLES.has(role)) return true;
    // Any element explicitly marked as foreground (e.g. modal, dropdown)
    if (el.getAttribute('data-foreground') === 'true') return true;
  }
  return false;
}

// ── Component ─────────────────────────────────────────────────────────────────
interface Props {
  visible: boolean;
  imageUrls: string[];
}

export function BookFloatBackground({ visible, imageUrls }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (imageUrls.length === 0) return;
    // Capture as non-null — both are confirmed non-null inside this effect.
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    // Non-null alias so nested functions don't re-trigger TS narrowing loss.
    const safeCtx = ctx;

    // ── Mutable animation state kept in a plain object (not React state) ──
    let animId = 0;
    let running = false;
    let lastTime = 0;
    let speedFactor = 1;
    let dragActive = false;
    let lastX = 0;
    let dragVelocity = 0;

    const sprites: Sprite[][] = Array.from({ length: DEPTH_LAYERS }, () => []);
    const loadedImages: HTMLImageElement[] = [];

    // ── Canvas sizing ──────────────────────────────────────────────────────
    function resize() {
      const dpr = Math.min(window.devicePixelRatio ?? 1, 2);
      const w = window.innerWidth;
      const h = window.innerHeight;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      safeCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // ── Sprite factory ─────────────────────────────────────────────────────
    function makeSprite(layerIdx: number, startX: number): Sprite | null {
      const cfg = LAYER_CONFIG[layerIdx];
      const img = loadedImages[Math.floor(Math.random() * loadedImages.length)];
      if (!img) return null;
      const ratio = img.naturalWidth > 0 && img.naturalHeight > 0
        ? img.naturalWidth / img.naturalHeight
        : 0.75; // typical book cover ratio
      let w: number, h: number;
      if (ratio >= 1) {
        w = MAX_DIM * cfg.scale;
        h = w / ratio;
      } else {
        h = MAX_DIM * cfg.scale;
        w = h * ratio;
      }
      const sizeVar = rand(0.85, 1.18);
      w *= sizeVar;
      h *= sizeVar;
      const spacing = w * rand(0.35, 0.75);
      const ch = window.innerHeight;
      const baseY = rand(h / 2 + 20, ch - h / 2 - 20);
      return {
        img,
        x: startX + w / 2 + spacing,
        baseY,
        w,
        h,
        speed: cfg.speed * rand(0.5, 1.25),
        opacity: cfg.opacity * rand(0.9, 1.0),
        layer: layerIdx,
        seed: rand(0, Math.PI * 2000),
      };
    }

    function fillLayer(layerIdx: number) {
      const cw = window.innerWidth;
      // Start sprites off the left edge for the initial fill
      let rightMost = sprites[layerIdx].length > 0
        ? Math.max(...sprites[layerIdx].map(s => s.x + s.w / 2))
        : -cw * 0.1;
      while (rightMost < cw * 1.15) {
        const s = makeSprite(layerIdx, rightMost);
        if (!s) break;
        sprites[layerIdx].push(s);
        rightMost = Math.max(...sprites[layerIdx].map(s => s.x + s.w / 2));
      }
    }

    // ── Draw a single sprite with rounded corners and subtle shadow ────────
    function drawSprite(s: Sprite, now: number) {
      const cw = window.innerWidth;
      const ch = window.innerHeight;
      const pulse = Math.sin(now * 0.0009 + s.seed) * 0.012 + 1;
      const floatY = Math.sin(now * 0.00075 + s.seed * 0.7) * 6;
      const w = s.w * pulse;
      const h = s.h * pulse;
      const x = s.x - w / 2;
      const y = s.baseY + floatY - h / 2;

      // Vignette fade near edges
      const edgeFadeX = Math.min(s.x / (cw * 0.08), 1, (cw - s.x) / (cw * 0.08));
      const edgeFadeY = Math.min(
        (s.baseY) / (ch * 0.06),
        1,
        (ch - s.baseY) / (ch * 0.06),
      );
      const edgeFade = Math.min(edgeFadeX, edgeFadeY);

      safeCtx.save();
      safeCtx.globalAlpha = s.opacity * Math.max(0, edgeFade);

      // Rounded clip
      const r = Math.min(6, w * 0.04, h * 0.04);
      safeCtx.beginPath();
      safeCtx.roundRect(x, y, w, h, r);
      safeCtx.clip();

      safeCtx.drawImage(s.img, x, y, w, h);
      safeCtx.restore();
    }

    // ── Animation loop ─────────────────────────────────────────────────────
    function animate(now: number) {
      if (!running) return;
      const dt = Math.min(40, now - lastTime) / 1000;
      lastTime = now;

      // Dampen drag velocity each frame
      dragVelocity *= 0.92;
      if (Math.abs(dragVelocity) > 0.001) {
        speedFactor += (Math.sign(dragVelocity) * Math.abs(speedFactor) - speedFactor) * 0.15;
      }

      const cw = window.innerWidth;
      const ch = window.innerHeight;

      safeCtx.clearRect(0, 0, cw, ch);

      // Draw back-to-front for correct depth ordering
      for (let l = DEPTH_LAYERS - 1; l >= 0; l--) {
        const layer = sprites[l];
        for (const s of layer) {
          s.x += s.speed * speedFactor * dt;

          // Wrap around horizontally — randomise Y on re-entry
          if (speedFactor >= 0 && s.x - s.w / 2 > cw + 20) {
            s.x = -s.w / 2 - rand(0, s.w * 0.5);
            s.baseY = rand(s.h / 2 + 20, ch - s.h / 2 - 20);
          } else if (speedFactor < 0 && s.x + s.w / 2 < -20) {
            s.x = cw + s.w / 2 + rand(0, s.w * 0.5);
            s.baseY = rand(s.h / 2 + 20, ch - s.h / 2 - 20);
          }

          drawSprite(s, now);
        }
      }

      animId = requestAnimationFrame(animate);
    }

    function startAnimation() {
      if (running) return;
      running = true;
      lastTime = performance.now();
      animId = requestAnimationFrame(animate);
    }

    function stopAnimation() {
      running = false;
      cancelAnimationFrame(animId);
    }

    // ── Image loading ──────────────────────────────────────────────────────
    let loaded = 0;
    const urls = shuffle(imageUrls);
    const MIN_TO_START = 8; // start as soon as enough images are ready

    function tryStart() {
      if (loadedImages.length >= MIN_TO_START && !running) {
        resize();
        for (let l = 0; l < DEPTH_LAYERS; l++) fillLayer(l);
        startAnimation();
      }
    }

    for (const url of urls) {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        loadedImages.push(img);
        loaded++;
        tryStart();
      };
      img.onerror = () => {
        loaded++;
        if (loaded === urls.length) tryStart(); // try with what we have
      };
      img.src = url;
    }

    // ── Resize handler ─────────────────────────────────────────────────────
    function onResize() {
      resize();
      // Re-scatter sprites for new viewport dimensions
      for (let l = 0; l < DEPTH_LAYERS; l++) {
        sprites[l] = [];
        fillLayer(l);
      }
    }

    // ── Pointer event handlers (window-level, foreground-gated) ───────────
    function onMouseDown(e: MouseEvent) {
      if (isOverForeground(e.clientX, e.clientY)) return;
      dragActive = true;
      lastX = e.clientX;
    }

    function onMouseMove(e: MouseEvent) {
      if (!dragActive) return;
      const dx = e.clientX - lastX;
      lastX = e.clientX;
      dragVelocity = dx * 0.025;
    }

    function onMouseUp() {
      dragActive = false;
    }

    function onWheel(e: WheelEvent) {
      if (isOverForeground(e.clientX, e.clientY)) return;
      e.preventDefault();
      const dir = e.deltaY > 0 ? 1 : -1;
      const MAX_SPEED = 6;
      speedFactor = Math.max(-MAX_SPEED, Math.min(MAX_SPEED, speedFactor + dir * 0.9));
      dragVelocity = 0;
    }

    function touchClientX(e: TouchEvent) {
      return e.touches[0]?.clientX ?? 0;
    }
    function touchClientY(e: TouchEvent) {
      return e.touches[0]?.clientY ?? 0;
    }

    function onTouchStart(e: TouchEvent) {
      if (isOverForeground(touchClientX(e), touchClientY(e))) return;
      dragActive = true;
      lastX = touchClientX(e);
    }

    function onTouchMove(e: TouchEvent) {
      if (!dragActive) return;
      const x = touchClientX(e);
      dragVelocity = (x - lastX) * 0.025;
      lastX = x;
    }

    function onTouchEnd() {
      dragActive = false;
    }

    window.addEventListener('resize', onResize);
    window.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('touchstart', onTouchStart, { passive: true });
    window.addEventListener('touchmove', onTouchMove, { passive: true });
    window.addEventListener('touchend', onTouchEnd);

    return () => {
      stopAnimation();
      window.removeEventListener('resize', onResize);
      window.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('wheel', onWheel);
      window.removeEventListener('touchstart', onTouchStart);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
    };
  }, [imageUrls]); // re-run when imageUrls changes; CSS controls visibility

  if (imageUrls.length === 0) return null;

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        display: 'block',
        pointerEvents: 'none', // all events pass through to foreground UI
        opacity: visible ? 1 : 0,
        transition: 'opacity 0.7s ease',
      }}
    />
  );
}
