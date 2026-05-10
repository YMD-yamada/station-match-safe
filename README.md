# 駅のみマッチ（安全MVP）

高崎線（上尾〜本庄）に限定した、同意ベースの駅近マッチングです。本リポジトリは他プロジェクトと干渉しない独立構成です。

## 機能

- ユーザー登録（JWT 発行）(`POST /users`) とログイン (`POST /auth/login`)
- プロフィール（`GET/PATCH /users/me`）、パスワード変更 (`POST /users/me/password`)
- `Authorization: Bearer` 付きの発見一覧 (`GET /discover`)
- 安全ポリシー・法的概要テキスト (`GET /policy/safety`)
- 静的ページ: `/legal/terms.html` / `/legal/privacy.html`（**ドラフト雛形**）
- 対象駅一覧 (`GET /stations`)
- 駅徒歩10分以内の候補 (`GET /venues`)
- 承認制マッチ (`POST /matches`, `POST /matches/{id}/decision`)
- 承認後チャット (`POST /matches/{id}/messages`)
- 通報・ブロック・監査ログ (`/safety/*`)
- SNS下書き→承認→公開 (`/social/drafts*`)
- IP単位レート制限、CORS制限、セキュリティヘッダ
- 任意保護の `/metrics`（`METRICS_API_KEY` と `X-Metrics-Key`）、監査ログ（`AUDIT_LOG_API_KEY` と `X-Audit-Key`）

## ローカル起動

```bash
cd station-match-safe
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

ブラウザ: `http://127.0.0.1:8000/`

環境変数は [.env.example](.env.example) を参照。

## 本番デプロイ

- **長期で無料に近い構成（推奨）**: [docs/FREE_LONGTERM.md](docs/FREE_LONGTERM.md)（Render Web 無料 + Neon 等）
- **手順索引**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## スモークテスト

```bash
cd station-match-safe
python scripts/mvp_smoke_test.py
python -m pytest -q
```

## CI

GitHub へプッシュすると `.github/workflows/ci.yml` が `pytest` とスモークを実行します。

## リリース

- **[docs/FREE_LONGTERM.md](docs/FREE_LONGTERM.md)**（Render + Neon 等）
- **[docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md)**（秘密情報・法務ドラフトの必読注意）
