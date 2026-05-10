# Handoff（station-match-safe）

## 状態（2026-05-10）

- 認証: `POST /users` / `POST /auth/login`（JWT Bearer）、`/users/me`、`/discover` 保護済み
- リリース向け: `pytest` + `scripts/mvp_smoke_test.py`、GitHub Actions CI、Render `render.yaml`（`JWT_SECRET` sync false 追加）
- 監査ログ: `AUDIT_LOG_API_KEY` + `X-Audit-Key`、未設定時は 404
- メトリクス: `METRICS_API_KEY` + `X-Metrics-Key`（任意。未設定時は従来どおり公開）
- 法務: `frontend/legal/terms.html` / `privacy.html` は**ドラフト**。専門家レビュー前提。作者は法的専門家ではない。

## 次にやるなら

- Render に `JWT_SECRET` / `ALLOW_ORIGINS` / `DATABASE_URL` を設定してデプロイ
- 法律文書の差し替えと「お問い合わせ窓口」追記
