// konfiguracja next-auth dla app router (route handler).
// używamy credentials provider i delegujemy weryfikację do backendu fastapi (/api/login).
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import axios from "axios";

// Bazowy url backendu fastapi.
// w trybie publicznym Caddy może mieć Basic Auth, a wtedy server-side fetch
// z NextAuth do publicznego URL będzie kończył się 401. Dlatego preferujemy
// BACKEND_INTERNAL_URL (np. http://backend:8000) w sieci docker-compose.
const BACKEND_BASE_URL = (process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000")
  .replace(/\/$/, "");

// (dokładamy /api)
const API_URL = `${BACKEND_BASE_URL}/api`;

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "Login",
      credentials: {
        username: { label: "Nazwa użytkownika", type: "text" },
        pin: { label: "PIN", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.pin) {
          throw new Error("Nazwa użytkownika i PIN są wymagane");
        }

        try {
          const response = await axios.post(`${API_URL}/login`, {
            username: credentials.username,
            pin: credentials.pin,
          });

          const data = response.data;

          if (data?.message === "Login successful" && data?.access_token) {
            return {
              id: data.id,
              name: data.username,
              username: data.username,
              accessToken: data.access_token,
            } as any;
          }

          return null;
        } catch (error: any) {
          console.error("Login error:", error?.response?.data || error?.message || error);
          throw new Error("Błąd podczas logowania");
        }
      },
    })
  ],
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 dni
  },
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        const existingUser =
          typeof (token as any).user === "object" && (token as any).user !== null
            ? ((token as any).user as Record<string, unknown>)
            : {};
        token.user = {
          ...existingUser,
          ...(user as unknown as Record<string, unknown>),
        };
      }
      return token;
    },
    async session({ session, token }) {
      // @ts-ignore - next-auth ma tu luźny typ user, a my dokładamy własne pola (id, accessToken)
      session.user = token.user;
      return session;
    },
  },
  debug: true, // tryb debug (więcej logów w dev)
});

export { handler as GET, handler as POST };