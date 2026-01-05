# ElectricBorder — szczegółowa dokumentacja

Komponent: `ElectricBorder.tsx`

`ElectricBorder` to wrapper, który dokłada do dowolnego elementu (np. `div`, `button`) animowaną „elektryczną” obwódkę.

Efekt jest osiągnięty przez **SVG filter** (turbulence + displacement) zastosowany na warstwie border.

---

## 1) API komponentu

### 1.1. Props

```ts
type ElectricBorderProps<T extends ElementType> = PropsWithChildren<{
  color?: string;
  speed?: number;
  chaos?: number;
  thickness?: number;
  className?: string;
  style?: CSSProperties;
  as?: T;
  disabled?: boolean;
}> & React.ComponentPropsWithoutRef<T>;
```

Najważniejsze:

- `as` — typ renderowanego elementu (domyślnie `div`).
- `color` — kolor obwódki.
- `thickness` — grubość obwódki.
- `speed` — wpływa na czas trwania animacji w filtrze.
- `chaos` — siła zniekształceń (scale w `feDisplacementMap`).
- `disabled` — redukuje `chaos` prawie do zera.

### 1.2. Przykład użycia jako przycisk

```tsx
<ElectricBorder
  as="button"
  color="#f97316"
  speed={0.1}
  chaos={0.3}
  className="w-full py-3 rounded-xl"
  disabled={!canRun}
>
  Generuj
</ElectricBorder>
```

---

## 2) Jak działa efekt

### 2.1. Ukryty SVG z definicją filtra

Komponent renderuje minimalny `<svg>` poza ekranem (fixed, bardzo mały, prawie niewidoczny), tylko po to, aby zdefiniować filter w `<defs>`.

```tsx
<svg className="fixed -left-[10000px] -top-[10000px] w-[10px] h-[10px] opacity-[0.001]">
  <defs>
    <filter id={filterId}>
      <feTurbulence ... />
      <feOffset> <animate attributeName="dy" ... /> </feOffset>
      ...
      <feDisplacementMap ... />
    </filter>
  </defs>
</svg>
```

### 2.2. Warstwy obwódki

Nad hostem komponent buduje kilka warstw:

1) `strokeRef` — główny border (na nim jest `filter: url(#...)`).
2) `glow1` i `glow2` — dodatkowe obwódki z `blur`, żeby dać poświatę.
3) `bgGlow` — rozmyty gradient w tle (większy, skalowany).

Wszystkie warstwy są `pointer-events: none`.

### 2.3. Identyfikator filtra

Filter id jest generowany na bazie `useId()` i czyszczony z `:` (czasem występuje w React ID):

```ts
const rawId = useId().replace(/[:]/g, '');
const filterId = `turbulent-displace-${rawId}`;
```

To zapobiega kolizjom, gdy na stronie jest wiele `ElectricBorder`.

---

## 3) Aktualizacja animacji i dopasowanie do rozmiaru

### 3.1. `updateAnim()`

Ta funkcja:

- odczytuje aktualny rozmiar hosta (`clientWidth/clientHeight`),
- aktualizuje `values` w `<animate>` dla `dx` i `dy`, aby przemieszczenia były skalowane do rozmiaru elementu,
- przelicza czas trwania animacji na podstawie `speed`:

```ts
const baseDur = 6;
const dur = Math.max(0.001, baseDur / (speed || 1));
```

- ustawia siłę zniekształcenia:

```ts
if (disp) disp.setAttribute('scale', String(30 * (effectiveChaos || 1)));
```

### 3.2. ResizeObserver

Komponent używa `ResizeObserver`, aby reagować na zmiany rozmiaru hosta (np. zmiana tekstu, responsywność):

```ts
const ro = new ResizeObserver(() => updateAnim());
ro.observe(rootRef.current);
```

---

## 4) `disabled` a „chaos”

Gdy `disabled === true`:

```ts
const effectiveChaos = disabled ? 0.01 : chaos;
```

Cel:
- efekt nadal jest widoczny jako obwódka,
- ale jest praktycznie nieruchomy (mniej „szumu”), więc UI nie wygląda jak aktywne.

---

## 5) Stylowanie i border-radius

Komponent próbuje dziedziczyć `borderRadius` ze `style`, a jeśli go nie ma, używa `inherit`.

To ważne, bo obwódka i glow muszą mieć identyczny radius jak host.

---

## 6) Ryzyka i pułapki

1) `ResizeObserver` nie działa w bardzo starych przeglądarkach.

2) `filter: url(#...)` może zachowywać się inaczej zależnie od przeglądarki / GPU.

3) `speed` bliskie 0 daje bardzo duże `dur` (powolna animacja). Kod broni się przez `Math.max(0.001, ...)`, ale nadal warto unikać ekstremów.

---

## 7) Checklist przy zmianach

- utrzymać unikalny `filterId` per instancja,
- zawsze dopasowywać animacje do `width/height`,
- nie zdejmować `pointer-events: none` z warstw obwódki,
- pamiętać o `disabled` → stabilny wygląd.
