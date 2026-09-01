"use client";

import { useId, useState } from "react";

/**
 * O "?" que explica um número do painel.
 *
 * Substitui o `title=""` do navegador por dois motivos: ele demora ~1s para
 * aparecer, e no celular **nunca** aparece — não há o que passar o mouse por
 * cima. Aqui o balão abre no toque, no foco do teclado e no hover.
 *
 * O texto fica no `aria-describedby` do botão, então quem usa leitor de tela
 * ouve a explicação junto do número, sem precisar abrir nada.
 */
export function Ajuda({
  children,
  lado = "direita",
}: {
  children: string;
  /** De que lado o balão cresce, para ele não sair da tela na ponta da linha. */
  lado?: "direita" | "esquerda";
}) {
  const id = useId();
  const [preso, setPreso] = useState(false);

  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label="O que é isto?"
        aria-describedby={id}
        aria-expanded={preso}
        onClick={() => setPreso((v) => !v)}
        onBlur={() => setPreso(false)}
        className="grid size-4 cursor-help place-items-center rounded-full border border-line text-[9px] leading-none text-muted transition hover:border-accent/60 hover:text-white"
      >
        ?
      </button>

      {/* sempre no DOM: é o que o aria-describedby aponta, e o leitor de tela
          lê o texto mesmo com o balão fechado */}
      <span
        id={id}
        role="tooltip"
        className={`pointer-events-none absolute top-6 z-20 w-56 rounded-lg border border-line bg-surface-3 px-3 py-2 text-left text-[11px] font-normal leading-snug text-foreground/90 shadow-lg transition ${
          lado === "direita" ? "left-0" : "right-0"
        } ${
          preso
            ? "visible opacity-100"
            : "invisible opacity-0 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
        }`}
      >
        {children}
      </span>
    </span>
  );
}
