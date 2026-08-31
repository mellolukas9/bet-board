/**
 * Endereço público a partir do nome da banca.
 *
 * Espelha `slugify` de `backend/app/services/bankrolls.py`. Quem manda é o
 * backend — é ele que grava o `slug` e que resolve empate entre nomes iguais
 * (`vip`, `vip-2`). Aqui a conta é repetida só para a **prévia**: a pessoa vê
 * o link mudando enquanto digita o nome, antes de salvar.
 */
export function slugify(texto: string): string {
  return texto
    .normalize("NFKD")
    // remove os acentos que o NFKD separou da letra
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase()
    .slice(0, 64)
    .replace(/^-+|-+$/g, "");
}
