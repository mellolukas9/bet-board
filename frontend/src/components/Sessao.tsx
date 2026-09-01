"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { logout, refreshSession } from "@/lib/api";
import { getToken, prazoDaSessao } from "@/lib/auth";

/** De quanto em quanto tempo o relógio olha para a sessão. */
const INTERVALO_MS = 5_000;

/** A partir daqui a tela avisa que a sessão está para cair. */
const AVISO_MS = 60_000;

/**
 * O que conta como "a pessoa ainda está aí".
 *
 * `mousemove` fica de fora de propósito: um esbarrão no mouse manteria a sessão
 * viva a noite inteira, que é justamente o que o prazo existe para evitar.
 * Rolar a lista de apostas conta — é leitura, e leitura é uso.
 */
const EVENTOS_DE_USO = ["pointerdown", "keydown", "wheel", "touchstart"] as const;

/**
 * O relógio da sessão: renova enquanto a pessoa usa o painel e a derruba quando
 * ela para.
 *
 * A regra de verdade é do servidor — o token vale poucos minutos e só o
 * `/auth/refresh` o estende. Isto aqui é o que faz a renovação acontecer
 * enquanto há uso, e o que tira a pessoa da tela quando não há: sem isso o
 * painel ficaria aberto mostrando dados de uma sessão que já morreu, até o
 * próximo clique dar 401.
 *
 * Devolve o aviso de "está para cair", para a moldura mostrá-lo.
 */
export function useSessao(): {
  /** segundos restantes quando a sessão está prestes a cair; `null` fora disso */
  avisoEmSegundos: number | null;
  /** "continuar conectado": renova agora e fecha o aviso */
  continuar: () => void;
} {
  const router = useRouter();
  const [avisoEmSegundos, setAviso] = useState<number | null>(null);

  // começa em zero e é acertado ao montar: ler o relógio durante o render é
  // impuro, e o React 19 reprova
  const ultimoUso = useRef(0);
  // trava de reentrância: o relógio bate a cada 5s e a renovação leva mais que
  // isso numa rede ruim — sem ela, sairiam várias renovações em fila
  const renovando = useRef(false);

  const encerrar = useCallback(() => {
    logout();
    router.replace("/login?expirada=1");
    // o proxy lê o cookie no servidor; sem o refresh a rota anterior fica em cache
    router.refresh();
  }, [router]);

  const renovar = useCallback(async () => {
    if (renovando.current) return;
    renovando.current = true;
    try {
      await refreshSession();
      setAviso(null);
    } catch {
      // 401 já é tratado no cliente HTTP; qualquer outra falha (rede fora) só
      // adia a renovação para a próxima batida do relógio
    } finally {
      renovando.current = false;
    }
  }, []);

  useEffect(() => {
    // abrir a tela é uso: a contagem começa agora
    ultimoUso.current = Date.now();

    function marcarUso() {
      ultimoUso.current = Date.now();
    }

    for (const evento of EVENTOS_DE_USO) {
      window.addEventListener(evento, marcarUso, { passive: true });
    }

    const relogio = setInterval(() => {
      const token = getToken();
      if (token === null) return; // já saiu por outro caminho

      const prazo = prazoDaSessao(token);
      if (prazo === null) return; // token ilegível: quem decide é o servidor

      const restante = prazo.expiraEm - Date.now();
      if (restante <= 0) {
        encerrar();
        return;
      }

      const parado = Date.now() - ultimoUso.current;

      // Mexeu desde a última batida e o token já passou da metade da janela:
      // renova. A metade é o ponto em que ainda sobra tempo para uma rede ruim
      // tentar de novo antes de a sessão cair.
      if (parado < INTERVALO_MS && restante < prazo.janelaMs / 2) {
        void renovar();
        return;
      }

      setAviso(restante <= AVISO_MS ? Math.ceil(restante / 1000) : null);
    }, INTERVALO_MS);

    return () => {
      clearInterval(relogio);
      for (const evento of EVENTOS_DE_USO) {
        window.removeEventListener(evento, marcarUso);
      }
    };
  }, [encerrar, renovar]);

  const continuar = useCallback(() => {
    ultimoUso.current = Date.now();
    void renovar();
  }, [renovar]);

  return { avisoEmSegundos, continuar };
}

/**
 * "Sua sessão está para expirar", com um botão para ficar.
 *
 * Existe para não perder trabalho: a revisão de uma tip é um formulário meio
 * preenchido, e uma pessoa que leu a tela por dez minutos sem clicar em nada
 * não deveria descobrir o prazo perdendo o que digitou.
 */
export function AvisoDeSessao({
  segundos,
  onContinuar,
}: {
  segundos: number;
  onContinuar: () => void;
}) {
  return (
    <div
      role="alertdialog"
      aria-labelledby="titulo-da-sessao"
      className="fixed inset-x-0 bottom-5 z-50 mx-auto w-[min(24rem,calc(100%-2.5rem))] rounded-xl border border-amber/40 bg-surface p-4 shadow-2xl"
    >
      <h2 id="titulo-da-sessao" className="text-sm font-medium text-amber">
        Sua sessão vai expirar
      </h2>
      <p className="mt-1 text-sm text-muted">
        Sem atividade, você volta para a tela de login em{" "}
        <span className="tabular-nums text-white">{segundos}s</span>.
      </p>
      <button
        type="button"
        onClick={onContinuar}
        className="mt-3 w-full rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white transition hover:bg-accent/85"
      >
        Continuar conectado
      </button>
    </div>
  );
}
