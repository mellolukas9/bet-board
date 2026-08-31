"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { getMe } from "@/lib/api";

/**
 * A porta de entrada do painel: manda a pessoa para onde ela quer ir.
 *
 * Quem tem uma banca só cai direto nela — parar numa lista de um item a cada
 * login seria um clique inútil por dia. Quem tem mais de uma (ou nenhuma) vai
 * para a lista, que é onde a escolha existe de verdade.
 */
export function Inicio() {
  const router = useRouter();

  useEffect(() => {
    let atual = true;

    void (async () => {
      try {
        const me = await getMe();
        if (!atual) return;
        router.replace(
          me.bankrolls.length === 1
            ? `/banca/${me.bankrolls[0].slug}`
            : "/bancas",
        );
      } catch {
        // 401 é tratado no cliente HTTP (limpa o cookie e recarrega); qualquer
        // outra falha vira a lista, que sabe mostrar o erro
        if (atual) router.replace("/bancas");
      }
    })();

    return () => {
      atual = false;
    };
  }, [router]);

  return (
    <main className="grid min-h-screen place-items-center">
      <p className="text-sm text-muted">Abrindo o painel…</p>
    </main>
  );
}
