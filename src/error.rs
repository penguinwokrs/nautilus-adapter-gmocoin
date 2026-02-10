use thiserror::Error;
use pyo3::prelude::*;

#[derive(Error, Debug)]
pub enum GmocoinError {
    #[error("API Request Error: {0}")]
    RequestError(#[from] reqwest::Error),

    #[error("WebSocket Error: {0}")]
    WebSocketError(#[from] tokio_tungstenite::tungstenite::Error),

    #[error("Parse Error: {0}")]
    ParseError(#[from] serde_json::Error),

    #[error("Authentication Error: {0}")]
    AuthError(String),

    #[error("Exchange Error: status={status}, {messages}")]
    ExchangeError {
        status: i32,
        messages: String,
    },

    #[error("Unknown Error: {0}")]
    Unknown(String),
}

impl From<GmocoinError> for PyErr {
    fn from(err: GmocoinError) -> Self {
        match err {
            GmocoinError::AuthError(e) => {
                pyo3::exceptions::PyPermissionError::new_err(e)
            }
            GmocoinError::ExchangeError { status, messages } => {
                pyo3::exceptions::PyRuntimeError::new_err(
                    format!("GMO Coin Error (status={}): {}", status, messages),
                )
            }
            _ => pyo3::exceptions::PyRuntimeError::new_err(err.to_string()),
        }
    }
}
