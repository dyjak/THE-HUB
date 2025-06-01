// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import axios from "axios";

// Upewnij się, że ten adres jest poprawny
const API_URL = "http://127.0.0.1:8000/api";
//const API_URL = "https://the-hub-onwb.onrender.com//api";

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "PIN",
      credentials: {
        pin: { label: "PIN", type: "text" }
      },
      async authorize(credentials) {
        if (!credentials?.pin) {
          throw new Error("PIN jest wymagany");
        }

        try {
          console.log("Próba logowania z PIN:", credentials.pin);
          // Połączenie z FastAPI
          const response = await axios.post(`${API_URL}/login`, {
            pin: credentials.pin
          });

          console.log("Odpowiedź z serwera:", response.data);

          // Zwracamy dane użytkownika
          if (response.data.message === "Login successful") {
            return {
              id: response.data.username,
              name: response.data.username,
            };
          }

          return null;
        } catch (error) {
          console.error("Login error:", error);
          throw new Error("Błąd podczas logowania");
        }
      }
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
        token.user = user;
      }
      return token;
    },
    async session({ session, token }) {
      // @ts-ignore
      session.user = token.user;
      return session;
    }
  },
  debug: true, // Włącz tryb debugowania, aby zobaczyć więcej szczegółów
});

export { handler as GET, handler as POST };