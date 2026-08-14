# CyberKingdoms — VS-001 Recreated Integrated Candidate 01

Recriação autorizada da Vertical Slice VS-001, baseada no comportamento que havia sido aprovado para freeze e no backend SQLite v0.1 existente em `washincofer/CyberKingdom1`.

## Como usar

Este pacote é um **overlay** para o repositório do backend atual.

1. Faça uma cópia de segurança do `web/index.html` atual.
2. Substitua `web/index.html` pelo arquivo deste pacote.
3. Mantenha o backend Python existente sem alterações.
4. Inicie o servidor conforme o README do backend.
5. Abra `http://127.0.0.1:8080`.

## O que a nova tela cobre

- City Hub contextual, sem free-walk.
- Trabalho Público.
- Action Queue FIFO com até 10 ações.
- Diferença visual entre `termina em` e `inicia em`.
- Reconciliação automática e manual.
- Mercado Regional acessível durante ações.
- Compra bloqueada visualmente quando falta Cz.
- Inventário e consumo.
- Saldo, fome, energia e estado técnico vindos da API.
- Fluxo guiado da jornada VS-001.

## Importante

O personagem exibido nesta reconstrução é um **placeholder técnico em CSS** porque os assets originais da Vertical Slice não estavam disponíveis. Ele deve ser substituído futuramente pelo Avatar Composer/VAM já especificado no projeto.

Os valores de economia continuam DEMO e não atualizam o Economy Balance.
