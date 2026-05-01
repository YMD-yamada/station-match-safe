# モノレポからデプロイする場合

親リポジトリのルートに `render.yaml` がある場合、Blueprint は通常そのファイルを読みます。

## 推奨: Web サービスを手動作成

1. [https://dashboard.render.com/](https://dashboard.render.com/) → **New +** → **Web Service**
2. リポジトリを選択
3. **Root Directory** に `station-match-safe` を指定
4. **Runtime** は Docker（このフォルダの `Dockerfile` を使用）
5. **Environment**:
   - `DATABASE_URL`: Render PostgreSQL の Internal/External URL
   - `ALLOW_ORIGINS`: 本番 URL
   - `API_RATE_LIMIT_PER_MIN`: `60`（任意）

## 代替: Blueprint にサービスを追記

親の `render.yaml` に以下のようなエントリを追加し、`rootDir: station-match-safe` を指定します（Render の Blueprint 仕様に従ってください）。

```yaml
services:
  - type: web
    name: station-match-safe
    rootDir: station-match-safe
    runtime: docker
    healthCheckPath: /health
```

データベースは Render で別途 PostgreSQL を作成し、`DATABASE_URL` を Web サービスに渡します。
