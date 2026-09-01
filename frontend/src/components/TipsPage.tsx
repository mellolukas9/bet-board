"use client";

import { useBanca } from "@/components/AppShell";
import { BackendStatus } from "@/components/BackendStatus";
import { TipsPanel } from "@/components/TipsPanel";

/**
 * A aba de operação da banca: subir o print, corrigir o que a IA leu errado,
 * informar as unidades e publicar no canal.
 *
 * O resultado (green/red/encerrada) **não** é marcado aqui — ele mora na lista
 * da Banca, junto do lucro que ele muda.
 */
export function TipsPage() {
  const { banca } = useBanca();

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <TipsPanel bankroll={banca} />
      <BackendStatus />
    </div>
  );
}
