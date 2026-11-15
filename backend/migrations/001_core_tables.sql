-- 核心表结构参考（PostgreSQL 语法，运行时不执行；建表由 SQLAlchemy create_all 完成）
-- 业务：竞品券后价还原与跟价建议台（pricewatch）

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(160) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(80)  NOT NULL,
    role            VARCHAR(20)  NOT NULL,
    org             VARCHAR(120),
    created_at      TIMESTAMP    NOT NULL
);

CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    actor_email     VARCHAR(160) NOT NULL,
    actor_role      VARCHAR(20)  NOT NULL,
    action          VARCHAR(64)  NOT NULL,
    entity          VARCHAR(40)  NOT NULL,
    entity_id       VARCHAR(64),
    detail          JSON,
    layer           VARCHAR(16)  NOT NULL DEFAULT 'domain',
    ip              VARCHAR(64),
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL
);

-- 竞品店铺（种子 sources 计数口径）
CREATE TABLE competitors (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(40)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    platform        VARCHAR(20)  NOT NULL DEFAULT 'taobao',
    shop_url        VARCHAR(255),
    region          VARCHAR(40),
    owner           VARCHAR(80),
    note            TEXT,
    capture_config  JSON,
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    last_captured_at TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL
);

-- 自有 SKU：成本 / 底价 / 目标毛利 / 对标竞品
CREATE TABLE skus (
    id              SERIAL PRIMARY KEY,
    sku_code        VARCHAR(48)  NOT NULL UNIQUE,
    name            VARCHAR(160) NOT NULL,
    category        VARCHAR(20)  NOT NULL,
    competitor_id   INTEGER      NOT NULL REFERENCES competitors(id),
    competitor_item_id VARCHAR(64),
    unit            VARCHAR(16)  NOT NULL DEFAULT '件',
    cost            DOUBLE PRECISION NOT NULL DEFAULT 0,
    floor_price     DOUBLE PRECISION NOT NULL DEFAULT 0,
    target_margin_pct DOUBLE PRECISION NOT NULL DEFAULT 15,
    current_price   DOUBLE PRECISION NOT NULL DEFAULT 0,
    stock           INTEGER      NOT NULL DEFAULT 0,
    note            TEXT,
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL
);

-- 抓价快照：页面价 + 券配置 + 算法 A 结果
CREATE TABLE snapshots (
    id              SERIAL PRIMARY KEY,
    sku_id          INTEGER      NOT NULL REFERENCES skus(id) ON DELETE CASCADE,
    competitor_id   INTEGER      NOT NULL REFERENCES competitors(id),
    captured_on     DATE         NOT NULL,
    page_price      DOUBLE PRECISION NOT NULL,
    full_reduction  JSON,
    shop_coupon     JSON,
    platform_coupon JSON,
    member_discount DOUBLE PRECISION NOT NULL DEFAULT 1,
    stock           INTEGER      NOT NULL DEFAULT 0,
    campaign        VARCHAR(80),
    source_url      VARCHAR(255),
    effective       JSON,
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_snapshots_sku_day UNIQUE (sku_id, captured_on)
);

-- 跟价规则：作用域 + 策略 + 目标毛利 + 降幅上限
CREATE TABLE rules (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(40)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    scope_kind      VARCHAR(16)  NOT NULL DEFAULT 'global',
    scope_value     VARCHAR(64),
    sku_id          INTEGER REFERENCES skus(id) ON DELETE CASCADE,
    competitor_id   INTEGER REFERENCES competitors(id) ON DELETE CASCADE,
    strategy        VARCHAR(16)  NOT NULL DEFAULT 'guarded',
    target_margin_pct DOUBLE PRECISION NOT NULL DEFAULT 15,
    max_drop_pct    DOUBLE PRECISION NOT NULL DEFAULT 15,
    priority        INTEGER      NOT NULL DEFAULT 100,
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    note            TEXT,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL
);

-- 一次测算运行
CREATE TABLE runs (
    id              SERIAL PRIMARY KEY,
    run_no          VARCHAR(40)  NOT NULL UNIQUE,
    trigger         VARCHAR(20)  NOT NULL DEFAULT 'manual',
    status          VARCHAR(20)  NOT NULL DEFAULT 'queued',
    operator_email  VARCHAR(160) NOT NULL,
    captured_on     DATE,
    competitor_id   INTEGER REFERENCES competitors(id) ON DELETE SET NULL,
    input_count     INTEGER      NOT NULL DEFAULT 0,
    output_count    INTEGER      NOT NULL DEFAULT 0,
    metrics         JSON,
    log_text        TEXT,
    seed_key        VARCHAR(120) UNIQUE,
    started_at      TIMESTAMP    NOT NULL,
    finished_at     TIMESTAMP
);

-- 跟价建议（算法 B 输出 + 审批）
CREATE TABLE advices (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER      NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sku_id          INTEGER      NOT NULL REFERENCES skus(id) ON DELETE CASCADE,
    snapshot_id     INTEGER REFERENCES snapshots(id) ON DELETE SET NULL,
    competitor_id   INTEGER REFERENCES competitors(id) ON DELETE SET NULL,
    rule_code       VARCHAR(40),
    title           VARCHAR(200) NOT NULL,
    summary         TEXT,
    action          VARCHAR(16)  NOT NULL DEFAULT 'follow',
    severity        VARCHAR(12)  NOT NULL DEFAULT 'low',
    score           DOUBLE PRECISION NOT NULL DEFAULT 0,
    status          VARCHAR(16)  NOT NULL DEFAULT 'pending',
    current_price   DOUBLE PRECISION NOT NULL DEFAULT 0,
    suggested_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    effective_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    p10             DOUBLE PRECISION NOT NULL DEFAULT 0,
    p25             DOUBLE PRECISION NOT NULL DEFAULT 0,
    p50             DOUBLE PRECISION NOT NULL DEFAULT 0,
    margin_pct      DOUBLE PRECISION NOT NULL DEFAULT 0,
    gap_pct         DOUBLE PRECISION NOT NULL DEFAULT 0,
    payload         JSON,
    approver        VARCHAR(160),
    decide_note     TEXT,
    decided_at      TIMESTAMP,
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_advices_run_sku UNIQUE (run_id, sku_id)
);

CREATE INDEX idx_advices_status ON advices (status);
CREATE INDEX idx_advices_severity ON advices (severity);
CREATE INDEX idx_snapshots_day ON snapshots (captured_on);
CREATE INDEX idx_rules_priority ON rules (priority);
