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
| `POST /private/v1/cancelOrders` | 複数注文キャンセル (ID指定) | ✅ `post_cancel_orders_py` |
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
| `timeInForce` | ✅ (FAK/FAS/FOK/SOK 対応) |
| `losscutPrice` | ❌ (changeOrderのみ対応) |
| `cancelBefore` | ✅ |

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
| `DELETE /private/v1/ws-auth` | トークン削除 | ⚠️ `delete_ws_auth_py` (署名検証に問題あり) |

### Private WebSocket (`wss://api.coin.z.com/ws/private/v1/{token}`)

| チャンネル | 説明 | 実装 |
|-----------|------|------|
| `executionEvents` | 約定通知 | ✅ 購読済み |
| `orderEvents` | 注文変更通知 | ✅ 購読済み |
| `positionEvents` | 建玉変更通知 | ⚠️ ハンドラのみ (未購読) |
| `positionSummaryEvents` | 建玉サマリー通知 | ⚠️ ハンドラのみ (未購読) |

### NautilusTrader連携機能

| 機能 | 実装 |
|------|------|
| QuoteTick (ticker→bid/ask) | ✅ |
| TradeTick (trades→price/size/side) | ✅ |
| OrderBookDeltas (orderbooks→snapshot) | ✅ |
| Bar (klines→OHLCV) | ❌ `_subscribe_bars` は警告ログのみ |
| submit_order (MARKET/LIMIT/STOP + TimeInForce) | ✅ |
| cancel_order | ✅ |
| modify_order (changeOrder) | ✅ `ModifyOrder` → `change_order` |
| generate_order_status_reports | ✅ `get_active_orders` から生成 |
| generate_fill_reports | ✅ `get_latest_executions` から生成 |
| generate_position_status_reports | ⚠️ 空リスト返却 (v0.2) |

---

## 未実装機能の詳細

### ~~1. Token Bucket レート制限~~ (実装済み)

`src/rate_limit.rs` に `TokenBucket` 構造体を実装。REST API (GET/POST) とWebSocket購読に適用。
Python Config の `rate_limit_per_sec` / `ws_rate_limit_per_sec` で設定可能。

- デフォルト: REST 20 req/s (Tier 1), WS 0.5 cmd/s
- Tier 2設定例: `rate_limit_per_sec=30.0`

### 1. アカウント情報系エンドポイント

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

### 3. `DELETE /private/v1/ws-auth` 署名問題

**優先度: Low**

`delete_ws_auth_py` は実装済みだが、DELETEリクエストのbody付き署名がGMOコインで正しく検証されない。
トークンは60分で自動失効するため実用上の影響は小さい。

### 4. `trades` チャンネル `TAKER_ONLY` オプション

**優先度: Low**

```json
{"command": "subscribe", "channel": "trades", "symbol": "BTC", "option": "TAKER_ONLY"}
```

Taker約定のみをフィルタリングして受信。`subscribe()` に `option` パラメータ追加が必要。

### 5. `_subscribe_bars` (Bar/OHLCV リアルタイム)

**優先度: Low**

GMOコインにはBar用のWebSocketチャンネルがないため、REST `get_klines` のポーリングまたは
Tickデータからのローカル集計が必要。現在は警告ログを出力するのみ。

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
| `losscutPrice` パラメータ | `post_order_py` に追加 | 新規注文時のロスカット価格 |

---

## その他

- [ ] ユニットテスト作成 (`tests/` ディレクトリ)
- [ ] 約定テスト (JPY入金後に小額LIMIT注文 → 約定 → WS通知確認)
- [ ] エラーハンドリング強化 (ネットワーク断時のリトライ戦略改善)
- [ ] `eprintln!` ログを `tracing` クレートに移行
