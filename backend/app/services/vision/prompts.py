"""Prompt de extração da tip — compartilhado por todos os provedores de visão.

Fica fora dos extratores porque a maioria dos erros de leitura se resolve
ajustando este texto, e o ajuste tem que valer para qualquer provedor.
"""

SYSTEM_PROMPT = """\
Você extrai dados de apostas esportivas a partir de prints (screenshots) de \
casas de apostas.

Regras:
- Transcreva o que está no print. Nunca invente, complete ou "corrija" um valor \
que não esteja visível — use null.
- A cotação (odd) é sempre decimal. Se o print usar fração (ex: 5/4) ou formato \
americano (ex: +125), converta para decimal.
- O stake é só o número: "R$ 50,00" vira 50.0. Vírgula decimal brasileira vira ponto.
- Se o print tiver várias seleções (múltipla/acumulada), descreva o conjunto em \
`market` e use a cotação total em `odd`.
- `matches` lista as partidas do bilhete ("Time A x Time B"), uma por seleção e \
na ordem do print. Duas seleções do mesmo jogo repetem esse jogo. Não invente \
partida que não esteja escrita, e nunca escreva ali o tipo da aposta.
- `market` não começa com "Dupla:", "Tripla:" nem "Múltipla:". O tipo da aposta \
é deduzido das partidas; repeti-lo no mercado duplica a informação na mensagem \
que vai para o grupo.
- Se a imagem não for um print de aposta, estiver ilegível ou cortada a ponto de \
impedir a leitura, preencha `unreadable_reason` e deixe os demais campos null.
"""

USER_PROMPT = "Extraia os dados da aposta neste print."
