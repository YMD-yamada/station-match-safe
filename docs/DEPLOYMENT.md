# 本番デプロイ

## 推奨（長期・無料に近い）

Render 付帯の無料 Postgres（30日制限）を避け、**外部の無料 Postgres（例: Neon）+ Render 無料 Web** にします。

手順の全文: **[FREE_LONGTERM.md](FREE_LONGTERM.md)**

## 補足: モノレポから出す場合

[MONOREPO.md](MONOREPO.md)

## リリース後の確認 URL（`<APP>` は実際の Render URL）

- `<APP>/health`
- `<APP>/policy/safety`
- `<APP>/stations`
- `<APP>/venues?station=熊谷`

## セキュリティ確認

- `ALLOW_ORIGINS` が本番ドメインのみ
- レスポンスヘッダ（`X-Frame-Options` 等）
- レート制限（429）

## 運用

- ログ: Render ダッシュボード **Logs**
- メトリクス: `GET /metrics`
- 監査: `GET /safety/audit-logs`
