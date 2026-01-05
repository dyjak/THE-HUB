# components — dokumentacja komponentów wspólnych

Ten folder zawiera **wspólną strukturę layoutu** aplikacji oraz komponenty UI (w podfolderze `ui/`).

- `Layout.tsx` — główny „shell” aplikacji: tło + nav + main + footer.
- `Nav.tsx` — górna nawigacja i stan logowania.
- `Footer.tsx` — stopka.
- `ui/` — komponenty efektowe (canvas/SVG/animacje) oraz elementy UX (loading overlay, glass background).

Dokumentacja komponentów w `ui` jest w pliku `ui/README.md`.

---

## 1) Layout.tsx

**Rola**

`Layout` jest wspólną ramą dla podstron:

- renderuje tło (`StarField`) jako element fixed pod całą aplikacją,
- na wierzchu układa: `Nav` → `main` → `Footer`,
- nie zarządza routingiem ani autoryzacją (to robi Next.js / NextAuth), tylko layout.

**API**

```tsx
export default function Layout({ children }: { children: React.ReactNode })
```

- `children` — zawartość aktualnej strony.

**Struktura DOM**

```tsx
<div className="... h-screen flex flex-col ...">
  <StarField />
  <div className="relative z-10 flex flex-col h-full">
    <Nav />
    <main className="... flex-grow overflow-y-auto ...">{children}</main>
    <Footer />
  </div>
</div>
```

**Uwagi praktyczne**

- `main` ma `overflow-y-auto` — długie widoki scrollują w obrębie ekranu.
- `StarField` ma `pointerEvents: 'none'`, więc nie blokuje klikania.

---

## 2) Nav.tsx

**Rola**

Top‑bar aplikacji:

- linki do kluczowych podstron (AIR, inventory, gallery, docs),
- stan sesji z NextAuth:
  - jeśli użytkownik zalogowany → powitanie + przycisk wylogowania,
  - jeśli niezalogowany → link `Log In`.

**Zależności**

- `useSession()` i `signOut()` z `next-auth/react`.
- Ikony z `react-icons/fa`.

**Logika sesji**

```tsx
const { data: session } = useSession();

return session ? (
  // widok po zalogowaniu
) : (
  // link do /login
);
```

**Wylogowanie**

```ts
signOut({ callbackUrl: '/' })
```

To kończy sesję i wraca na stronę główną.

---

## 3) Footer.tsx

**Rola**

Stała stopka (branding / wersja).

**API**

Brak propsów.

**Zachowanie**

- domyślna przezroczystość `opacity-70`, po najechaniu `hover:opacity-100`.

---

## 4) components/ui (link)

- Dokumentacja ogólna: `src/components/ui/README.md`
- Dodatkowe, bardzo szczegółowe opisy:
  - `src/components/ui/ElectricBorder.README.md`
  - `src/components/ui/ParticleText.README.md`
  - `src/components/ui/ParticleSpinner.README.md`
  - `src/components/ui/CosmicButton.README.md`
  - `src/components/ui/CosmicOrb.README.md`
