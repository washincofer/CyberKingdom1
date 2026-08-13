# Status — SQLite Prototype v0.1

- Character Creation / Avatar: **HOLD**, fora deste escopo.
- Vertical Slice de referência: **VS-001**.
- Persistência do protótipo: **SQLite**.
- Backend: Python standard library, sem framework/dependência externa.
- API: `/api/v1` preservando os contratos do Sprint 01.
- UI de prova: incluída em `/`.
- Action Queue: FIFO, limite 10.
- Idempotência: habilitada em trabalho, compra e consumo.
- Ledger: transferências Cz em partidas de soma zero.
- Outbox: eventos persistidos.
- CI: unitários + concorrência + playtest.

## Gate desta versão

Esta versão deve ser considerada `PROTOTYPE_READY` quando a suíte local e o GitHub Actions estiverem verdes. Ela **não substitui** o futuro gate de banco de produção.
