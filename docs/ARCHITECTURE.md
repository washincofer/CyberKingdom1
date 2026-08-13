# SQLite Prototype Architecture — v0.1

## Decisão de protótipo

Para o próximo ciclo do CyberKingdoms, SQLite substitui temporariamente o adapter em arquivo e o gate PostgreSQL. O objetivo é permitir uma vertical slice persistente, reproduzível no notebook/PC do DEV e executável no GitHub Actions sem provisionar infraestrutura externa.

SQLite **não é declarado como banco definitivo de produção**. A fronteira `Database -> GameService -> HTTP API` mantém a regra de negócio separada da persistência para permitir migração posterior.

## Garantias adotadas no protótipo

- `PRAGMA journal_mode=WAL`.
- `PRAGMA foreign_keys=ON`.
- `PRAGMA busy_timeout=15000`.
- `BEGIN IMMEDIATE` para comandos mutáveis que exigem serialização.
- `action_settlements.action_id` é chave primária: liquidação única.
- `idempotency_records.idempotency_key` é chave primária: replay seguro.
- índice único parcial protege posição ativa da Action Queue.
- constraints impedem estoque e quantidades negativas.
- lançamentos contábeis são gravados em pares cuja soma é zero pela camada de domínio.

## Limitações conhecidas

- SQLite serializa writers; isto é aceitável para protótipo, mas não representa throughput distribuído de produção.
- Worker é chamado por `/internal/reconcile`, CLI ou leitura de estado. Em produção deve existir scheduler/worker dedicado.
- Não há autenticação real nesta fatia.
- Parâmetros de recompensa/preço/necessidades são DEMO.
- O endpoint de consumo permanece sprint-local até confirmação do contrato canônico.

## Caminho de migração

1. Congelar os testes de domínio desta versão como contrato de regressão.
2. Introduzir adapter PostgreSQL ou serviço equivalente.
3. Rodar a mesma suíte contra o novo adapter.
4. Adicionar concorrência distribuída e locks do banco alvo.
5. Somente então promover a persistência para autoridade de produção.
