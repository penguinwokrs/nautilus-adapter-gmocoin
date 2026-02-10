"""
Example: Full TradingNode setup with GMO Coin adapter.

Usage:
    python examples/full_trading_node.py

Environment variables required:
    GMOCOIN_API_KEY
    GMOCOIN_API_SECRET
"""

import os
from nautilus_trader.live.node import TradingNode
from nautilus_trader.config import TradingNodeConfig, LoggingConfig, InstrumentProviderConfig

from nautilus_gmocoin.config import GmocoinDataClientConfig, GmocoinExecClientConfig
from nautilus_gmocoin.factories import GmocoinDataClientFactory, GmocoinExecutionClientFactory


def main():
    api_key = os.environ.get("GMOCOIN_API_KEY", "")
    api_secret = os.environ.get("GMOCOIN_API_SECRET", "")

    if not api_key or not api_secret:
        print("Please set GMOCOIN_API_KEY and GMOCOIN_API_SECRET environment variables")
        return

    data_config = GmocoinDataClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        instrument_provider=InstrumentProviderConfig(
            load_all=False,
            load_ids=frozenset(["BTC/JPY.GMOCOIN"]),
        ),
    )

    exec_config = GmocoinExecClientConfig(
        api_key=api_key,
        api_secret=api_secret,
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

    # Add your strategy here:
    # node.trader.add_strategy(your_strategy)

    node.build()

    try:
        node.run()
    except KeyboardInterrupt:
        node.dispose()


if __name__ == "__main__":
    main()
