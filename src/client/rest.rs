use reqwest::{Client, Method};
use serde::de::DeserializeOwned;
use hmac::{Hmac, Mac};
use sha2::Sha256;
use crate::error::GmocoinError;
use crate::model::{
    market_data::{Ticker, Depth, SymbolInfo},
    order::{OrdersList, ExecutionsList},
    account::Asset,
};
use std::time::{SystemTime, UNIX_EPOCH};
use pyo3::prelude::*;

type HmacSha256 = Hmac<Sha256>;

#[pyclass]
#[derive(Clone)]
pub struct GmocoinRestClient {
    client: Client,
    api_key: String,
    api_secret: String,
    base_url_public: String,
    base_url_private: String,
}

#[pymethods]
impl GmocoinRestClient {
    #[new]
    pub fn new(api_key: String, api_secret: String, timeout_ms: u64, proxy_url: Option<String>) -> Self {
        let mut builder = Client::builder()
            .timeout(std::time::Duration::from_millis(timeout_ms));

        if let Some(proxy) = proxy_url {
            if let Ok(p) = reqwest::Proxy::all(proxy) {
                builder = builder.proxy(p);
            }
        }

        Self {
            client: builder.build().unwrap_or_else(|_| Client::new()),
            api_key,
            api_secret,
            base_url_public: "https://api.coin.z.com/public".to_string(),
            base_url_private: "https://api.coin.z.com/private".to_string(),
        }
    }

    // ========== Public API (Python) ==========

    pub fn get_status_py(&self, py: Python) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let res: serde_json::Value = client.public_get("/v1/status", None).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_ticker_py(&self, py: Python, symbol: Option<String>) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let query = symbol.as_ref().map(|s| vec![("symbol", s.as_str())]);
            let res: Vec<Ticker> = client.public_get("/v1/ticker", query.as_deref()).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_orderbooks_py(&self, py: Python, symbol: String) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let query = vec![("symbol", symbol.as_str())];
            let res: Depth = client.public_get("/v1/orderbooks", Some(&query)).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_trades_py(&self, py: Python, symbol: String, page: Option<i32>, count: Option<i32>) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let mut query_owned: Vec<(String, String)> = vec![("symbol".to_string(), symbol)];
            if let Some(p) = page { query_owned.push(("page".to_string(), p.to_string())); }
            if let Some(c) = count { query_owned.push(("count".to_string(), c.to_string())); }
            let query: Vec<(&str, &str)> = query_owned.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect();
            let res: serde_json::Value = client.public_get("/v1/trades", Some(&query)).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_klines_py(&self, py: Python, symbol: String, interval: String, date: String) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let path = format!("/v1/klines?symbol={}&interval={}&date={}", symbol, interval, date);
            let res: serde_json::Value = client.public_get_raw(&path).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_symbols_py(&self, py: Python) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let res: Vec<SymbolInfo> = client.public_get("/v1/symbols", None).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    // ========== Private API (Python) ==========

    pub fn get_assets_py(&self, py: Python) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let res: Vec<Asset> = client.private_get("/v1/account/assets", None).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_active_orders_py(&self, py: Python, symbol: String, page: Option<i32>, count: Option<i32>) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let mut query_owned: Vec<(String, String)> = vec![("symbol".to_string(), symbol)];
            if let Some(p) = page { query_owned.push(("page".to_string(), p.to_string())); }
            if let Some(c) = count { query_owned.push(("count".to_string(), c.to_string())); }
            let query: Vec<(&str, &str)> = query_owned.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect();
            let res: OrdersList = client.private_get("/v1/activeOrders", Some(&query)).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_executions_py(&self, py: Python, order_id: String) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let query = vec![("orderId", order_id.as_str())];
            let res: ExecutionsList = client.private_get("/v1/executions", Some(&query)).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_latest_executions_py(&self, py: Python, symbol: String, page: Option<i32>, count: Option<i32>) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let mut query_owned: Vec<(String, String)> = vec![("symbol".to_string(), symbol)];
            if let Some(p) = page { query_owned.push(("page".to_string(), p.to_string())); }
            if let Some(c) = count { query_owned.push(("count".to_string(), c.to_string())); }
            let query: Vec<(&str, &str)> = query_owned.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect();
            let res: ExecutionsList = client.private_get("/v1/latestExecutions", Some(&query)).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    // ========== Order API (Python) ==========

    pub fn post_order_py(
        &self,
        py: Python,
        symbol: String,
        side: String,
        execution_type: String,
        size: String,
        price: Option<String>,
        time_in_force: Option<String>,
    ) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let mut body = serde_json::json!({
                "symbol": symbol,
                "side": side,
                "executionType": execution_type,
                "size": size,
            });
            if let Some(p) = price { body["price"] = serde_json::json!(p); }
            if let Some(tif) = time_in_force { body["timeInForce"] = serde_json::json!(tif); }

            let body_str = body.to_string();
            let res: serde_json::Value = client.private_post("/v1/order", &body_str).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn post_change_order_py(
        &self,
        py: Python,
        order_id: String,
        price: String,
        losscut_price: Option<String>,
    ) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let mut body = serde_json::json!({
                "orderId": order_id,
                "price": price,
            });
            if let Some(lp) = losscut_price { body["losscutPrice"] = serde_json::json!(lp); }

            let body_str = body.to_string();
            let res: serde_json::Value = client.private_post("/v1/changeOrder", &body_str).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn post_cancel_order_py(&self, py: Python, order_id: String) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let body = serde_json::json!({"orderId": order_id}).to_string();
            let res: serde_json::Value = client.private_post("/v1/cancelOrder", &body).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn post_cancel_bulk_order_py(
        &self,
        py: Python,
        symbols: Vec<String>,
        side: Option<String>,
    ) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let mut body = serde_json::json!({"symbols": symbols});
            if let Some(s) = side { body["side"] = serde_json::json!(s); }

            let body_str = body.to_string();
            let res: serde_json::Value = client.private_post("/v1/cancelBulkOrder", &body_str).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    // ========== WS Auth (Python) ==========

    pub fn post_ws_auth_py(&self, py: Python) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let res: serde_json::Value = client.private_post("/v1/ws-auth", "").await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn put_ws_auth_py(&self, py: Python, token: String) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let body = serde_json::json!({"token": token}).to_string();
            let res: serde_json::Value = client.private_put("/v1/ws-auth", &body).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_order_py(&self, py: Python, order_id: String) -> PyResult<PyObject> {
        let client = self.clone();
        let future = async move {
            let query = vec![("orderId", order_id.as_str())];
            let res: OrdersList = client.private_get("/v1/orders", Some(&query)).await.map_err(PyErr::from)?;
            serde_json::to_string(&res).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }
}

// ========== Internal (Rust-only) ==========

impl GmocoinRestClient {
    fn generate_signature(&self, text: &str) -> String {
        let mut mac = HmacSha256::new_from_slice(self.api_secret.as_bytes())
            .expect("HMAC can take key of any size");
        mac.update(text.as_bytes());
        hex::encode(mac.finalize().into_bytes())
    }

    fn timestamp_ms() -> String {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis()
            .to_string()
    }

    /// Public GET: base_url_public + endpoint
    pub async fn public_get<T: DeserializeOwned>(
        &self,
        endpoint: &str,
        query: Option<&[(&str, &str)]>,
    ) -> Result<T, GmocoinError> {
        let url = format!("{}{}", self.base_url_public, endpoint);
        let mut builder = self.client.get(&url);
        if let Some(q) = query {
            builder = builder.query(q);
        }

        let response = builder.send().await?;
        let text = response.text().await?;

        self.parse_response::<T>(&text)
    }

    /// Public GET with raw path (already includes query string)
    pub async fn public_get_raw<T: DeserializeOwned>(
        &self,
        path_with_query: &str,
    ) -> Result<T, GmocoinError> {
        let url = format!("{}{}", self.base_url_public, path_with_query);
        let response = self.client.get(&url).send().await?;
        let text = response.text().await?;
        self.parse_response::<T>(&text)
    }

    /// Private GET: base_url_private + endpoint with auth headers
    pub async fn private_get<T: DeserializeOwned>(
        &self,
        endpoint: &str,
        query: Option<&[(&str, &str)]>,
    ) -> Result<T, GmocoinError> {
        let timestamp = Self::timestamp_ms();

        // GMO Coin GET signature: timestamp + "GET" + path (NO query params in signature)
        let text_to_sign = format!("{}GET{}", timestamp, endpoint);
        let signature = self.generate_signature(&text_to_sign);

        let url = format!("{}{}", self.base_url_private, endpoint);
        let mut builder = self.client.get(&url)
            .header("API-KEY", &self.api_key)
            .header("API-TIMESTAMP", &timestamp)
            .header("API-SIGN", signature);

        if let Some(q) = query {
            builder = builder.query(q);
        }

        let response = builder.send().await?;
        let text = response.text().await?;
        self.parse_response::<T>(&text)
    }

    /// Private POST: base_url_private + endpoint with auth headers
    pub async fn private_post<T: DeserializeOwned>(
        &self,
        endpoint: &str,
        body: &str,
    ) -> Result<T, GmocoinError> {
        self.private_request::<T>(Method::POST, endpoint, body).await
    }

    /// Private PUT: base_url_private + endpoint with auth headers
    pub async fn private_put<T: DeserializeOwned>(
        &self,
        endpoint: &str,
        body: &str,
    ) -> Result<T, GmocoinError> {
        self.private_request::<T>(Method::PUT, endpoint, body).await
    }

    async fn private_request<T: DeserializeOwned>(
        &self,
        method: Method,
        endpoint: &str,
        body: &str,
    ) -> Result<T, GmocoinError> {
        let timestamp = Self::timestamp_ms();
        let method_str = method.as_str();

        // GMO Coin signature: timestamp + method + path + body
        let text_to_sign = format!("{}{}{}{}", timestamp, method_str, endpoint, body);
        let signature = self.generate_signature(&text_to_sign);

        let url = format!("{}{}", self.base_url_private, endpoint);
        let mut builder = self.client.request(method, &url)
            .header("API-KEY", &self.api_key)
            .header("API-TIMESTAMP", &timestamp)
            .header("API-SIGN", signature)
            .header("Content-Type", "application/json");

        if !body.is_empty() {
            builder = builder.body(body.to_string());
        }

        let response = builder.send().await?;
        let text = response.text().await?;
        self.parse_response::<T>(&text)
    }

    /// Parse GMO Coin response: {"status": 0, "data": ..., "responsetime": "..."}
    fn parse_response<T: DeserializeOwned>(&self, text: &str) -> Result<T, GmocoinError> {
        let val: serde_json::Value = serde_json::from_str(text)?;
        let status = val.get("status").and_then(|v| v.as_i64()).unwrap_or(-1) as i32;

        if status == 0 {
            if let Some(data) = val.get("data") {
                match serde_json::from_value::<T>(data.clone()) {
                    Ok(res) => Ok(res),
                    Err(e) => Err(GmocoinError::Unknown(format!(
                        "Parse Error on data: {}. Error: {}",
                        data, e
                    ))),
                }
            } else {
                Err(GmocoinError::Unknown(format!(
                    "status=0 but no data. Body: {}",
                    text
                )))
            }
        } else {
            // Extract error messages
            let messages = val
                .get("messages")
                .and_then(|m| m.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|msg| msg.get("message_string").and_then(|s| s.as_str()))
                        .collect::<Vec<_>>()
                        .join("; ")
                })
                .unwrap_or_else(|| format!("Unknown error. Body: {}", text));

            Err(GmocoinError::ExchangeError { status, messages })
        }
    }

    // Internal Rust methods for use by execution_client

    pub async fn post_ws_auth(&self) -> Result<String, GmocoinError> {
        let val: serde_json::Value = self.private_post("/v1/ws-auth", "").await?;
        val.as_str()
            .map(|s| s.to_string())
            .ok_or_else(|| GmocoinError::Unknown("ws-auth response is not a string".to_string()))
    }

    pub async fn put_ws_auth(&self, token: &str) -> Result<(), GmocoinError> {
        let body = serde_json::json!({"token": token}).to_string();
        let _: serde_json::Value = self.private_put("/v1/ws-auth", &body).await?;
        Ok(())
    }

    pub async fn get_assets(&self) -> Result<Vec<Asset>, GmocoinError> {
        self.private_get("/v1/account/assets", None).await
    }

    pub async fn submit_order(
        &self,
        symbol: &str,
        side: &str,
        execution_type: &str,
        size: &str,
        price: Option<&str>,
        time_in_force: Option<&str>,
    ) -> Result<serde_json::Value, GmocoinError> {
        let mut body = serde_json::json!({
            "symbol": symbol,
            "side": side,
            "executionType": execution_type,
            "size": size,
        });
        if let Some(p) = price {
            body["price"] = serde_json::json!(p);
        }
        if let Some(tif) = time_in_force {
            body["timeInForce"] = serde_json::json!(tif);
        }

        let body_str = body.to_string();
        self.private_post("/v1/order", &body_str).await
    }

    pub async fn cancel_order(&self, order_id: u64) -> Result<serde_json::Value, GmocoinError> {
        let body = serde_json::json!({"orderId": order_id}).to_string();
        self.private_post("/v1/cancelOrder", &body).await
    }

    pub async fn get_order(&self, order_id: u64) -> Result<OrdersList, GmocoinError> {
        let oid_str = order_id.to_string();
        let query = vec![("orderId", oid_str.as_str())];
        self.private_get("/v1/orders", Some(&query)).await
    }

    pub async fn get_executions_for_order(&self, order_id: u64) -> Result<ExecutionsList, GmocoinError> {
        let oid_str = order_id.to_string();
        let query = vec![("orderId", oid_str.as_str())];
        self.private_get("/v1/executions", Some(&query)).await
    }
}
