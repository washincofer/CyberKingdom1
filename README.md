# CyberKingdom — SQLite Prototype v0.1

Primeiro pacote **GitHub-ready** do backend persistente da Vertical Slice VS-001.

> Jornada preservada: **Trabalho Público → Action Queue → receber Cz → Mercado → comprar → consumir**.

## Por que SQLite agora?

O gate anterior ficou bloqueado pela ausência de PostgreSQL no runtime. Para não travar o projeto, esta versão usa **SQLite como persistência de protótipo**, mantendo a API e a regra de negócio separadas do banco. Firebase continua sendo uma alternativa futura para serviços online, mas não é necessário para esta etapa.

## O que já existe

- SQLite real via `sqlite3` da biblioteca padrão do Python.
- Action Queue FIFO persistente, limite de 10 ações.
- Reconciliação por timestamps absolutos.
- Liquidação única de Trabalho Público.
- Saldo em Cz e ledger de soma zero.
- Mercado com estoque e compra atômica.
- Inventário e consumo.
- Idempotência para operações mutáveis.
- Outbox de eventos.
- API HTTP `/api/v1`.
- Tela web mínima para provar a VS-001.
- Testes unitários e multiprocesso de concorrência.
- GitHub Actions CI em Python 3.11/3.12/3.13.

## Requisitos

- Python 3.11+
- Nenhum pacote pip obrigatório.

## Rodar localmente

```bash
./scripts/start.sh
```

Ou no Windows/PowerShell:

```powershell
$env:PYTHONPATH="backend"
python -m cyberkingdoms.cli serve --host 127.0.0.1 --port 8080
```

Abra `http://127.0.0.1:8080`.

## Resetar o protótipo

```bash
python scripts/reset_demo.py
```

## Testes

```bash
./scripts/run_tests.sh
```

## Playtest automatizado VS-001

```bash
python scripts/playtest.py
```

O relatório é gravado em `playtest-report.json` (ignorado pelo git).

## API principal

- `GET /health`
- `GET /api/v1/me`
- `GET /api/v1/actions`
- `POST /api/v1/public-jobs`
- `DELETE /api/v1/actions/{id}`
- `GET /api/v1/accounts/fa-player/balance`
- `GET /api/v1/accounts/fa-player/transactions`
- `GET /api/v1/inventories/inv-player`
- `GET /api/v1/markets/city-alpha/listings`
- `POST /api/v1/market-listings/lst-ration-basic/purchase`
- `POST /api/v1/items/RATION_BASIC/consume`
- `POST /internal/reconcile`
- `GET /internal/outbox`

Operações mutáveis de domínio requerem `Idempotency-Key`.

## DEMO, não balanceamento

O seed usa temporariamente:

- Trabalho Público: `+50 Cz`.
- Custo de energia: `10`.
- Ração: `20 Cz`.
- Ganho de fome: `25`.

Esses números existem apenas para fechar a jornada VS-001 e **não atualizam o Economy Balance**.

## Estrutura

```text
backend/cyberkingdoms/   regra de negócio, SQLite e HTTP
backend/tests/           regressão e concorrência
web/                     UI mínima da VS-001
openapi/                 contrato HTTP
scripts/                 start, reset, playtest e testes
docs/                    arquitetura, status e upload GitHub
.github/workflows/       CI
```

## Próximo gate sugerido

1. Subir este pacote no `CyberKingdom`.
2. Confirmar GitHub Actions verde.
3. Conectar a UI/Vertical Slice principal a esta API.
4. Fazer QA de regressão da VS-001 no navegador.
5. Só então decidir entre evoluir SQLite, Firebase ou retornar ao PostgreSQL para produção.
