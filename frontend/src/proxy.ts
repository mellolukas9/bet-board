import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { TOKEN_COOKIE } from "@/lib/auth";

/**
 * Porteiro do painel.
 *
 * Só olha se **existe** um cookie de sessão — quem valida a assinatura do token
 * é o backend, em toda chamada. Isto aqui evita o piscar da tela do painel para
 * quem não está logado; não é a barreira de segurança.
 *
 * (No Next 16 este arquivo se chama `proxy.ts`; `middleware.ts` foi renomeado.)
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const logado = request.cookies.has(TOKEN_COOKIE);
  const naTelaDeLogin = pathname === "/login";

  // /b/<slug> é a página que o tipster manda para os assinantes: ela existe
  // justamente para quem não tem conta. Quem decide se ela abre é o backend
  // (banca privada responde 404), não o cookie.
  if (pathname.startsWith("/b/")) return NextResponse.next();

  if (!logado && !naTelaDeLogin) {
    const destino = new URL("/login", request.url);
    // volta para onde a pessoa queria ir depois de entrar
    destino.searchParams.set("next", pathname);
    return NextResponse.redirect(destino);
  }

  if (logado && naTelaDeLogin) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // tudo menos os assets do Next e o favicon
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
