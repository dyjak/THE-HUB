# Frontend — architektura i biblioteki (Next.js)

Ten dokument opisuje **techniczny** obraz frontendu: jak jest zbudowany (architektura), jakie biblioteki i zasoby są użyte oraz **po co** zostały dobrane. Ma pomóc osobie, która widzi projekt pierwszy raz.

Repozytorium frontendu znajduje się w folderze `frontend-next/`.

---

## 1) Streszczenie architektury

Frontend to aplikacja **Next.js 15** oparta o **App Router** (`src/app/*`) i **React 19**.

Najważniejsze cechy:

- **Routing i layout** realizuje App Router (segmenty w `src/app`).
- **Autoryzacja** realizowana jest przez **NextAuth** (Credentials Provider) i deleguje weryfikację do backendu FastAPI.
- **Komunikacja z backendem** odbywa się głównie przez `fetch()` (na komponentach klienckich) do endpointów FastAPI pod `/api/...`.
- **UI** jest zbudowane na **TailwindCSS** + zestaw własnych komponentów efektowych w `src/components/ui`.
- Moduł **AIR** (`src/app/air`) jest osobnym „podsystemem” wewnątrz aplikacji: ma swój layout, podstrony i komponenty kroków (parametry → MIDI → render/eksport).

---

## 2) Framework i runtime

### Next.js 15 (App Router)
- Wykorzystuje `src/app` z plikami `layout.tsx`, `page.tsx` i podfolderami jako segmentami routingu.
- Aplikacja jest uruchamiana w trybie dev przez `next dev --turbopack`.
- `next.config.ts` jest w tej chwili minimalny (brak niestandardowych ustawień).

**Dlaczego Next.js?**
- Naturalny podział na layouty i moduły (np. `air`) bez ręcznego konfigurowania routera.
- Łatwe route-handlery (np. dla NextAuth) w `src/app/api/...`.

### React 19
- Interfejs jest oparty w dużej mierze o komponenty klienckie (`"use client"`), bo UI jest interaktywne (formularze, kroki, audio player, pobieranie plików, itp.).

### TypeScript (strict)
- Projekt działa w trybie `strict: true` (patrz `tsconfig.json`).
- Alias importów: `@/*` → `./src/*`.

**Dlaczego TS strict?**
- Zmniejsza ryzyko błędów w złożonych strukturach danych z backendu (np. plany JSON).
- Ułatwia refaktoryzację w module `air`.

---

## 3) Struktura projektu (najważniejsze katalogi)

- `src/app/` — routing (App Router), layouty i strony.
  - `layout.tsx` — RootLayout: fonty, globalne style, providery, shell aplikacji.
  - `providers.tsx` — globalne providery (obecnie `SessionProvider`).
  - `page.tsx` — strona startowa, obecnie robi `redirect("/air")`.
  - `login/` — ekran logowania.
  - `air/` — moduł AIR (główny obszar aplikacji).
  - `api/auth/[...nextauth]/route.ts` — NextAuth handler.

- `src/components/` — współdzielone komponenty layoutu:
  - `Layout.tsx` — wspólny „shell”: tło + `Nav` + `Footer` + `main`.
  - `Nav.tsx`, `Footer.tsx` — nawigacja i stopka.
  - `ui/` — komponenty wizualne/efektowe (animacje, tła, przyciski, loadery).

- `src/lib/`, `src/hooks/` — obecnie puste (rezerwa na wspólne helpery i hooki). W praktyce logika domenowa AIR jest trzymana wewnątrz `src/app/air/lib`.

---

## 4) Routing i layouty

### Root layout
- `src/app/layout.tsx`:
  - importuje `globals.css`,
  - ładuje font z `next/font/google` (np. `Space_Grotesk`),
  - opakowuje całą aplikację w `Providers` oraz komponent `Layout`.

### Layout aplikacji (shell)
- `src/components/Layout.tsx`:
  - renderuje tło (Canvas/efekt) przez `StarField`,
  - nakłada na to właściwą treść: `Nav`, `main`, `Footer`.

### Moduł AIR jako odseparowany segment
- `src/app/air/layout.tsx`:
  - sprawdza sesję przez `useSession()`,
  - jeśli użytkownik jest niezalogowany — robi `router.replace("/login")`,
  - w trakcie ładowania sesji pokazuje ekran „Ładowanie sesji...”.

**Dlaczego layout per moduł?**
- `air` ma własne wymagania (np. gate przez sesję), więc naturalnie trzyma się to w `air/layout.tsx` zamiast rozsypywać if-y po każdej podstronie.

---

## 5) Uwierzytelnianie i sesja (NextAuth)

### NextAuth — route handler
- `src/app/api/auth/[...nextauth]/route.ts` konfiguruje NextAuth w App Router.
- Provider: **CredentialsProvider**.
- W `authorize()` wykonywany jest request do backendu FastAPI (endpoint `/api/login`).
- Backend zwraca `access_token` i podstawowe dane użytkownika; frontend zapisuje je do tokena JWT sesji.

### SessionProvider
- `src/app/providers.tsx`:
  - aplikacja jest owinięta w `SessionProvider` (NextAuth), co udostępnia `useSession()`.

### Ekran logowania
- `src/app/login/page.tsx`:
  - UI logowania: username + PIN 6-cyfrowy,
  - logowanie jest wykonywane przez `signIn("credentials", { redirect: false, ... })`.

**Dlaczego NextAuth?**
- Standaryzuje przechowywanie sesji po stronie frontendu.
- Ułatwia „ochronę” segmentów UI (np. layout `air`).
- Pozwala trzymać token dostępowy w session/jwt bez ręcznego budowania całej logiki cookies.

---

## 6) Komunikacja z backendem (FastAPI)

### Główny wzorzec
- Frontend komunikuje się z backendem FastAPI bezpośrednio przez HTTP.
- Używana jest zmienna środowiskowa:
  - `NEXT_PUBLIC_BACKEND_URL` (np. `http://127.0.0.1:8000`).
- Główny prefiks endpointów backendu to zazwyczaj: `/api`.

W kodzie często występuje wzorzec:
- `const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";`
- `const API_PREFIX = "/api";`
- `const MODULE_PREFIX = "/air/<moduł>";`

### fetch() jako domyślny klient HTTP
- Zdecydowana większość wywołań to `fetch()` w komponentach klienckich (np. kroki AIR, inventory, gallery, user projects).

**Dlaczego fetch?**
- Jest natywny w przeglądarce, bez dodatkowych wrapperów.
- Wystarcza do prostych żądań JSON i pobierania blobów (download).

### Axios (użycie punktowe)
- `axios` jest używany głównie w NextAuth route handlerze (`authorize()`), gdzie wygodnie obsłużyć payload/odpowiedzi.

### Przykładowe obszary komunikacji w AIR
- `src/app/air/step-components/ParamPlanStep.tsx`:
  - pobiera listy providerów/modeli,
  - tworzy `run_id` przez POST do backendu,
  - robi synchronizacje „best-effort” (np. PATCH meta i selected_samples).

- `src/app/air/step-components/MidiPlanStep.tsx`:
  - POST compose,
  - odtwarzanie poprzednich wyników przez `initialRunId`.

- `src/app/air/step-components/RenderStep.tsx`:
  - POST render audio,
  - pobieranie ZIP lub listy plików (manifest) i ściąganie przez blob.

### Serwowanie audio i artefaktów
- Backend udostępnia wygenerowane pliki (audio/MIDI/SVG) pod `/api/audio/...`.
- W UI są helpery, które „normalizują” ścieżki (czasem backend zwraca `output\...` z separatorami Windows) na URL.

---

## 7) Moduł AIR — logika i podział na kroki

AIR jest największym modułem frontendu:

- `src/app/air/page.tsx` jest „orkiestratorem” kroków:
  - zarządza stanem kroków (StepId),
  - trzyma stan wyników pośrednich (np. `paramPlan`, `midiResult`, `runId*`, `selectedSamples`),
  - steruje przechodzeniem między krokami oraz potwierdzeniem cofnięcia.

- `src/app/air/step-components/` zawiera implementację UI i logiki kroków:
  - `ParamPlanStep.tsx` (parametry),
  - `MidiPlanStep.tsx` (plan MIDI) + `MidiPianoroll.tsx` (wizualizacja),
  - `RenderStep.tsx` (render/eksport),
  - `SampleSelector.tsx`, audio playery, dialogi.

- `src/app/air/lib/` trzyma modele danych i helpery domenowe:
  - `paramTypes.ts` — typy danych,
  - `constants.ts` — listy opcji (style, mood, metrum, instrumenty itd.),
  - `paramUtils.ts` — normalizacja danych z backendu/AI do bezpiecznych struktur (clamp, fallbacki, heurystyki).

**Dlaczego taki podział?**
- Krokowa nawigacja naturalnie pasuje do „wizard” UX.
- `lib/` w obrębie `air` pozwala trzymać logikę domenową blisko miejsca użycia (mniejszy narzut niż globalne `src/lib`).

---

## 8) UI, styling i biblioteki wizualne

### TailwindCSS
- Podstawowe stylowanie jest w Tailwind.
- W `tailwind.config.js` content obejmuje `./src/**/*` + ścieżki kompatybilne z app router.

**Dlaczego Tailwind?**
- Szybkie prototypowanie ekranów i komponentów.
- Spójność stylowania w module AIR bez rozbudowanej warstwy CSS.

### Komponenty UI w `src/components/ui`
Własny zestaw komponentów efektowych (tła, animacje, wizualne przyciski). Przykłady:
- `StarField.js` — animowane tło (canvas/efekt gwiazd).
- `ParticleText.tsx` + `ParticleSpinner.tsx` — efekty cząsteczkowe.
- `ElectricBorder.tsx` — przyciski/ramki z „elektryczną” obwódką.
- `AnimatedCard.tsx`, `AnimatedHeading`, `TypedText` — elementy animowane.

Te komponenty są wykorzystywane do:
- budowania „klimatu” UI (cyber/space),
- wyróżniania kluczowych akcji (przyciski, nagłówki),
- sygnalizacji stanu (loading overlay/spinner).

### Biblioteki animacji
Zależności w `package.json` wskazują na wykorzystywanie:
- `framer-motion` oraz `motion` — animacje komponentów.

### Ikony
- `react-icons` — proste ikony w `Nav`, przyciski, oznaczenia.

### Markdown / dokumentacja w UI
- `react-markdown` — renderowanie treści Markdown w interfejsie (np. dokumentacja pod `/air/docs` — jeśli jest używana w danym segmencie).

### Pozostałe efekty
- `@liquidglass/react`, `react-bits`, `react-starfield`, `react-type-animation` — biblioteki wspierające efekty UI/animacje.

---

## 9) Konwencje i wzorce w kodzie

### Komponenty klienckie
- Duża część kodu to `"use client"` z powodu:
  - interakcji użytkownika (formularze, wybory),
  - audio playback (WebAudio/HTMLAudio),
  - dynamicznego pobierania danych i renderowania wyników.

### „Best-effort sync”
W kilku miejscach w AIR:
- UI jest „źródłem prawdy”,
- a zapis do backendu (PATCH meta, selected samples) jest wykonywany **bez blokowania UX** — błędy są ignorowane lub raportowane miękko.

To podejście jest praktyczne, gdy:
- backend to długi pipeline (AI/render) i chcemy zachować płynność UI,
- a utrata części synchronizacji nie powinna zatrzymać pracy użytkownika.

### Odtwarzanie poprzednich wyników przez run_id
- Kroki wspierają `initialRunId` (np. odczyt poprzedniego stanu po odświeżeniu lub powrocie).

### Normalizacja danych
- `paramUtils.ts` zawiera funkcje, które „porządkują” dane z modelu/backendu:
  - dopasowanie stringów do sugerowanych opcji,
  - wartości domyślne,
  - heurystyki instrumentów.

---

## 10) Uruchamianie i konfiguracja (praktycznie)

### Komendy
- Dev: `pnpm dev`
- Build: `pnpm build`
- Start: `pnpm start`
- Lint: `pnpm lint`

### Zmienna środowiskowa
Ustaw w `frontend-next/.env.local` (jeśli backend nie działa na domyślnym adresie):

- `NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000`

---

## 11) Miejsca, od których warto zacząć czytanie kodu

Jeśli wchodzisz w projekt pierwszy raz:

1) Root i providery
- `src/app/layout.tsx`
- `src/app/providers.tsx`
- `src/components/Layout.tsx`

2) Autoryzacja
- `src/app/api/auth/[...nextauth]/route.ts`
- `src/app/login/page.tsx`
- `src/app/air/layout.tsx`

3) Moduł AIR (główny przepływ UI)
- `src/app/air/page.tsx`
- `src/app/air/step-components/ParamPlanStep.tsx`
- `src/app/air/step-components/MidiPlanStep.tsx`
- `src/app/air/step-components/RenderStep.tsx`

4) Inventory i projekty użytkownika
- `src/app/air/inventory/ui/InventoryBrowser.tsx`
- `src/app/air/me/page.tsx`

---

## 12) Uwagi techniczne (stan obecny)

- `src/lib/` i `src/hooks/` są puste — większość logiki domenowej żyje w `src/app/air/lib`.
- Strona `src/app/page.tsx` robi natychmiastowe `redirect("/air")`; reszta JSX w tym pliku jest w praktyce nieużywana.
- Nie ma wydzielonej „warstwy API klienta” (np. `apiClient.ts`). Wywołania `fetch()` są robione bezpośrednio w komponentach. To jest proste i czytelne, ale przy większej skali warto rozważyć centralizację.
