CREATE TABLE IF NOT EXISTS {{SCHEMA}}.products (
    id_produto         INTEGER PRIMARY KEY,
    origem             INTEGER,
    status             INTEGER,
    id_imposto         INTEGER,
    desc_produto       TEXT,
    d_val              INTEGER,
    id_marca           INTEGER,
    desc_marca         TEXT,
    id_medida          INTEGER,
    desc_medida        TEXT,
    id_ncm             INTEGER,
    cod_ncm            TEXT,
    id_categoria       INTEGER,
    desc_categoria     TEXT,
    id_subcategoria    INTEGER,
    desc_subcategoria  TEXT,
    inf_adic           TEXT,
    tp_balanca         INTEGER,
    tp_item            INTEGER,
    v_compra           NUMERIC(18, 6),
    v_minimo           NUMERIC(18, 6),
    raw_xml            TEXT,
    last_synced_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.product_codes (
    id_produto    INTEGER NOT NULL,
    id_codigo     INTEGER NOT NULL,
    cod_produto   TEXT,
    id_tp_codigo  INTEGER,
    ind_status    INTEGER,
    PRIMARY KEY (id_produto, id_codigo)
);
CREATE INDEX IF NOT EXISTS ix_product_codes_cod ON {{SCHEMA}}.product_codes (cod_produto);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.product_prices (
    id_produto    INTEGER NOT NULL,
    id_preco      INTEGER NOT NULL,
    id_loja       INTEGER,
    id_tab_preco  INTEGER,
    tp_preco      INTEGER,
    status        INTEGER,
    v_compra      NUMERIC(18, 6),
    v_custo       NUMERIC(18, 6),
    v_preco       NUMERIC(18, 6),
    PRIMARY KEY (id_produto, id_preco)
);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.product_lojas (
    id_produto       INTEGER NOT NULL,
    id_loja          INTEGER NOT NULL,
    id_produto_loja  INTEGER,
    desc_local       TEXT,
    qtd_minimo       NUMERIC(18, 6),
    v_minimo         NUMERIC(18, 6),
    PRIMARY KEY (id_produto, id_loja)
);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.product_stock (
    id_produto      INTEGER NOT NULL,
    id_loja         INTEGER NOT NULL,
    fant            TEXT,
    q_saldo         NUMERIC(18, 6),
    dh_saldo        TIMESTAMPTZ,
    last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id_produto, id_loja)
);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.sales_movements (
    id_mov            UUID PRIMARY KEY,
    dh_emi            TIMESTAMPTZ,
    tp_mov            INTEGER,
    ind_status        INTEGER,
    tp_status         INTEGER,
    desc_status       TEXT,
    desc_tp           TEXT,
    tp_amb            INTEGER,
    emit_id_loja      INTEGER,
    emit_doc          TEXT,
    dest_id_cadastro  INTEGER,
    dest_doc          TEXT,
    dest_x_nome       TEXT,
    id_operador       INTEGER,
    id_caixa          INTEGER,
    num_caixa         INTEGER,
    n_nf              INTEGER,
    tot_v_nf          NUMERIC(18, 4),
    tot_q_com         NUMERIC(18, 4),
    tot_qtd_itens     INTEGER,
    tot_v_prod        NUMERIC(18, 4),
    tot_v_desc        NUMERIC(18, 4),
    tot_v_outro       NUMERIC(18, 4)
);
CREATE INDEX IF NOT EXISTS ix_sales_movements_dh_emi ON {{SCHEMA}}.sales_movements (dh_emi);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.sales_items (
    id_mov          UUID    NOT NULL REFERENCES {{SCHEMA}}.sales_movements (id_mov) ON DELETE CASCADE,
    n_item          INTEGER NOT NULL,
    id_produto      INTEGER,
    id_prod         TEXT,
    c_prod          TEXT,
    x_prod          TEXT,
    u_com           TEXT,
    q_com           NUMERIC(18, 4),
    v_un_com        NUMERIC(18, 6),
    v_prod          NUMERIC(18, 4),
    v_desc          NUMERIC(18, 4),
    v_outro         NUMERIC(18, 4),
    id_vendedor     INTEGER,
    login_vendedor  TEXT,
    inf_ad_prod     TEXT,
    PRIMARY KEY (id_mov, n_item)
);
CREATE INDEX IF NOT EXISTS ix_sales_items_id_produto ON {{SCHEMA}}.sales_items (id_produto);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.sync_log (
    resource     TEXT PRIMARY KEY,
    last_run     TIMESTAMPTZ,
    last_cursor  TEXT,
    status       TEXT,
    message      TEXT
);
