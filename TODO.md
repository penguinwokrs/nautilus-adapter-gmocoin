# TODO: nautilus-adapter-gmocoin

## Token Bucket レート制限の実装

### 背景

GMOコインAPIにはTier別のレート制限があり、超過すると `ERR-5003 (Request too many)` エラーが返される。
現在はアプリケーションレベルの遅延（WebSocket購読間の2秒ディレイ）で暫定対応しているが、
正式なToken Bucketアルゴリズムによる制御が必要。

### GMOコイン レート制限仕様

| Tier | 対象 | 制限 |
|------|------|------|
| Private API (REST) | 注文系エンドポイント | 1秒あたり約1リクエスト（注文/変更/キャンセル） |
| Private API (REST) | 参照系エンドポイント | 1秒あたり約5リクエスト |
| Public API (REST) | 全エンドポイント | 1秒あたり約10リクエスト |
| WebSocket | 購読コマンド | 1秒あたり約1コマンド |

※ 正確なレートは公式ドキュメント要確認: https://api.coin.z.com/docs/#restrictions

### 現状の暫定対応

- **WebSocket購読**: `data_client.rs` で購読送信間に2秒のディレイ挿入
  - ファイル: `src/client/data_client.rs` L170-172
  - ファイル: `src/client/execution_client.rs` L207-211
- **REST API**: 制御なし（呼び出し元の頻度に依存）

### 実装方針

#### 1. Rust側にToken Bucket構造体を追加

```rust
// src/rate_limit.rs (新規)
use std::time::{Duration, Instant};
use tokio::sync::Mutex;

pub struct TokenBucket {
    max_tokens: f64,
    refill_rate: f64, // tokens per second
    tokens: Mutex<f64>,
    last_refill: Mutex<Instant>,
}

impl TokenBucket {
    pub fn new(max_tokens: f64, refill_rate: f64) -> Self { ... }

    /// トークンが利用可能になるまで待機
    pub async fn acquire(&self) { ... }

    /// トークンが即座に利用可能かチェック（ノンブロッキング）
    pub fn try_acquire(&self) -> bool { ... }
}
```

#### 2. GmocoinRestClientに組み込み

```rust
pub struct GmocoinRestClient {
    // ... 既存フィールド
    rate_limiter_order: Arc<TokenBucket>,   // 注文系: 1 req/s
    rate_limiter_query: Arc<TokenBucket>,   // 参照系: 5 req/s
    rate_limiter_public: Arc<TokenBucket>,  // Public: 10 req/s
}
```

- `private_post()` 呼び出し前に `rate_limiter_order.acquire().await`
- `private_get()` 呼び出し前に `rate_limiter_query.acquire().await`
- `public_get()` 呼び出し前に `rate_limiter_public.acquire().await`

#### 3. WebSocket購読にも適用

```rust
// data_client.rs ws_loop内
let ws_rate_limiter = TokenBucket::new(1.0, 0.5); // 2秒間隔

for msg in to_send {
    ws_rate_limiter.acquire().await;
    ws.send(Message::Text(msg)).await?;
}
```

#### 4. Python側からのレート制限設定

```python
class GmocoinDataClientConfig(LiveDataClientConfig):
    # ... 既存フィールド
    rate_limit_orders_per_sec: float = 1.0
    rate_limit_queries_per_sec: float = 5.0
    rate_limit_public_per_sec: float = 10.0
```

### 優先度

**Medium** - 現状の暫定対応で基本的な動作は可能。高頻度取引や複数シンボル同時購読時に問題になる可能性あり。

### 関連ファイル

- `src/client/rest.rs` - REST API呼び出し（rate limiter組み込み箇所）
- `src/client/data_client.rs` - Public WebSocket購読（現在2sディレイで暫定対応）
- `src/client/execution_client.rs` - Private WebSocket購読（同上）
- `nautilus_gmocoin/config.py` - Python設定クラス（rate limit設定追加）

---

## その他 TODO

### v0.1 残作業

- [ ] ユニットテスト作成（`tests/` ディレクトリ）
- [ ] 約定テスト（JPY入金後に小額LIMIT注文 → 約定 → WS通知確認）
- [ ] `_subscribe_bars` 実装（現在は警告ログのみ）
- [ ] エラーハンドリング強化（ネットワーク断時のリトライ戦略改善）

### v0.2 (信用取引対応)

- [ ] マージンロング（`settleType=OPEN`）
- [ ] 空売り（ショート）
- [ ] ポジション決済（`POST /v1/closeOrder`）
- [ ] ポジション管理（`GET /v1/openPositions`, `/v1/positionSummary`）
- [ ] Private WS `positionEvents`, `positionSummaryEvents` チャンネル対応
