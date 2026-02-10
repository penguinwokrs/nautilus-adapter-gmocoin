# nautilus-adapter-gmocoin

[NautilusTrader](https://nautilustrader.io/) 用の GMO Coin アダプター。Rust による高速な REST/WebSocket クライアントを Python から利用できます。

## 特徴

- **Rust 実装**: pyo3 によるネイティブ拡張で高速な API 通信
- **データクライアント**: ティッカー、板情報、約定、K線のリアルタイム取得
- **実行クライアント**: 注文送信・キャンセル・残高照会
- **NautilusTrader 完全対応**: DataClient / ExecutionClient として TradingNode に統合

## 要件

- Python 3.11+
- NautilusTrader 1.222+

## インストール

### GitHub Release から（推奨）

[Releases](https://github.com/penguinwokrs/nautilus-adapter-gmocoin/releases) からお使いの環境用の wheel をダウンロードしてインストール:

```bash
pip install nautilus_adapter_gmocoin-0.1.0-cp311-abi3-manylinux_2_34_x86_64.whl
```

対応プラットフォーム: Linux (x86_64, aarch64)

### ソースからビルド

```bash
pip install maturin
maturin build --release
pip install target/wheels/nautilus_adapter_gmocoin-*.whl
```

### 開発モード

```bash
pip install maturin
maturin develop --release
pip install pytest nautilus-trader  # テスト用
```

## クイックスタート

```python
import os
from nautilus_trader.live.node import TradingNode
from nautilus_trader.config import TradingNodeConfig, LoggingConfig, InstrumentProviderConfig

from nautilus_gmocoin.config import GmocoinDataClientConfig, GmocoinExecClientConfig
from nautilus_gmocoin.factories import GmocoinDataClientFactory, GmocoinExecutionClientFactory

# API キーは環境変数で設定
data_config = GmocoinDataClientConfig(
    api_key=os.environ["GMOCOIN_API_KEY"],
    api_secret=os.environ["GMOCOIN_API_SECRET"],
    instrument_provider=InstrumentProviderConfig(
        load_all=False,
        load_ids=frozenset(["BTC/JPY.GMOCOIN"]),
    ),
)

exec_config = GmocoinExecClientConfig(
    api_key=os.environ["GMOCOIN_API_KEY"],
    api_secret=os.environ["GMOCOIN_API_SECRET"],
    instrument_provider=InstrumentProviderConfig(
        load_all=False,
        load_ids=frozenset(["BTC/JPY.GMOCOIN"]),
    ),
)

node_config = TradingNodeConfig(
    trader_id="TRADER-001",
    data_clients={"GMOCOIN": data_config},
    exec_clients={"GMOCOIN": exec_config},
    logging=LoggingConfig(log_level="INFO"),
)

node = TradingNode(config=node_config)
node.add_data_client_factory("GMOCOIN", GmocoinDataClientFactory)
node.add_exec_client_factory("GMOCOIN", GmocoinExecutionClientFactory)
node.build()
node.run()
```

サンプル実行:

```bash
export GMOCOIN_API_KEY=your_api_key
export GMOCOIN_API_SECRET=your_api_secret
python examples/full_trading_node.py
```

## 設定

| オプション | 型 | デフォルト | 説明 |
|-----------|-----|----------|------|
| `api_key` | str | 必須 | GMO Coin API キー |
| `api_secret` | str | 必須 | GMO Coin API シークレット |
| `timeout_ms` | int | 10000 | REST API タイムアウト（ミリ秒） |
| `proxy_url` | str | None | プロキシ URL |
| `order_book_depth` | int | 20 | 板情報の深さ（DataClient） |
| `rate_limit_per_sec` | float | None | REST API レート制限（デフォルト: Tier 1） |

## テスト

```bash
pytest tests/ -v
```

API キーが必要なテスト（`test_rest_private.py`）は環境変数未設定時にスキップされます。

## CI / CD

- **PR**: 全ブランチへの PR でテストを実行
- **main へのマージ**: テスト通過後、自動ビルド・GitHub Release 作成
- **ブランチ保護**: main へのマージには `Test` ステータスチェックの成功が必須

## ライセンス

LGPL-3.0-or-later
