# Analytics Capability Map

The LLM plans/explains. Python/SQL tools calculate.

## Data engineering / quality
- File discovery and inspection
- CSV/XLSX/XLSM/Parquet loading
- Type/semantic role inference
- Missingness, duplicates, constant columns
- IQR and robust-Z outlier screening
- Explicit validation rules
- Schema drift
- Safe cleaning plans
- Local synthetic test data (no formal privacy guarantee)
- DuckDB read-only SQL over a local dataset

## Statistics / data science
- Descriptive statistics + confidence intervals
- Normality diagnostics
- Independent 2-group comparison: Welch t / Mann-Whitney
- Paired comparison: paired t / Wilcoxon
- 3+ group comparison: one-way ANOVA / Welch ANOVA / Kruskal-Wallis + Tukey where suitable
- Categorical association: chi-square / Fisher check + Cramer's V
- Pearson/Spearman/Kendall correlation
- Bootstrap mean CI
- Linear regression + basic heteroskedasticity/VIF diagnostics
- Logistic regression + odds ratios
- PCA
- K-Means + silhouette
- Isolation Forest anomaly screening
- Distribution drift screening
- Holt-Winters time-series forecast + holdout backtest
- Kaplan-Meier survival analysis (optional `lifelines`)
- Cross-validated random-forest baseline + permutation importance
- Monte Carlo NPV simulation

## BI / reporting
- Pivot/aggregation Excel reports
- Executive Excel dashboard template
- Self-contained interactive Plotly HTML dashboard
- PDF summary formatter

## NPL / asset management
- Portfolio balance/collection summary
- DPD aging
- Debtor concentration / HHI
- Vintage cumulative collection curve
- Count and optional balance-weighted roll-rate/migration matrix
- Actual vs target
- Single valuation scenario
- Multi-scenario NPV/MOIC grid
- Monte Carlo NPV uncertainty analysis

## Knowledge / learning
- Local PDF/DOCX/TXT/MD/CSV/XLSX knowledge ingestion
- SQLite FTS5 retrieval
- Optional Ollama embeddings for hybrid retrieval
- Editable Mentor/Senior/Executive/Technical personalities
- Human-approved business-rule memory
- Repeated tool-sequence workflow suggestions
- Local critic/reviewer command

## Windows-native Excel automation
- Optional real Excel PivotTable generation through COM (`pywin32`)
- Requires desktop Microsoft Excel
- Source workbook is not modified; a new output workbook is created
