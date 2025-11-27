# Cloudflare D1 数据库导入指南

本文档介绍如何将本地生成的 SQLite 数据库 (`stock_data.db`) 导入到 Cloudflare D1，并说明如何进行日常更新。

## 前置条件

1.  拥有 Cloudflare 账号。
2.  安装并配置 `wrangler` 命令行工具。
    ```bash
    npm install -g wrangler
    wrangler login
    ```

## 1. 创建 D1 数据库

在 Cloudflare 控制台或使用命令行创建数据库。

```bash
wrangler d1 create stock-data
```

记下输出中的 `database_id`，后续配置 `wrangler.toml` 需要用到。

## 2. 首次导入数据

由于 Cloudflare D1 的免费版每日写入限制为 **100,000 行**，而我们的初始化数据可能超过这个限制（800只股票 * 300+天 ≈ 240,000 行），因此首次导入建议直接上传 SQLite 数据库文件，或者分批执行 SQL。

**推荐方法：直接上传 SQLite 文件 (覆盖)**

D1 允许直接通过 HTTP API 或 Wrangler 上传 SQLite 文件来覆盖数据库（注意：这会删除现有数据）。

但是，目前 `wrangler d1 execute` 主要用于执行 SQL。对于初始化大量数据，最稳妥的方式是生成 SQL 文件并分批执行，或者使用 D1 的导入功能（如果可用）。

**方法 A: 生成 SQL 文件并执行**

1.  将本地 SQLite 数据库导出为 SQL 文件：
    ```bash
    sqlite3 stock_data.db .dump > dump.sql
    ```

2.  执行 SQL 文件导入：
    ```bash
    wrangler d1 execute stock-data --file=dump.sql
    ```
    *注意：如果文件过大，可能需要手动拆分 SQL 文件。*

**方法 B: 本地测试与迁移**

如果只是本地测试，可以使用 `wrangler d1 execute` 直接操作本地数据库文件（不适用，D1 是远程的）。

## 3. 日常更新 (自动化)

为了遵守每日 100,000 行的写入限制，我们不能每天都全量覆盖数据。我们需要增量更新。

我们提供了一个脚本 `update_d1.py` 和 GitHub Action 来自动完成每日更新。

### 3.1 `update_d1.py` 脚本原理

该脚本会：
1.  获取当天的沪深300和中证500成分股列表。
2.  获取这些股票 **当天** 的 K 线数据。
3.  生成一个 `update.sql` 文件，包含 `INSERT` 语句。
4.  每天的数据量约为 800 行，远低于 100,000 行的限制。

### 3.2 配置 GitHub Action

在 GitHub 仓库中配置以下 Secrets：

*   `CLOUDFLARE_API_TOKEN`: Cloudflare API 令牌 (需要 D1 编辑权限)。
*   `CLOUDFLARE_ACCOUNT_ID`: Cloudflare 账户 ID。

GitHub Action (`.github/workflows/daily_update.yml`) 会在每个交易日结束后自动运行，获取最新数据并推送到 D1。

## 4. 免费版限制说明

*   **每日写入行数**: 100,000 行。
*   **数据库大小**: 500 MB。
*   **读取操作**: 每天 500 万次。

请务必确保 `update_d1.py` 仅生成增量数据的 SQL，避免触发限制。
