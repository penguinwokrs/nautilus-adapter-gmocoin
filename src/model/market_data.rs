use serde::{Deserialize, Serialize};
use pyo3::prelude::*;

#[pyclass(from_py_object)]
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Ticker {
    #[pyo3(get)]
    pub ask: String,
    #[pyo3(get)]
    pub bid: String,
    #[pyo3(get)]
    pub high: String,
    #[pyo3(get)]
    pub low: String,
    #[pyo3(get)]
    pub last: String,
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub timestamp: String,
    #[pyo3(get)]
    pub volume: String,
}

#[pymethods]
impl Ticker {
    #[new]
    pub fn new(
        ask: String,
        bid: String,
        high: String,
        low: String,
        last: String,
        symbol: String,
        timestamp: String,
        volume: String,
    ) -> Self {
        Self { ask, bid, high, low, last, symbol, timestamp, volume }
    }
}

#[pyclass(from_py_object)]
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct DepthEntry {
    #[pyo3(get)]
    pub price: String,
    #[pyo3(get)]
    pub size: String,
}

#[pyclass(from_py_object)]
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Depth {
    #[pyo3(get)]
    pub asks: Vec<DepthEntry>,
    #[pyo3(get)]
    pub bids: Vec<DepthEntry>,
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    #[serde(default)]
    pub timestamp: String,
}

#[pymethods]
impl Depth {
    #[new]
    pub fn new(asks: Vec<DepthEntry>, bids: Vec<DepthEntry>, symbol: String, timestamp: String) -> Self {
        Self { asks, bids, symbol, timestamp }
    }
}

#[pyclass(from_py_object)]
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Trade {
    #[pyo3(get)]
    pub price: String,
    #[pyo3(get)]
    pub side: String,
    #[pyo3(get)]
    pub size: String,
    #[pyo3(get)]
    pub timestamp: String,
    #[pyo3(get)]
    pub symbol: Option<String>,
}

#[pymethods]
impl Trade {
    #[new]
    pub fn new(price: String, side: String, size: String, timestamp: String, symbol: Option<String>) -> Self {
        Self { price, side, size, timestamp, symbol }
    }
}

/// Symbol info from GET /v1/symbols
#[pyclass(from_py_object)]
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct SymbolInfo {
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    #[serde(rename = "minCloseOrderSize")]
    pub min_close_order_size: Option<String>,
    #[pyo3(get)]
    #[serde(rename = "maxOrderSize")]
    pub max_order_size: Option<String>,
    #[pyo3(get)]
    #[serde(rename = "sizeStep")]
    pub size_step: Option<String>,
    #[pyo3(get)]
    #[serde(rename = "tickSize")]
    pub tick_size: Option<String>,
    #[pyo3(get)]
    #[serde(rename = "minOrderSize")]
    pub min_order_size: Option<String>,
    #[pyo3(get)]
    #[serde(rename = "takerFee")]
    pub taker_fee: Option<String>,
    #[pyo3(get)]
    #[serde(rename = "makerFee")]
    pub maker_fee: Option<String>,
}

#[pymethods]
impl SymbolInfo {
    #[new]
    pub fn new(symbol: String) -> Self {
        Self {
            symbol,
            min_close_order_size: None,
            max_order_size: None,
            size_step: None,
            tick_size: None,
            min_order_size: None,
            taker_fee: None,
            maker_fee: None,
        }
    }
}

/// Kline data from GET /v1/klines
#[derive(Deserialize, Serialize, Debug, Clone)]
#[allow(dead_code)]
pub struct Kline {
    #[serde(rename = "openTime")]
    pub open_time: String,
    pub open: String,
    pub high: String,
    pub low: String,
    pub close: String,
    pub volume: String,
}
