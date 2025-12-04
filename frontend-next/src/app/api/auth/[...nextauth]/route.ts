// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import axios from "axios";

// Backend FastAPI URL
const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL
  ? `${process.env.NEXT_PUBLIC_BACKEND_URL}/api`
  : "http://127.0.0.1:8000/api";

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
        token.user = {
          ...token.user,
          ...user,
        };
      }
      return token;
    },
    async session({ session, token }) {
      // @ts-ignore
      session.user = token.user;
      return session;
    },
  },
  debug: true, // Włącz tryb debugowania, aby zobaczyć więcej szczegółów
});

export { handler as GET, handler as POST };