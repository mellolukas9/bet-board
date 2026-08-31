"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE_URL, getHealth } from "@/lib/api";
import type { HealthResponse } from "@/types/api";

/**
 * Estado do backend, consultado pelo navegador.
 *
 * Era um Server Component até a 1.7; virou cliente porque agora mora dentro da
 * moldura do painel (`AppShell`), que é cliente — e um componente de servidor
 * não pode ser filho de um.
 */
export function BackendStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [verificando, setVerificando] = useState(true);

  const verificar = useCallback(async () => {
    try {
      const resposta = await getHealth();
      setHealth(resposta);
      setErro(null);
    } catch (e) {
      setHealth(null);
      setErro(e instanceof Error ? e.message : "Erro desconhecido");
    } finally {
      setVerificando(false);
    }
  }, []);

  /**
   * Consulta inicial.
   *
   * A chamada mora dentro de um IIFE, e não em `void verificar()`, porque o
   * React 19 reprova setState no corpo síncrono do efeito — e o analisador não
   * enxerga o `await` escondido dentro da função nomeada.
   */
  useEffect(() => {
    let atual = true;

    void (async () => {
      try {
        const resposta = await getHealth();
        if (!atual) return;
        setHealth(resposta);
        setErro(null);
      } catch (e) {
        if (atual) setErro(e instanceof Error ? e.message : "Erro desconhecido");
      } finally {
        if (atual) setVerificando(false);
      }
    })();

    return () => {
      atual = false;
    };
  }, []);

  const online = health !== null;

  return (
    <section className="rounded-xl border border-line bg-surface p-5">
      <header className="flex items-center gap-3">
        <span
          className={`inline-block size-2.5 rounded-full ${
            verificando ? "bg-muted" : online ? "bg-green" : "bg-red"
          }`}
          aria-hidden
        />
        <h2 className="text-sm font-medium">
          {verificando
            ? "Verificando o backend…"
            : online
              ? "Backend online"
              : "Backend offline"}
        </h2>
        <button
          type="button"
          onClick={() => {
            setVerificando(true);
            void verificar();
          }}
          disabled={verificando}
          className="ml-auto rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
        >
          Verificar
        </button>
      </header>

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
        <Row label="API">
          <span className="font-mono text-xs">{API_BASE_URL}</span>
        </Row>

        {health && (
          <>
            <Row label="Ambiente">{health.environment}</Row>
            <Row label="Banco">
              <span className={health.database === "up" ? "text-green" : "text-amber"}>
                {health.database === "up" ? "conectado" : "sem conexão"}
              </span>
            </Row>
          </>
        )}

        {erro && (
          <Row label="Erro">
            <span className="text-red">{erro}</span>
          </Row>
        )}
      </dl>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 truncate">{children}</dd>
    </>
  );
}
