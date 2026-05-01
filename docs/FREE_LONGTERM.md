# 長期・無料に近い運用（推奨）

Render の **無料 Postgres は作成から30日で期限切れ**になります（[Deploy for Free](https://render.com/docs/free)）。  
「完全無料で長く動かす」なら **Web は Render 無料**、**DB は別サービスの無料 Postgres** が現実的です。

ここでは **Neon**（サーバレス Postgres、無料枠あり）を例にします。別プロバイダ（Supabase 等）でも同様に、`DATABASE_URL` を Render の環境変数に入れれば動きます。

## あなたがやること（順番固定）

### A. Neon で DB を作る（無料枠）

1. [https://console.neon.tech/](https://console.neon.tech/) でアカウント作成
2. **Create project**（リージョンは東京に近いものがあれば優先）
3. 接続文字列（**Connection string** / URI）をコピー  
   - 形式は `postgresql://...` または `postgres://...`  
   - `sslmode=require` が付いていなくても、このアプリ側で TLS を付与します（`app/db.py`）

### B. Render で Web だけデプロイ

**Blueprint でも可**（`render.yaml` に DB定義はありません）。初回に **シークレット入力**を求められます。

1. [https://dashboard.render.com/](https://dashboard.render.com/) → **New +** → **Blueprint**
2. リポジトリ `YMD-yamada/station-match-safe` を選択
3. 画面の指示で **`DATABASE_URL`** に Neon の URI を貼り付け  
4. デプロイ完了後、Web の URL を確認（例: `https://station-match-safe.onrender.com`）

### C. CORS を本番 URL に固定（必須）

1. Render → `station-match-safe` → **Environment**
2. **`ALLOW_ORIGINS`** に、手順 B の **本番 URL を引用符なしで1行**（例）

```text
https://station-match-safe.onrender.com
```

3. Save → 再デプロイ完了を待つ

### D. 動作確認

- `<APP>/health`
- `<APP>/policy/safety`
- `<APP>/stations`
- `<APP>/venues?station=熊谷`

## 課金が「スケール前」に起き得る箇所（注意）

Render の無料 Webは、**外向き帯域**や**ビルドパイプライン分**の超過で、公式上は **追加課金** または **支払い方法なしなら停止** があり得ます（[Deploy for Free](https://render.com/docs/free) の *Bandwidth and build pipeline*）。  
ユーザー数が少ない段階では通常問題になりにくいですが、**完全ゼロ円保証**はプラットフォーム側に依存します。月1回 [Billing の Included usage](https://dashboard.render.com/billing#included-usage) を見るのが安全です。

## Neon 側の注意

Neon の無料枠にも **容量・CU時間の上限**があります。上限に達すると **書き込み不可やスリープ**などの制限が出ることがあります（Neon の料金/ドキュメントを参照）。  
小規模利用では通常十分ですが、**「永久無制限無料」ではない**点だけ押さえてください。
