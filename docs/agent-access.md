# Giving AI agents access to the warehouse

AI agents (labor scheduling, prep forecasting, guest experience) should read curated tables, never raw ones.

## Principles

- **Agents read `metrics` only.** `store_day_metrics` contains no personal data, has a documented grain (one row per store per business date) and column descriptions written for a model to read.
- **Read-only identity.** Agents use their own service account with `bigquery.dataViewer` on the `metrics` dataset and `bigquery.jobUser` on the project. They get no access to `raw`, `staging` or `conformed`.
- **Descriptions are the contract.** dbt `description` fields are persisted to BigQuery (`persist_docs`), so an agent connected through an MCP server for BigQuery can discover what each table and column means without a human explaining it.
- **Cost guardrails.** Set a maximum bytes billed on the agent's queries and keep tables partitioned by `business_date`, so a badly formed agent query can't scan years of data.

## Connecting through MCP

Expose BigQuery to the agent through an MCP server that supports BigQuery (for example, Google's MCP Toolbox for Databases), configured with the read-only service account above and limited to the `metrics` dataset. Prefer a small set of named, parameterised queries ("sales per labor hour for store X over the last N days") over free-form SQL. They're easier to test, cheaper and harder to misuse.
