-- Schéma SQLite du bot Breakout Swing (mode WAL, mono-utilisateur local)

CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    hash TEXT NOT NULL,
    path TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    json TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS backtests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    dataset_id INTEGER REFERENCES datasets(id),
    config_id INTEGER REFERENCES configs(id),
    engine_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'en_cours',   -- en_cours | termine | erreur
    error TEXT,
    started_at INTEGER NOT NULL,
    finished_at INTEGER,
    report_json TEXT,                          -- métriques + attribution + ventilations
    equity_json TEXT                           -- courbe sous-échantillonnée pour l'UI
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER REFERENCES backtests(id),
    paper_session_id INTEGER REFERENCES paper_sessions(id),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    mode TEXT NOT NULL,
    entry_ts INTEGER NOT NULL,
    exit_ts INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    qty REAL NOT NULL,
    exit_reason TEXT NOT NULL,
    aborted INTEGER NOT NULL DEFAULT 0,
    pnl_gross REAL NOT NULL,
    entry_fee REAL NOT NULL,
    exit_fee REAL NOT NULL,
    slippage_cost REAL NOT NULL,
    funding_cost REAL NOT NULL,
    pnl_net REAL NOT NULL,
    r_multiple REAL NOT NULL,
    mae REAL NOT NULL,
    mfe REAL NOT NULL,
    signals_json TEXT
);

CREATE TABLE IF NOT EXISTS optimize_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,                        -- grid | walkforward
    dataset_id INTEGER REFERENCES datasets(id),
    base_config_json TEXT NOT NULL,
    params_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'en_cours',
    error TEXT,
    results_json TEXT,
    stability_json TEXT,
    created_at INTEGER NOT NULL,
    finished_at INTEGER
);

CREATE TABLE IF NOT EXISTS paper_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_json TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bootstrap_start_ts INTEGER NOT NULL DEFAULT 0,  -- t0 des index moteur (stable entre reprises)
    started_at INTEGER NOT NULL,
    stopped_at INTEGER,
    status TEXT NOT NULL DEFAULT 'active'      -- active | arretee
);

CREATE TABLE IF NOT EXISTS paper_state (
    session_id INTEGER PRIMARY KEY REFERENCES paper_sessions(id),
    engine_state_json TEXT NOT NULL,
    last_candle_ts INTEGER NOT NULL,
    equity REAL NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES paper_sessions(id),
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    state TEXT NOT NULL,
    evaluation_json TEXT NOT NULL,
    has_decision INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS param_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    trigger_kind TEXT NOT NULL,                -- auto | manuel
    old_config_json TEXT NOT NULL,
    new_config_json TEXT NOT NULL,
    diff_json TEXT NOT NULL,
    wf_job_id INTEGER REFERENCES optimize_jobs(id),
    stability_score REAL,
    guardrail_report_json TEXT,
    status TEXT NOT NULL,                      -- proposee | approuvee | rejetee | appliquee | auto_appliquee
    applied_at INTEGER
);

CREATE TABLE IF NOT EXISTS coherence_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES paper_sessions(id),
    backtest_id INTEGER REFERENCES backtests(id),
    period_start INTEGER NOT NULL,
    period_end INTEGER NOT NULL,
    pct_identical REAL NOT NULL,
    report_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS oi_collector (
    symbol TEXT NOT NULL,
    ts INTEGER NOT NULL,
    open_interest REAL NOT NULL,
    PRIMARY KEY (symbol, ts)
);

CREATE INDEX IF NOT EXISTS idx_trades_backtest ON trades(backtest_id);
CREATE INDEX IF NOT EXISTS idx_trades_paper ON trades(paper_session_id);
CREATE INDEX IF NOT EXISTS idx_journal_session ON decision_journal(session_id, ts);
