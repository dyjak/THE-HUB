// Strona startowa aplikacji.
// W aktualnej wersji projekt od razu przekierowuje do /air.
// to musi być redirect po stronie serwera (server component), żeby nie spamować logów
// błędem NEXT_REDIRECT w runtime.

import { redirect } from "next/navigation";

export default function Home() {
    redirect("/air");
}