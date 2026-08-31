import { Suspense } from "react";

import { LoginForm } from "@/components/LoginForm";

export const metadata = {
  title: "Entrar — Bet Board",
};

export default function LoginPage() {
  // `useSearchParams` (o `?next=` do proxy) exige Suspense em volta
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
