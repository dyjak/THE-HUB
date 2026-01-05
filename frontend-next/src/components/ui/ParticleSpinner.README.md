# ParticleSpinner — szczegółowa dokumentacja

Komponent: `ParticleSpinner.tsx`

`ParticleSpinner` to loader na `<canvas>` przedstawiający obręcz cząsteczek krążących wokół środka.

Cechy:
- ruch obrotowy (rotacja),
- delikatny ruch ambient (sin/cos),
- opcjonalna interakcja z myszą (odpychanie),
- dopasowanie canvasa do rozmiaru rodzica.

---

## 1) API

```ts
interface ParticleSpinnerProps {
  className?: string;
  colors?: string[];
  particleSize?: number;
  mouseRadius?: number;
  mouseStrength?: number;
  radius?: number;
  count?: number;
  speed?: number;
}
```

- `radius` — bazowy promień obręczy.
- `count` — liczba cząsteczek.
- `speed` — szybkość rotacji.

---

## 2) Model cząsteczki

```ts
interface Particle {
  x: number;
  y: number;
  angle: number; // pozycja na obręczy
  dist: number;  // odległość od środka
  size: number;
  color: string;
  phaseX: number;
  phaseY: number;
}
```

- `angle/dist` to „baza” (biegunowe),
- `x/y` to faktyczna pozycja, do której dążymy i którą odchylamy.

---

## 3) Inicjalizacja

W `useEffect` komponent:

1) Pobiera `canvas` i `ctx`.
2) Dopasowuje rozmiar canvasa do rozmiaru rodzica (`parent.clientWidth/Height`).
3) Tworzy `count` cząsteczek:
   - `angle` równomiernie rozłożony wokół koła,
   - `dist` = `radius` + losowa wariancja, żeby obręcz była „grubsza”,
   - kolor losowany z palety.

---

## 4) Pętla animacji

Każda klatka:

1) Czyści canvas.
2) Zwiększa `timeRef` i `rotationRef`.
3) Dla każdej cząsteczki liczy:

- pozycję bazową na obręczy:

```ts
baseX = centerX + cos(angle + rotation) * dist
baseY = centerY + sin(angle + rotation) * dist
```

- ambient:

```ts
ambientX = sin(t + phaseX) * 2
ambientY = cos(t + phaseY) * 2
```

- target:

```ts
targetX = baseX + ambientX
targetY = baseY + ambientY
```

4) Jeśli mysz aktywna i cząsteczka w `mouseRadius`:
- odpychamy cząsteczkę od kursora.

5) Jeśli mysz nie wpływa:
- cząsteczka wraca do targetu easingiem (`/10`).

6) Rysuje kółko (`ctx.arc`).

---

## 5) Interakcja z myszą

- `mousemove` ustawia `mouseRef.{x,y,active}`.
- `mouseleave` wyłącza interakcję.

Odpychanie jest liczone siłą zależną od odległości:

```ts
force = (mouseRadius - distance) / mouseRadius
particle.x -= (dx / distance) * force * mouseStrength
```

---

## 6) Resize i sprzątanie

- `window.resize` wywołuje `init()` (ponowne dopasowanie canvasa i rekonstrukcja cząsteczek).

Cleanup:
- `cancelAnimationFrame`
- usunięcie event listenerów

---

## 7) Typowe problemy

1) „Rozmyty” canvas
- Komponent nie skaluje pod DPR (`devicePixelRatio`), tylko dopasowuje width/height do rodzica.
- Jeśli chcemy ostrzejszy obraz: dodać DPR scaling jak w `CosmicOrb`.

2) Zbyt ciężka animacja
- zmniejszyć `count`,
- zmniejszyć rozmiar canvasa,
- zmniejszyć `speed`.

---

## 8) Checklist przy zmianach

- utrzymać dopasowanie rozmiaru do rodzica,
- uważać na duże `count` (CPU),
- jeśli dodamy DPR scaling, pamiętać o `ctx.setTransform`.
