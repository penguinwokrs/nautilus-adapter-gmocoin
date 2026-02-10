use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{sleep, Duration};
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::{SinkExt, StreamExt};
use url::Url;
use pyo3::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};
use tracing::{info, warn, error};
use crate::client::rest::GmocoinRestClient;
use crate::model::order::Order;

#[pyclass]
pub struct GmocoinExecutionClient {
    rest_client: GmocoinRestClient,
    // Callback for order/execution/asset updates: (event_type, data_json)
    order_callback: Arc<std::sync::Mutex<Option<PyObject>>>,
    // Order state tracking
    orders: Arc<RwLock<HashMap<u64, Order>>>,
    client_oid_map: Arc<RwLock<HashMap<String, u64>>>,
    shutdown: Arc<AtomicBool>,
}

#[pymethods]
impl GmocoinExecutionClient {
    #[new]
    pub fn new(api_key: String, api_secret: String, timeout_ms: u64, proxy_url: Option<String>, rate_limit_per_sec: Option<f64>) -> Self {
        Self {
            rest_client: GmocoinRestClient::new(api_key, api_secret, timeout_ms, proxy_url, rate_limit_per_sec),
            order_callback: Arc::new(std::sync::Mutex::new(None)),
            orders: Arc::new(RwLock::new(HashMap::new())),
            client_oid_map: Arc::new(RwLock::new(HashMap::new())),
            shutdown: Arc::new(AtomicBool::new(false)),
        }
    }

    pub fn set_order_callback(&self, callback: PyObject) {
        let mut lock = self.order_callback.lock().unwrap();
        *lock = Some(callback);
    }

    /// Connect to Private WebSocket (with token refresh loop)
    pub fn connect(&self, py: Python) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let order_cb_arc = self.order_callback.clone();
        let orders_arc = self.orders.clone();
        let shutdown = self.shutdown.clone();

        shutdown.store(false, Ordering::SeqCst);

        let future = async move {
            std::thread::Builder::new()
                .name("gmocoin-ws-private".to_string())
                .spawn(move || {
                    let rt = tokio::runtime::Builder::new_current_thread()
                        .enable_all()
                        .build()
                        .expect("Failed to build tokio runtime for Private WS");

                    rt.block_on(Self::ws_loop(
                        rest_client, order_cb_arc, orders_arc, shutdown,
                    ));
                })
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    format!("Failed to spawn Private WS thread: {}", e)
                ))?;

            Ok("Connected")
        };

        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    // ========== Order Operations (Python) ==========

    #[pyo3(signature = (symbol, amount, side, execution_type, client_order_id, price=None, time_in_force=None, cancel_before=None, losscut_price=None, settle_type=None))]
    pub fn submit_order(
        &self,
        py: Python,
        symbol: String,
        amount: String,
        side: String,
        execution_type: String,
        client_order_id: String,
        price: Option<String>,
        time_in_force: Option<String>,
        cancel_before: Option<bool>,
        losscut_price: Option<String>,
        settle_type: Option<String>,
    ) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let client_oid_map_arc = self.client_oid_map.clone();

        let future = async move {
            let price_ref = price.as_deref();
            let tif_ref = time_in_force.as_deref();
            let lp_ref = losscut_price.as_deref();
            let st_ref = settle_type.as_deref();
            let res = rest_client
                .submit_order(&symbol, &side, &execution_type, &amount, price_ref, tif_ref, cancel_before, lp_ref, st_ref)
                .await
                .map_err(PyErr::from)?;

            // The response "data" is the orderId as a string
            let order_id_str = res.as_str().unwrap_or("").to_string();
            let order_id: u64 = order_id_str.parse().unwrap_or(0);

            if order_id > 0 {
                let mut map = client_oid_map_arc.write().await;
                map.insert(client_order_id, order_id);
            }

            let result = serde_json::json!({"order_id": order_id});
            serde_json::to_string(&result)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn cancel_order(&self, py: Python, _symbol: String, order_id: String) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let future = async move {
            let oid = order_id.parse::<u64>().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid order_id: {}", e))
            })?;

            let res = rest_client.cancel_order(oid).await.map_err(PyErr::from)?;
            serde_json::to_string(&res)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_order(&self, py: Python, order_id: String) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let future = async move {
            let oid = order_id.parse::<u64>().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid order_id: {}", e))
            })?;

            let res = rest_client.get_order(oid).await.map_err(PyErr::from)?;
            serde_json::to_string(&res)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_executions(&self, py: Python, order_id: String) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let future = async move {
            let oid = order_id.parse::<u64>().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid order_id: {}", e))
            })?;

            let res = rest_client
                .get_executions_for_order(oid)
                .await
                .map_err(PyErr::from)?;
            serde_json::to_string(&res)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn change_order(
        &self,
        py: Python,
        order_id: String,
        price: String,
        losscut_price: Option<String>,
    ) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let future = async move {
            let oid = order_id.parse::<u64>().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid order_id: {}", e))
            })?;

            let lp_ref = losscut_price.as_deref();
            let res = rest_client
                .change_order(oid, &price, lp_ref)
                .await
                .map_err(PyErr::from)?;
            serde_json::to_string(&res)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn cancel_orders(
        &self,
        py: Python,
        order_ids: Vec<String>,
    ) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let future = async move {
            let oids: Vec<u64> = order_ids.iter()
                .map(|s| s.parse::<u64>())
                .collect::<Result<Vec<_>, _>>()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Invalid order_id: {}", e)
                ))?;

            let res = rest_client
                .cancel_orders(&oids)
                .await
                .map_err(PyErr::from)?;
            serde_json::to_string(&res)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_active_orders(
        &self,
        py: Python,
        symbol: String,
        page: Option<i32>,
        count: Option<i32>,
    ) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let future = async move {
            let res = rest_client
                .get_active_orders(&symbol, page.unwrap_or(1), count.unwrap_or(100))
                .await
                .map_err(PyErr::from)?;
            serde_json::to_string(&res)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_latest_executions(
        &self,
        py: Python,
        symbol: String,
        page: Option<i32>,
        count: Option<i32>,
    ) -> PyResult<PyObject> {
        let rest_client = self.rest_client.clone();
        let future = async move {
            let res = rest_client
                .get_latest_executions(&symbol, page.unwrap_or(1), count.unwrap_or(100))
                .await
                .map_err(PyErr::from)?;
            serde_json::to_string(&res)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn get_assets_py(&self, py: Python) -> PyResult<PyObject> {
        self.rest_client.get_assets_py(py)
    }

    // ========== Position Operations (Python) ==========

    pub fn get_margin_py(&self, py: Python) -> PyResult<PyObject> {
        self.rest_client.get_margin_py(py)
    }

    pub fn get_open_positions(&self, py: Python, symbol: String, page: Option<i32>, count: Option<i32>) -> PyResult<PyObject> {
        self.rest_client.get_open_positions_py(py, symbol, page, count)
    }

    pub fn get_position_summary(&self, py: Python, symbol: Option<String>) -> PyResult<PyObject> {
        self.rest_client.get_position_summary_py(py, symbol)
    }

    #[pyo3(signature = (symbol, side, execution_type, settle_position, price=None, time_in_force=None))]
    pub fn close_order(
        &self,
        py: Python,
        symbol: String,
        side: String,
        execution_type: String,
        settle_position: Vec<(u64, String)>,
        price: Option<String>,
        time_in_force: Option<String>,
    ) -> PyResult<PyObject> {
        self.rest_client.post_close_order_py(py, symbol, side, execution_type, settle_position, price, time_in_force)
    }

    #[pyo3(signature = (symbol, side, execution_type, size, price=None, time_in_force=None))]
    pub fn close_bulk_order(
        &self,
        py: Python,
        symbol: String,
        side: String,
        execution_type: String,
        size: String,
        price: Option<String>,
        time_in_force: Option<String>,
    ) -> PyResult<PyObject> {
        self.rest_client.post_close_bulk_order_py(py, symbol, side, execution_type, size, price, time_in_force)
    }

    pub fn change_losscut_price(&self, py: Python, position_id: u64, losscut_price: String) -> PyResult<PyObject> {
        self.rest_client.put_losscut_price_py(py, position_id, losscut_price)
    }
}

impl GmocoinExecutionClient {
    async fn ws_loop(
        rest_client: GmocoinRestClient,
        order_cb_arc: Arc<std::sync::Mutex<Option<PyObject>>>,
        orders_arc: Arc<RwLock<HashMap<u64, Order>>>,
        shutdown: Arc<AtomicBool>,
    ) {
        let mut backoff_sec = 5u64;
        let max_backoff = 60u64;

        loop {
            if shutdown.load(Ordering::SeqCst) { return; }

            // 1. Get access token
            let token = match rest_client.post_ws_auth().await {
                Ok(t) => t,
                Err(e) => {
                    error!("GMO: Failed to get Private WS auth token: {}. Retrying in {}s...", e, backoff_sec);
                    sleep(Duration::from_secs(backoff_sec)).await;
                    backoff_sec = (backoff_sec * 2).min(max_backoff);
                    continue;
                }
            };

            info!("GMO: Got Private WS token");

            // 2. Connect to Private WS
            let ws_url = format!("wss://api.coin.z.com/ws/private/v1/{}", token);
            let url = match Url::parse(&ws_url) {
                Ok(u) => u,
                Err(e) => {
                    error!("GMO: Invalid Private WS URL: {}. Retrying in 5s...", e);
                    sleep(Duration::from_secs(5)).await;
                    continue;
                }
            };

            match connect_async(url).await {
                Ok((mut ws, _)) => {
                    info!("GMO: Connected to Private WebSocket");
                    backoff_sec = 5;

                    // Subscribe to execution and order events with rate limiting
                    let ws_sub_limiter = crate::rate_limit::TokenBucket::new(1.0, 0.5);
                    let channels = vec!["executionEvents", "orderEvents", "positionEvents", "positionSummaryEvents"];
                    for ch in &channels {
                        ws_sub_limiter.acquire().await;
                        let sub_msg = serde_json::json!({
                            "command": "subscribe",
                            "channel": ch,
                        });
                        if let Err(e) = ws.send(Message::Text(sub_msg.to_string())).await {
                            error!("GMO: Failed to subscribe to {}: {}", ch, e);
                        }
                    }

                    // Token refresh tracking
                    let mut last_refresh = std::time::Instant::now();
                    let refresh_interval = Duration::from_secs(900); // 15 minutes

                    // Main message loop
                    loop {
                        if shutdown.load(Ordering::SeqCst) {
                            let _ = ws.send(Message::Close(None)).await;
                            return;
                        }

                        // Check if token needs refresh
                        if last_refresh.elapsed() >= refresh_interval {
                            if let Err(e) = rest_client.put_ws_auth(&token).await {
                                error!("GMO: Failed to extend Private WS token: {}. Reconnecting...", e);
                                break;
                            }
                            info!("GMO: Extended Private WS token");
                            last_refresh = std::time::Instant::now();
                        }

                        match ws.next().await {
                            Some(Ok(Message::Text(txt))) => {
                                Self::process_ws_message(&txt, &order_cb_arc, &orders_arc).await;
                            }
                            Some(Ok(Message::Ping(data))) => {
                                let _ = ws.send(Message::Pong(data)).await;
                            }
                            Some(Ok(Message::Close(_))) => {
                                warn!("GMO: Private WS closed by server");
                                break;
                            }
                            Some(Err(e)) => {
                                error!("GMO: Private WS error: {}", e);
                                break;
                            }
                            None => {
                                warn!("GMO: Private WS stream ended");
                                break;
                            }
                            _ => {}
                        }
                    }
                }
                Err(e) => {
                    error!("GMO: Failed to connect Private WS: {}. Retrying in {}s...", e, backoff_sec);
                }
            }

            if shutdown.load(Ordering::SeqCst) { return; }
            sleep(Duration::from_secs(backoff_sec)).await;
            backoff_sec = (backoff_sec * 2).min(max_backoff);
        }
    }

    async fn process_ws_message(
        msg_json: &str,
        order_cb_arc: &Arc<std::sync::Mutex<Option<PyObject>>>,
        orders_arc: &Arc<RwLock<HashMap<u64, Order>>>,
    ) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(msg_json) {
            // Check for error responses
            if val.get("error").is_some() {
                warn!("GMO: Private WS error response: {}", msg_json);
                return;
            }

            let channel = val.get("channel").and_then(|c| c.as_str()).unwrap_or("unknown");

            let event_type = match channel {
                "executionEvents" => "ExecutionUpdate",
                "orderEvents" => "OrderUpdate",
                "positionEvents" => "PositionUpdate",
                "positionSummaryEvents" => "PositionSummaryUpdate",
                _ => "Unknown",
            };

            // For OrderUpdate, try to cache the order
            if event_type == "OrderUpdate" {
                if let Ok(order) = serde_json::from_value::<Order>(val.clone()) {
                    let mut orders = orders_arc.write().await;
                    orders.insert(order.order_id, order);
                }
            }

            // Call Python callback
            let cb_opt = {
                let lock = order_cb_arc.lock().unwrap();
                lock.clone()
            };
            if let Some(cb) = cb_opt {
                Python::with_gil(|py| {
                    let _ = cb.call1(py, (event_type, msg_json.to_string()));
                });
            }
        }
    }
}
