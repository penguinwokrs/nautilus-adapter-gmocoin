#![allow(non_local_definitions)]

use pyo3::prelude::*;

mod client;
mod error;
mod model;
mod rate_limit;

#[pymodule]
fn _nautilus_gmocoin(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize tracing subscriber (stderr) for Rust log visibility
    use std::sync::Once;
    static INIT: Once = Once::new();
    INIT.call_once(|| {
        tracing_subscriber::fmt()
            .with_target(false)
            .with_env_filter(
                tracing_subscriber::EnvFilter::try_from_default_env()
                    .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info"))
            )
            .init();
    });

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
