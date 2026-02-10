# TODO: nautilus-adapter-gmocoin

## GMOコイン公式API vs アダプタ実装状況

### Public REST API

| エンドポイント | 説明 | 実装 |
|---------------|------|------|
| `GET /public/v1/status` | 取引所ステータス | ✅ `get_status_py` |
| `GET /public/v1/ticker` | 最新レート | ✅ `get_ticker_py` |
| `GET /public/v1/orderbooks` | 板情報 | ✅ `get_orderbooks_py` |
| `GET /public/v1/trades` | 取引履歴 | ✅ `get_trades_py` |
| `GET /public/v1/klines` | ローソク足 | ✅ `get_klines_py` |
| `GET /public/v1/symbols` | 取扱銘柄情報 | ✅ `get_symbols_py` |

### Public WebSocket (`wss://api.coin.z.com/ws/public/v1`)

| チャンネル | 説明 | 実装 |
|-----------|------|------|
| `ticker` | リアルタイムレート | ✅ |
| `orderbooks` | 板情報 | ✅ |
| `trades` | 約定情報 | ✅ |
| `trades` (option: `TAKER_ONLY`) | Takerのみフィルタ | ❌ |

### Private REST API - アカウント

| エンドポイント | 説明 | 実装 |
|---------------|------|------|
| `GET /private/v1/account/assets` | 資産残高 | ✅ `get_assets_py` |
| `GET /private/v1/account/margin` | 余力情報 | ❌ |
| `GET /private/v1/account/tradingVolume` | 取引高情報 | ❌ |
| `GET /private/v1/account/fiatDepositHistory` | JPY入金履歴 | ❌ |
| `GET /private/v1/account/fiatWithdrawalHistory` | JPY出金履歴 | ❌ |
| `GET /private/v1/account/depositHistory` | 暗号資産入金履歴 | ❌ |
| `GET /private/v1/account/withdrawalHistory` | 暗号資産出金履歴 | ❌ |
| `POST /private/v1/account/transfer` | 振替 (現物↔レバレッジ) | ❌ |

### Private REST API - 注文

| エンドポイント | 説明 | 実装 |
|---------------|------|------|
| `POST /private/v1/order` | 新規注文 | ✅ `post_order_py` |
| `POST /private/v1/changeOrder` | 注文変更 | ✅ `post_change_order_py` |
| `POST /private/v1/cancelOrder` | 注文キャンセル | ✅ `post_cancel_order_py` |
| `POST /private/v1/cancelOrders` | 複数注文キャンセル (ID指定) | ❌ |
| `POST /private/v1/cancelBulkOrder` | 一括注文キャンセル (銘柄指定) | ✅ `post_cancel_bulk_order_py` |
| `GET /private/v1/orders` | 注文情報取得 | ✅ `get_order_py` |
| `GET /private/v1/activeOrders` | 有効注文一覧 | ✅ `get_active_orders_py` |
| `GET /private/v1/executions` | 約定情報取得 | ✅ `get_executions_py` |
| `GET /private/v1/latestExecutions` | 最新約定一覧 | ✅ `get_latest_executions_py` |

### Private REST API - 注文パラメータ

| パラメータ | `post_order` での対応 |
|-----------|---------------------|
| `symbol` | ✅ |
| `side` | ✅ |
| `executionType` | ✅ |
| `size` | ✅ |
| `price` | ✅ |
| `timeInForce` | ✅ |
| `losscutPrice` | ❌ (changeOrderのみ対応) |
| `cancelBefore` | ❌ |

### Private REST API - ポジション (レバレッジ取引)

| エンドポイント | 説明 | 実装 |
|---------------|------|------|
| `GET /private/v1/openPositions` | 建玉一覧 | ❌ |
| `GET /private/v1/positionSummary` | 建玉サマリー | ❌ |
| `POST /private/v1/closeOrder` | 決済注文 | ❌ |
| `POST /private/v1/closeBulkOrder` | 一括決済注文 | ❌ |
| `PUT /private/v1/losscutPrice` | ロスカットレート変更 | ❌ |

### Private REST API - WebSocket認証

| エンドポイント | 説明 | 実装 |
|---------------|------|------|
| `POST /private/v1/ws-auth` | アクセストークン取得 | ✅ `post_ws_auth_py` |
| `PUT /private/v1/ws-auth` | トークン延長 | ✅ `put_ws_auth_py` |
| `DELETE /private/v1/ws-auth` | トークン削除 | ❌ |

### Private WebSocket (`wss://api.coin.z.com/ws/private/v1/{token}`)

| チャンネル | 説明 | 実装 |
|-----------|------|------|
| `executionEvents` | 約定通知 | ✅ 購読済み |
| `orderEvents` | 注文変更通知 | ✅ 購読済み |
| `positionEvents` | 建玉変更通知 | ⚠️ ハンドラのみ (未購読) |
| `positionSummaryEvents` | 建玉サマリー通知 | ⚠️ ハンドラのみ (未購読) |

### NautilusTrader連携機能

| 機能 | 説明 | 実装 |
|------|------|------|
| QuoteTick (ticker→bid/ask) | ✅ |  |
| TradeTick (trades→price/size/side) | ✅ |  |
| OrderBookDeltas (orderbooks→snapshot) | ✅ |  |
| Bar (klines→OHLCV) | ❌ `_subscribe_bars` は警告ログのみ |  |
| submit_order (MARKET/LIMIT/STOP) | ✅ |  |
| cancel_order | ✅ |  |
| modify_order (changeOrder) | ❌ Python ExecutionClient未対応 |  |
| generate_order_status_reports | ⚠️ 空リスト返却 |  |
| generate_fill_reports | ⚠️ 空リスト返却 |  |
| generate_position_status_reports | ⚠️ 空リスト返却 |  |

---

## 未実装機能の詳細

### 1. Token Bucket レート制限

**優先度: Medium**

GMOコインAPIにはTier別のレート制限があり、超過すると `ERR-5003 (Request too many)` エラーが返される。
現在はWebSocket購読間の2秒ディレイで暫定対応。

| Tier | 対象 | 制限 |
|------|------|------|
| Tier 1 (週間取引高 < 10億円) | 全API | GET: 20 req/s, POST: 20 req/s |
| Tier 2 (週間取引高 ≥ 10億円) | 全API | GET: 30 req/s, POST: 30 req/s |
| WebSocket | 購読コマンド | 約1コマンド/秒 |

**実装方針:**
- Rust側に `TokenBucket` 構造体を追加 (`src/rate_limit.rs`)
- `GmocoinRestClient` の `public_get` / `private_get` / `private_post` に組み込み
- WebSocket購読にも適用
- Python Config から設定可能にする

**暫定対応箇所:**
- `src/client/data_client.rs` L170-172 (購読間2sディレイ)
- `src/client/execution_client.rs` L207-211 (同上)

### 2. `POST /private/v1/cancelOrders` (複数注文ID指定キャンセル)

**優先度: Low**

`cancelBulkOrder` (銘柄単位の一括キャンセル) は実装済みだが、特定の注文IDリストを指定するキャンセルは未実装。

```
POST /private/v1/cancelOrders
Body: {"orderIds": [123, 456, 789]}
```

### 3. アカウント情報系エンドポイント

**優先度: Low** (NautilusTrader直接連携には不要)

| エンドポイント | 用途 |
|---------------|------|
| `GET /v1/account/margin` | レバレッジ余力。現物のみ (v0.1) では不要 |
| `GET /v1/account/tradingVolume` | 取引高。レート制限Tier判定に使える |
| `GET /v1/account/fiatDepositHistory` | JPY入金履歴。監査/ログ用途 |
| `GET /v1/account/fiatWithdrawalHistory` | JPY出金履歴。監査/ログ用途 |
| `GET /v1/account/depositHistory` | 暗号資産入金履歴。監査/ログ用途 |
| `GET /v1/account/withdrawalHistory` | 暗号資産出金履歴。監査/ログ用途 |
| `POST /v1/account/transfer` | 現物↔レバレッジ口座振替。v0.2で必要 |

### 4. `DELETE /private/v1/ws-auth` (WSトークン削除)

**優先度: Low**

disconnect時にトークンを明示的に無効化する。現在は放置で有効期限切れに依存。

### 5. 注文パラメータ拡張

**優先度: Medium**

| パラメータ | 説明 | 対応方針 |
|-----------|------|---------|
| `losscutPrice` | ロスカット価格 (レバレッジ用) | v0.2で `post_order_py` に追加 |
| `cancelBefore` | 注文前に既存注文をキャンセル | `post_order_py` にオプション追加 |

### 6. `trades` チャンネル `TAKER_ONLY` オプション

**優先度: Low**

```json
{"command": "subscribe", "channel": "trades", "symbol": "BTC", "option": "TAKER_ONLY"}
```

Taker約定のみをフィルタリングして受信。`subscribe()` に `option` パラメータ追加が必要。

### 7. NautilusTrader レポート機能

**優先度: Medium**

| メソッド | 現状 | 対応方針 |
|---------|------|---------|
| `generate_order_status_reports` | 空リスト | `get_active_orders` + `get_orders` で実装 |
| `generate_fill_reports` | 空リスト | `get_latest_executions` で実装 |
| `generate_position_status_reports` | 空リスト | v0.2でポジション対応時に実装 |

### 8. `_subscribe_bars` (Bar/OHLCV リアルタイム)

**優先度: Low**

GMOコインにはBar用のWebSocketチャンネルがないため、REST `get_klines` のポーリングまたは
Tickデータからのローカル集計が必要。現在は警告ログを出力するのみ。

### 9. `modify_order` (Python ExecutionClient)

**優先度: Medium**

Rust側の `post_change_order_py` は実装済みだが、Python `GmocoinExecutionClient` に
`modify_order(command: ModifyOrder)` メソッドが未実装。NautilusTraderの注文変更機能を利用するために必要。

---

## ポジション/レバレッジ対応 (v0.2)

| 機能 | エンドポイント | 説明 |
|------|---------------|------|
| マージンロング | `POST /v1/order` (`settleType=OPEN`) | 信用買い |
| 空売り (ショート) | `POST /v1/order` (`settleType=OPEN`, `side=SELL`) | 信用売り |
| 決済注文 | `POST /v1/closeOrder` | 個別決済 |
| 一括決済 | `POST /v1/closeBulkOrder` | 銘柄単位一括決済 |
| 建玉一覧 | `GET /v1/openPositions` | ポジション取得 |
| 建玉サマリー | `GET /v1/positionSummary` | サマリー取得 |
| ロスカットレート変更 | `PUT /v1/losscutPrice` | ロスカット価格変更 |
| 口座振替 | `POST /v1/account/transfer` | 現物↔レバレッジ |
| 余力情報 | `GET /v1/account/margin` | レバレッジ余力 |
| WS 建玉通知 | `positionEvents` チャンネル購読 | ハンドラは実装済み |
| WS 建玉サマリー通知 | `positionSummaryEvents` チャンネル購読 | ハンドラは実装済み |

---

## その他

- [ ] ユニットテスト作成 (`tests/` ディレクトリ)
- [ ] 約定テスト (JPY入金後に小額LIMIT注文 → 約定 → WS通知確認)
- [ ] エラーハンドリング強化 (ネットワーク断時のリトライ戦略改善)
- [ ] `eprintln!` ログを `tracing` クレートに移行
