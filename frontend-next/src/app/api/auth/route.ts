// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import axios from "axios";

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "PIN",
      credentials: {
        pin: { label: "PIN", type: "text" }
      },
      async authorize(credentials) {
        if (!credentials?.pin) {
          return null;
        }

        try {
          // Połączenie z Twoim FastAPI
          const response = await axios.post("http://127.0.0.1:8000/api/login", {
            pin: credentials.pin
          });

          // zwracamy dane użytkownika
          if (response.data.message === "Login successful") {
            return {
              id: response.data.username,
              name: response.data.username,
            };
          }

          return null;
        } catch (error) {
          console.error("Login error:", error);
          return null;
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
  }
});

export { handler as GET, handler as POST };