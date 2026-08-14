# CyberKingdoms — VS-001 Recreated / Integrated Candidate 01

Status: **RECREATED_FROM_APPROVED_BEHAVIOR**

Esta versão foi recriada porque o pacote visual original da Vertical Slice Candidate 01 não estava mais disponível. A autorização de recriação permite mudanças visuais, mas preserva como contrato funcional a jornada anteriormente aprovada.

## Contrato funcional preservado

1. Trabalho Público inicia uma ação.
2. Action Queue é FIFO, persistente e limitada a 10 ações ativas.
3. A interface distingue ação em andamento (`termina em`) de ação futura (`inicia em`).
4. O servidor reconcilia ações usando timestamps absolutos.
5. Trabalho concluído liquida Cz uma única vez.
6. Mercado Regional permanece acessível durante ações.
7. Compra valida saldo e estoque no backend.
8. Compra concluída adiciona o item ao inventário persistente.
9. Consumo remove a Ração Básica e atualiza a fome com limite de 100.
10. Valores econômicos continuam marcados como DEMO/MOCK e não alteram o Economy Balance.

## Mudanças visuais autorizadas

- A cena City Hub foi recriada em CSS sem depender dos assets perdidos.
- O cidadão exibido na cena é um placeholder visual técnico, não substitui o Avatar Composer/VAM em produção.
- A UI agora exibe explicitamente a autoridade do backend e um painel técnico de estado.
- Mercado e Hub são contextos de tela; não há free-walk.

## Backend integrado

A UI consome diretamente:

- `GET /api/v1/me`
- `GET /api/v1/actions`
- `POST /api/v1/public-jobs`
- `DELETE /api/v1/actions/{id}`
- `GET /api/v1/accounts/fa-player/balance`
- `GET /api/v1/inventories/inv-player`
- `GET /api/v1/markets/city-alpha/listings`
- `POST /api/v1/market-listings/{id}/purchase`
- `POST /api/v1/items/RATION_BASIC/consume`
- `POST /internal/reconcile`

Operações mutáveis que fazem parte do domínio continuam enviando `Idempotency-Key`.

## Gate de aprovação sugerido

A recriação pode ser promovida a **VS-001 Integrated Freeze 01** quando:

- regressão automatizada do backend continuar verde;
- playtest da jornada completa continuar verde;
- UI for testada no navegador contra o backend real;
- fila de 10 ações, compra sem saldo, acesso ao mercado durante ação e reconciliação pós-retorno forem confirmados;
- a substituição futura do placeholder visual pelo Avatar Composer não alterar o contrato funcional.
