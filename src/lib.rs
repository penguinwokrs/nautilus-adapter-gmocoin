#![allow(non_local_definitions)]

use pyo3::prelude::*;

mod client;
mod error;
mod model;

#[pymodule]
fn _nautilus_gmocoin(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<client::rest::GmocoinRestClient>()?;
    m.add_class::<client::data_client::GmocoinDataClient>()?;
    m.add_class::<client::execution_client::GmocoinExecutionClient>()?;

    // Models
    m.add_class::<model::market_data::Ticker>()?;
    m.add_class::<model::market_data::Depth>()?;
    m.add_class::<model::market_data::Trade>()?;
    m.add_class::<model::market_data::SymbolInfo>()?;
    m.add_class::<model::orderbook::OrderBook>()?;
    Ok(())
}
