# Prints de tips para teste

Coleção de prints reais usada para medir a taxa de acerto da IA de visão
(`pytest -m vision`). A meta da Fase 1.2 é **15–20 prints** cobrindo os casos que
aparecem no dia a dia do grupo.

## Como adicionar um caso

Dois arquivos com o **mesmo nome**:

```
bet365-over25.png     <- o print
bet365-over25.json    <- os valores corretos
```

O `.json` declara só os campos que você quer conferir — o que não estiver ali é
ignorado na comparação:

```json
{
  "source": "Bet365",
  "event": "Flamengo x Palmeiras",
  "market": "Over 2.5 gols",
  "odd": 1.85,
  "stake": 50.0,
  "currency": "BRL"
}
```

A comparação normaliza espaços e caixa nos textos, e aceita vírgula ou ponto
decimal em `odd`/`stake`.

## O que vale a pena cobrir

- Casas diferentes (Bet365, Betano, Superbet, Estrela Bet…)
- Simples e múltiplas/acumuladas
- Mercados variados: over/under, handicap asiático, ambas marcam, escanteios
- Odds em formatos diferentes, se a casa exibir assim
- **Bilhete montado numa partida só** ("Criar Aposta"): é onde a leitura mais
  erra — a cotação do topo é a total, as de cada seleção são parciais, e a
  caixa de aposta em branco não é print ilegível.
- **Casos ruins de propósito:** print cortado, borrado, foto de tela.
  Para esses, o `.json` esperado leva os campos como `null`.

## Um `.json` sem o print ainda não vale

O teste só olha para um caso quando existem os **dois** arquivos. Um `.json`
sozinho fica esperando a imagem, sem quebrar a suíte — é o caso do
`bet365-criar-aposta-atletico-cruzeiro.json`, que espera o print do bilhete
Atlético-MG x Cruzeiro.

## Privacidade

Prints de casa de aposta costumam mostrar saldo, nome e ID da conta. Corte ou
borre essas áreas antes de commitar — este diretório vai para o git.
