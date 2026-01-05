# components/ui — dokumentacja komponentów UI

Ten folder zawiera komponenty UI wykorzystywane w całej aplikacji.

W praktyce są tu 3 klasy komponentów:

1) **UX / warstwa aplikacyjna**
- `LoadingOverlay.tsx` — pełnoekranowa nakładka „czekaj” w portalu.
- `ElectricBorder.tsx` — wrapper z animowaną obwódką SVG (często używany jako przycisk).
- `FluidGlassBackground.tsx` — wrapper z tłem typu „liquid glass”.

2) **Efekty canvas (animacje)**
- `ParticleSpinner.tsx` — loader z cząsteczek.
- `ParticleText.tsx` — tekst jako chmura cząsteczek.
- `CosmicButton.tsx` — button z gwiazdami i cząsteczkami na obrysie.
- `CosmicOrb.tsx` — „kula” z cząsteczek.
- `StarField.js` — tło gwiezdne (biblioteka `react-starfield`).

3) **Proste komponenty animacji / prezentacji**
- `AnimatedCard.tsx` (+ duplikat `AnimatedCard.jsx`)
- `AnimatedHeading.jsx`
- `TypedText.tsx` (+ `TypedText.jsx`, `TypedText.d.ts`)

> W repo są duplikaty `.jsx`/`.tsx` dla części komponentów. W dokumentacji opisuję warianty i różnice.

---

## 1) LoadingOverlay.tsx

**Rola**

Pełnoekranowy overlay do długich operacji (AI / render). Renderowany przez portal do `document.body`, więc:

- nie jest przycinany przez `overflow` rodziców,
- zawsze jest „nad” layoutem.

**API**

```ts
interface LoadingOverlayProps {
  isVisible: boolean;
  text?: string;      // obecnie niewykorzystywane
  message?: string;   // tekst w UI
}
```

**Render warunkowy**

- `isVisible === false` → `null`.

**Skład UI**

- przyciemnienie tła (`bg-black/70` + `backdrop-blur-md`),
- w środku: `ParticleSpinner`.

**Portal**

```ts
return typeof document !== 'undefined'
  ? createPortal(overlay, document.body)
  : null;
```

**Uwagi**

- komponent importuje `TypedText`, ale nie używa go (aktualnie to „martwy import”).

---

## 2) FluidGlassBackground.tsx

**Rola**

Wrapper do efektu „liquid glass” za treścią.

**API**

```ts
interface FluidGlassBackgroundProps {
  children: ReactNode;
  className?: string;
}
```

**Mechanizm**

- `LiquidGlass` (z `@liquidglass/react`) jest umieszczony absolutnie pod contentem.

```tsx
<div className="absolute inset-0 -z-10">
  <LiquidGlass displacementScale={1} />
</div>
```

**Uwagi**

- Komponent nie zarządza stanem ani efektami.
- Jest czysto prezentacyjny.

---

## 3) ElectricBorder.tsx

**Rola**

Generyczny wrapper nadający elementowi animowaną „elektryczną” obwódkę.

Wykorzystywany m.in. w krokach AIR jako `as="button"`.

**API (najważniejsze)**

- `as?: ElementType` — pozwala renderować jako `div`, `button`, itd.
- `color`, `speed`, `chaos`, `thickness` — parametry efektu.
- `disabled` — redukuje chaos niemal do zera.

**Technika**

- SVG filter (`feTurbulence` + `feOffset` + `feDisplacementMap`) jest definiowany w ukrytym `<svg>`.
- Border dostaje `filter: url(#...)`.

**Responsywność**

- `ResizeObserver` obserwuje hosta i aktualizuje parametry animacji w zależności od szerokości/wysokości.

Szczegółowa dokumentacja jest w osobnym pliku: `ElectricBorder.README.md`.

---

## 4) ParticleSpinner.tsx

**Rola**

Loader na `<canvas>`: obręcz cząsteczek wokół środka + ambient motion + odpychanie przez mysz.

**Kluczowy model**

Każda cząsteczka ma:

- pozycję `(x, y)`
- bazę w biegunowych `(angle, dist)`
- fazy ambient (`phaseX/phaseY`)

**Animacja**

- rotacja obręczy rośnie o `speed`.
- jeśli mysz blisko i aktywna → cząsteczka jest odpychana.
- inaczej wraca do pozycji bazowej (ease).

Szczegółowa dokumentacja: `ParticleSpinner.README.md`.

---

## 5) ParticleText.tsx

**Rola**

Tekst renderowany jako cząsteczki na canvasie.

**Mechanizm**

1) Komponent rysuje tekst na canvasie.
2) Odczytuje `ImageData` i wybiera piksele z alphą powyżej progu.
3) Z tych punktów tworzy cząsteczki.
4) W animacji cząsteczki wracają do „bazowych” punktów i reagują na mysz.

**Fallback**

Jeśli tekst nie mieści się w kontenerze (na podstawie pomiaru DOM), komponent przełącza się na zwykły tekst.

Szczegółowa dokumentacja: `ParticleText.README.md`.

---

## 6) CosmicButton.tsx

**Rola**

Przycisk z dwoma canvasami:

- tło: gwiazdy (wolny ruch + twinkle),
- „obwódka”: cząsteczki krążące po obrysie zaokrąglonego prostokąta.

**Disabled**

Gdy `disabled === true` efekt nie jest inicjalizowany.

Szczegółowa dokumentacja: `CosmicButton.README.md`.

---

## 7) CosmicOrb.tsx

**Rola**

Canvas z cząsteczkami, które tworzą „kulę”:

- separacja (unikają zlepiania),
- przyciąganie do środka,
- przyciąganie do myszy w hover.

Szczegółowa dokumentacja: `CosmicOrb.README.md`.

---

## 8) StarField.js

**Rola**

Tło gwiezdne oparte o bibliotekę `react-starfield`.

**Ważne cechy**

- wrapper jest `position: fixed; inset: 0; pointerEvents: none;`
- komponent jest `aria-hidden` (tło dekoracyjne).

---

## 9) AnimatedCard.tsx / AnimatedCard.jsx

**Rola**

Karta (link) z animacją wejścia.

- Wersja TS: typowane propsy (`path`, `name`, `index`).
- Wersja JSX: to samo, ale bez typów.

Animacja:

```ts
initial={{ opacity: 0, scale: 0.8 }}
animate={{ opacity: 1, scale: 1 }}
transition={{ duration: 0.5, delay: index * 0.2 }}
```

---

## 10) AnimatedHeading.jsx

**Rola**

Nagłówek z prostą animacją pojawienia.

- start: `opacity: 0`, `y: -20`
- koniec: `opacity: 1`, `y: 0`

---

## 11) TypedText.tsx / TypedText.jsx / TypedText.d.ts

**Rola**

Wrapper na `react-type-animation`.

- TS: posiada interfejs `TypedTextProps`.
- JSX: wersja bez typów.
- `.d.ts`: deklaracja typów (przydatna, gdy importowane jest `.jsx`).

---

## 12) Uwagi repo (duplikaty plików)

W folderze są jednocześnie pliki `.tsx` i `.jsx` o tej samej nazwie.

Ważne konsekwencje:

- Import bez rozszerzenia może rozwiązać się inaczej w zależności od konfiguracji builda.
- Dla spójności warto docelowo zostawić jeden wariant (preferowany `.tsx`).

W tej dokumentacji nie zmieniamy jednak kodu — tylko opisujemy aktualny stan.
