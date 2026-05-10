# リリース前チェックリスト（運営側作業）

> **重要**: ここにある文章は開発・運用上のチェックリストです。**法令判断やコンプライアンス適合を保証するものではありません。** サービス開始前には、運営者が管轄法域に適した資格ある専門家（法律・税務など）への相談を行ってください。

## インフラと秘密情報

- [ ] `DATABASE_URL`（本番 Postgres / Neon）が **TLS** 経由であり、アプリ側 `app/db.py` の要件を満たす
- [ ] `JWT_SECRET` を **本番専用の十分長いランダム値** に設定し、開発用デフォルトを使わない
- [ ] `ALLOW_ORIGINS` を **本番フロントのオリジンだけ** に絞る（ワイルドカードと credentials の併用に注意）
- [ ] （推奨）`AUDIT_LOG_API_KEY` を設定し、`GET /safety/audit-logs` は **`X-Audit-Key`** のみで参照
- [ ] （推奨）`METRICS_API_KEY` を設定し、`GET /metrics` は **`X-Metrics-Key`** のみで参照
- [ ] Render / PaaS の **自動デプロイ** と **環境変数** の変更履歴を把握している

## 利用者に見える文書

- [ ] [frontend/legal/terms.html](../frontend/legal/terms.html) と [privacy.html](../frontend/legal/privacy.html) は **ドラフト**。本文を事業実態・地域に合わせ **専門家レビュー後に差し替える**
- [ ] アプリ内の「同意」チェック文言と、アプリ/API の実装の間に矛盾がない

## アプリ確認 URL（ブラウザまたは curl）

- `GET /health`
- `GET /policy/safety`
- （オリジントークンがある場合）サインイン → `GET /discover`

## CI

- GitHub で **CI が緑** であること（`pytest` + スモークスクリプト）
