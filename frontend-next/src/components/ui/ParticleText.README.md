# ParticleText — szczegółowa dokumentacja

Komponent: `ParticleText.tsx`

`ParticleText` renderuje napis jako **chmurę cząsteczek na canvasie**. Cząsteczki układają się w kształt liter i reagują na mysz.

---

## 1) API

```ts
interface ParticleTextProps {
  text?: string;
  className?: string;
  colors?: string[];
  particleSize?: number;
  mouseRadius?: number;
  mouseStrength?: number;
  font?: string;
}
```

Parametry sterują:

- `text` — wyświetlany napis.
- `colors` — paleta kolorów cząsteczek (losowana per cząsteczka).
- `particleSize` — promień rysowanych punktów.
- `mouseRadius` — promień działania myszy.
- `mouseStrength` — siła odpychania.
- `font` — font używany do „odcisku” tekstu na canvasie.

---

## 2) Dwa tryby działania: canvas vs fallback tekstowy

Komponent ma stan:

- `usePlainText: boolean`

I przełącza się na zwykły tekst, gdy napis nie mieści się w kontenerze.

### 2.1. Pomiar dopasowania (useLayoutEffect)

Mechanizm:

1) Renderujemy ukryty element `measureRef` z tym samym fontem co finalny tekst.
2) Sprawdzamy `scrollWidth`.
3) Jeśli `scrollWidth > containerWidth * 0.98` → `usePlainText = true`.

Dlaczego `useLayoutEffect`?
- żeby pomiar wykonać po tym, jak DOM ma finalne rozmiary (przed „mignięciem”).

### 2.2. Obsługa `font` z `clamp()`

Canvas nie rozumie `clamp()` w `ctx.font`, więc komponent:

- używa `getComputedStyle(measureRef).font` jako priorytetu,
- a w fallbacku tekstowym umie wygenerować styl CSS z `clamp(...)`.

To jest powód istnienia `fallbackTextStyle`.

---

## 3) Główna idea: „odcisk tekstu” → piksele → cząsteczki

### 3.1. Inicjalizacja

W `useEffect` (gdy `usePlainText` jest false):

- dopasowujemy canvas do rodzica,
- rysujemy tekst w centrum,
- pobieramy `ImageData` z całego canvasa,
- próbkujemy piksele krokiem `step = 4` (kompromis wydajność/gęstość),
- dla pikseli z `alpha > 128` tworzymy cząsteczki.

Każda cząsteczka ma:

```ts
interface Particle {
  x: number; y: number;       // aktualna pozycja
  baseX: number; baseY: number; // docelowa pozycja (kształt liter)
  size: number;
  density: number;            // obecnie niewykorzystywane w dynamice
  color: string;
  phaseX: number; phaseY: number; // fazy ambient
}
```

`x/y` startują losowo, a `baseX/baseY` są punktami liter.

---

## 4) Pętla animacji

Każda klatka:

1) Czyścimy canvas.
2) Dla każdej cząsteczki liczymy:
   - odległość do myszy,
   - odpychanie, jeśli mysz jest aktywna i blisko,
   - docelową pozycję bazową + ambient.
3) Jeśli mysz daleko, cząsteczka wraca do targetu przez easing.

### 4.1. Interakcja z myszą

```ts
force = (mouseRadius - distance) / mouseRadius
particle.x -= (dx / distance) * force * mouseStrength
particle.y -= (dy / distance) * force * mouseStrength
```

### 4.2. Ambient motion

Każda cząsteczka ma własną fazę, co zapobiega synchronicznemu „pompowaniu” całego tekstu:

```ts
ambientX = sin(t + phaseX) * 1.5
ambientY = cos(t + phaseY) * 1.5
```

### 4.3. Powrót do bazy (ease)

```ts
particle.x -= (particle.x - targetX) / 15
particle.y -= (particle.y - targetY) / 15
```

Im większy dzielnik, tym wolniejszy i bardziej płynny powrót.

---

## 5) Obsługa zdarzeń i sprzątanie

- `mousemove` / `mouseleave` na canvasie ustawia `mouseRef.active`.
- `resize` wywołuje ponowną inicjalizację (rekonstrukcja cząsteczek).

Sprzątanie:

- `cancelAnimationFrame`
- usunięcie listenerów

---

## 6) Typowe problemy

1) Tekst „znika” i jest tylko fallback
- kontener jest zbyt wąski względem fontu (zgodnie z intencją fallbacku).

2) Wysokie zużycie CPU
- zbyt duże wymiary canvasa i zbyt gęste cząsteczki.
- w takim wypadku warto zwiększyć `step` (np. 6–8) albo zmniejszyć font.

3) Rozjechany font na canvasie
- `font` przekazane bezpośrednio może różnić się od tego, co CSS finalnie ustawia.
- komponent preferuje `getComputedStyle(measureRef).font` — to zwykle rozwiązuje problem.

---

## 7) Checklist przy zmianach

- nie usuwać pomiaru `measureRef` (to chroni UI na małych ekranach),
- trzymać sampling `step` jako parametr wydajności,
- pilnować, aby `init()` było wołane na `resize` i przy zmianie `text/font`.
