# 本番リリース手順（Render）

## 前提

このフォルダ単体を Git リポジトリのルートにするのが最も簡単です。モノレポの場合は [MONOREPO.md](MONOREPO.md) を参照してください。

## 1) GitHub に公開

1. 新規リポジトリ作成: [https://github.com/new](https://github.com/new)
2. このディレクトリのみを push（例）:

```bash
cd station-match-safe
git init
git add .
git commit -m "release: station-only match MVP"
git branch -M main
git remote add origin <YOUR_REPO_URL>
git push -u origin main
```

## 2) Render で Blueprint デプロイ

1. Render ダッシュボード: [https://dashboard.render.com/](https://dashboard.render.com/)
2. **New +** → **Blueprint**
3. GitHub リポジトリを接続し、ルートの `render.yaml` を選択
4. Web サービス `station-match-safe` と PostgreSQL `station-match-db` が作成される
5. Web サービスの **Environment** で `ALLOW_ORIGINS` を設定:
   - デプロイ完了後に表示される URL（例: `https://station-match-safe.onrender.com`）をそのまま入力
   - 複数ドメインはカンマ区切り（例: `https://app.example.com,https://www.example.com`）

## 3) リリース確認（URL は実際の値に置き換え）

- ヘルス: `https://<YOUR_SERVICE>.onrender.com/health`
- ポリシー: `https://<YOUR_SERVICE>.onrender.com/policy/safety`
- 駅一覧: `https://<YOUR_SERVICE>.onrender.com/stations`
- 候補: `https://<YOUR_SERVICE>.onrender.com/venues?station=熊谷`

## 4) セキュリティ確認

- CORS が本番ドメインのみになっていること（`ALLOW_ORIGINS`）
- レスポンスヘッダに `X-Frame-Options`, `X-Content-Type-Options`, `Content-Security-Policy` が付与されていること
- 過剰アクセスで `429` が返ること（レート制限）

## 5) 運用

- ログ: Render ダッシュボードの **Logs**
- メトリクス: `GET /metrics`
- 監査: `GET /safety/audit-logs`
