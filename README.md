# 駅のみマッチ（安全MVP）

高崎線（上尾〜本庄）に限定した、同意ベースの駅近マッチングです。本リポジトリは他プロジェクトと干渉しない独立構成です。

## 機能

- 20歳以上のユーザー登録 (`POST /users`)
- 安全ポリシー (`GET /policy/safety`)
- 対象駅一覧 (`GET /stations`)
- 駅徒歩10分以内の候補 (`GET /venues`)
- 承認制マッチ (`POST /matches`, `POST /matches/{id}/decision`)
- 承認後チャット (`POST /matches/{id}/messages`)
- 通報・ブロック・監査ログ (`/safety/*`)
- SNS下書き→承認→公開 (`/social/drafts*`)
- IP単位レート制限、CORS制限、セキュリティヘッダ

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

[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## スモークテスト

```bash
cd station-match-safe
set PYTHONPATH=.
python scripts/mvp_smoke_test.py
python -m pytest -q
```
