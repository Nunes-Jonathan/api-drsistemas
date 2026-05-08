# api-drsistemas

Streamlit dashboard sobre o Web Service Retaguarda (Saurus). Sincroniza
produtos, estoque e vendas para um Postgres (AWS RDS, autenticação IAM) e
expõe:

- 📋 **Produtos** — lista detalhada, busca por descrição/EAN, filtros, drill-in
  (preços por loja, códigos, estoque, últimas vendas) e export para CSV ou Excel.
- 📊 **Dashboard** — KPIs, top-N produtos mais vendidos, EANs duplicados e
  heatmap dia-da-semana × hora destacando os horários com menor faturamento.

## Setup

1. **AWS / RDS**
   - O usuário IAM precisa da permissão `rds-db:connect` no ARN do usuário do
     banco (`postgres`).
   - Smoke-test com `psql` usando o CA bundle do sistema:
     ```bash
     export RDSHOST="database-1.cluster-cx8gk8sogfmb.us-east-2.rds.amazonaws.com"
     export SYSTEM_CA="/etc/ssl/certs/ca-certificates.crt"
     psql "host=$RDSHOST port=5432 dbname=postgres user=postgres sslmode=verify-full \
       sslrootcert=$SYSTEM_CA \
       password=$(aws rds generate-db-auth-token --hostname $RDSHOST --port 5432 --username postgres --region us-east-2)" \
       -c "SELECT 1"
     ```
   - O `secrets.toml` já aponta para `/etc/ssl/certs/ca-certificates.crt` com
     `sslmode = "verify-full"`. Em distros não-Debian, ajuste o caminho (ex.:
     `/etc/pki/tls/certs/ca-bundle.crt` no RHEL/Fedora).

2. **Dependências**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Secrets**
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # edite com Dominio + xSenha reais
   ```

4. **Rodar**
   ```bash
   streamlit run app.py
   ```

   Na primeira execução o app cria o schema `drsistemas` e suas tabelas.
   Use a barra lateral para:
   - **Sweep de produtos** (1..N): popula `products`, `product_codes`, `product_prices`.
   - **Vendas (incremental)**: popula `sales_movements`, `sales_items`.
   - **Backfill**: completa produtos vistos em vendas mas ausentes do cadastro.

## Arquitetura

- `wsretaguarda/` — transporte SOAP (gzip + base64) e parsers XML.
- `db/` — engine SQLAlchemy com `creator` que gera token IAM a cada checkout
  (TTL de 15 min), schema e queries.
- `sync/` — sweep paralelo de produtos e pull incremental de vendas.
- `app.py` + `pages/` — Streamlit (entry + páginas Produtos e Dashboard).

A API SOAP **não tem endpoint de listagem de produtos** — `retProduto` busca
um por vez por `IdProduto`. Por isso fazemos sweep + harvest a partir das
vendas e cacheamos tudo em Postgres.
