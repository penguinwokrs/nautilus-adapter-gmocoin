# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2024 Penguinworks. All rights reserved.
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------
"""
GMO Coin adapter constants.
"""

from nautilus_trader.model.identifiers import Venue


# Venue identifier
GMOCOIN_VENUE = Venue("GMOCOIN")

# API endpoints
GMOCOIN_PUBLIC_REST_URL = "https://api.coin.z.com/public"
GMOCOIN_PRIVATE_REST_URL = "https://api.coin.z.com/private"

# WebSocket endpoints
GMOCOIN_PUBLIC_WS_URL = "wss://api.coin.z.com/ws/public/v1"
GMOCOIN_PRIVATE_WS_URL = "wss://api.coin.z.com/ws/private/v1"

# Rate limits (requests per second)
GMOCOIN_RATE_LIMIT_TIER1 = 20  # <1B JPY weekly volume
GMOCOIN_RATE_LIMIT_TIER2 = 30  # >=1B JPY weekly volume

# Order status mappings (GMO Coin -> NautilusTrader string)
ORDER_STATUS_MAP = {
    "WAITING": "ACCEPTED",
    "ORDERED": "ACCEPTED",
    "MODIFYING": "ACCEPTED",
    "CANCELLING": "PENDING_CANCEL",
    "CANCELED": "CANCELED",
    "EXECUTED": "FILLED",
    "EXPIRED": "EXPIRED",
}

# Order side mappings
ORDER_SIDE_MAP = {
    "BUY": "BUY",
    "SELL": "SELL",
}

# Order type mappings (GMO Coin executionType -> NautilusTrader)
ORDER_TYPE_MAP = {
    "MARKET": "MARKET",
    "LIMIT": "LIMIT",
    "STOP": "STOP_MARKET",
}

# Reverse: NautilusTrader -> GMO Coin
NAUTILUS_TO_GMO_ORDER_TYPE = {
    "MARKET": "MARKET",
    "LIMIT": "LIMIT",
    "STOP_MARKET": "STOP",
}

# TimeInForce mappings (GMO Coin -> NautilusTrader)
TIME_IN_FORCE_MAP = {
    "FAK": "IOC",
    "FAS": "GTC",
    "FOK": "FOK",
    "SOK": "GTC",  # Post-only (maker only)
}

# Kline intervals supported by GMO Coin
KLINE_INTERVALS = [
    "1min", "5min", "10min", "15min", "30min",
    "1hour", "4hour", "8hour", "12hour",
    "1day", "1week", "1month",
]

# Error codes
ERROR_CODES = {
    0: "OK",
    1: "System error",
    5: "Maintenance",
}
