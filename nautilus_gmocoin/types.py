# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2024 Penguinworks. All rights reserved.
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
# -------------------------------------------------------------------------------------------------
"""
GMO Coin adapter custom types.
"""

from enum import Enum, auto
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


class GmocoinOrderStatus(Enum):
    WAITING = auto()
    ORDERED = auto()
    MODIFYING = auto()
    CANCELLING = auto()
    CANCELED = auto()
    EXECUTED = auto()
    EXPIRED = auto()

    @classmethod
    def from_str(cls, value: str) -> "GmocoinOrderStatus":
        mapping = {
            "WAITING": cls.WAITING,
            "ORDERED": cls.ORDERED,
            "MODIFYING": cls.MODIFYING,
            "CANCELLING": cls.CANCELLING,
            "CANCELED": cls.CANCELED,
            "EXECUTED": cls.EXECUTED,
            "EXPIRED": cls.EXPIRED,
        }
        return mapping.get(value.upper(), cls.WAITING)


class GmocoinOrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

    @classmethod
    def from_str(cls, value: str) -> "GmocoinOrderSide":
        return cls.BUY if value.upper() == "BUY" else cls.SELL


class GmocoinOrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"

    @classmethod
    def from_str(cls, value: str) -> "GmocoinOrderType":
        mapping = {
            "MARKET": cls.MARKET,
            "LIMIT": cls.LIMIT,
            "STOP": cls.STOP,
        }
        return mapping.get(value.upper(), cls.MARKET)


class GmocoinTimeInForce(Enum):
    FAK = "FAK"  # Fill and Kill (IOC)
    FAS = "FAS"  # Fill and Store (GTC)
    FOK = "FOK"  # Fill or Kill
    SOK = "SOK"  # Post-only / maker only


@dataclass
class GmocoinOrderInfo:
    order_id: int
    symbol: str
    side: GmocoinOrderSide
    execution_type: GmocoinOrderType
    size: Decimal
    executed_size: Decimal
    price: Optional[Decimal]
    status: GmocoinOrderStatus
    timestamp: str

    @property
    def is_open(self) -> bool:
        return self.status in (
            GmocoinOrderStatus.WAITING,
            GmocoinOrderStatus.ORDERED,
            GmocoinOrderStatus.MODIFYING,
        )

    @property
    def is_filled(self) -> bool:
        return self.status == GmocoinOrderStatus.EXECUTED

    @property
    def is_canceled(self) -> bool:
        return self.status == GmocoinOrderStatus.CANCELED


@dataclass
class GmocoinExecution:
    execution_id: int
    order_id: int
    symbol: str
    side: GmocoinOrderSide
    size: Decimal
    price: Decimal
    fee: Decimal
    timestamp: str


@dataclass
class GmocoinAsset:
    symbol: str
    amount: Decimal
    available: Decimal

    @property
    def locked(self) -> Decimal:
        return self.amount - self.available
