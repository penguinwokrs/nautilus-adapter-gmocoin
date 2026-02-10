use pyo3::prelude::*;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::{SinkExt, StreamExt};
use std::sync::Arc;
use serde_json::Value;
use std::collections::HashSet;
use tokio::time::{sleep, Duration};
use std::sync::atomic::{AtomicBool, Ordering};
use tracing::{info, warn, error};

use crate::model::orderbook::OrderBook;
use crate::rate_limit::TokenBucket;

#[pyclass(from_py_object)]
#[derive(Clone)]
pub struct GmocoinDataClient {
    data_callback: Arc<std::sync::Mutex<Option<Py<PyAny>>>>,
    /// (channel, symbol, option) - option is e.g. "TAKER_ONLY" for trades
    subscriptions: Arc<std::sync::Mutex<HashSet<(String, String, String)>>>,
    outgoing: Arc<std::sync::Mutex<Vec<String>>>,
    books: Arc<std::sync::Mutex<std::collections::HashMap<String, OrderBook>>>,
    shutdown: Arc<AtomicBool>,
    connected: Arc<AtomicBool>,
    ws_rate_limit: TokenBucket,
}

#[pymethods]
impl GmocoinDataClient {
    /// Create a new GmocoinDataClient.
    ///
    /// `ws_rate_limit_per_sec`: WebSocket subscription rate limit (commands/sec).
    ///   Default 0.5 (1 command per 2 seconds) for safety.
    #[new]
    pub fn new(ws_rate_limit_per_sec: Option<f64>) -> Self {
        let ws_rate = ws_rate_limit_per_sec.unwrap_or(0.5);
        Self {
            data_callback: Arc::new(std::sync::Mutex::new(None)),
            subscriptions: Arc::new(std::sync::Mutex::new(HashSet::new())),
            outgoing: Arc::new(std::sync::Mutex::new(Vec::new())),
            books: Arc::new(std::sync::Mutex::new(std::collections::HashMap::new())),
            shutdown: Arc::new(AtomicBool::new(false)),
            connected: Arc::new(AtomicBool::new(false)),
            ws_rate_limit: TokenBucket::new(1.0, ws_rate),
        }
    }

    pub fn set_data_callback(&self, callback: Py<PyAny>) {
        let mut lock = self.data_callback.lock().unwrap();
        *lock = Some(callback);
    }

    pub fn connect<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let data_cb_arc = self.data_callback.clone();
        let subs_arc = self.subscriptions.clone();
        let outgoing_arc = self.outgoing.clone();
        let books_arc = self.books.clone();
        let shutdown = self.shutdown.clone();
        let connected = self.connected.clone();
        let ws_rate_limit = self.ws_rate_limit.clone();

        shutdown.store(false, Ordering::SeqCst);
        connected.store(false, Ordering::SeqCst);

        let future = async move {
            std::thread::Builder::new()
                .name("gmocoin-ws-public".to_string())
                .spawn(move || {
                    let rt = tokio::runtime::Builder::new_current_thread()
                        .enable_all()
                        .build()
                        .expect("Failed to build tokio runtime for WS");

                    rt.block_on(Self::ws_loop(
                        subs_arc, outgoing_arc, data_cb_arc, books_arc, shutdown, connected, ws_rate_limit,
                    ));
                })
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    format!("Failed to spawn WS thread: {}", e)
                ))?;

            Ok("Connected")
        };

        pyo3_async_runtimes::tokio::future_into_py(py, future)
    }

    /// Subscribe to a channel for a symbol, with an optional option (e.g. "TAKER_ONLY" for trades).
    #[pyo3(signature = (channel, symbol, option = None))]
    pub fn subscribe<'py>(&self, py: Python<'py>, channel: String, symbol: String, option: Option<String>) -> PyResult<Bound<'py, PyAny>> {
        let subs_arc = self.subscriptions.clone();
        let outgoing_arc = self.outgoing.clone();
        let connected = self.connected.clone();

        let future = async move {
            let opt_str = option.clone().unwrap_or_default();

            // Always store for reconnection
            {
                let mut subs = subs_arc.lock().unwrap();
                subs.insert((channel.clone(), symbol.clone(), opt_str));
            }

            // If already connected, queue the subscribe message for immediate sending.
            if connected.load(Ordering::SeqCst) {
                let msg = Self::build_subscribe_msg(&channel, &symbol, option.as_deref());
                let mut queue = outgoing_arc.lock().unwrap();
                queue.push(msg);
            }

            Ok("Subscribe command stored")
        };

        pyo3_async_runtimes::tokio::future_into_py(py, future)
    }

    pub fn disconnect<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let shutdown = self.shutdown.clone();
        let future = async move {
            shutdown.store(true, Ordering::SeqCst);
            Ok("Disconnected")
        };
        pyo3_async_runtimes::tokio::future_into_py(py, future)
    }
}

impl GmocoinDataClient {
    fn build_subscribe_msg(channel: &str, symbol: &str, option: Option<&str>) -> String {
        let mut msg = serde_json::json!({
            "command": "subscribe",
            "channel": channel,
            "symbol": symbol,
        });
        if let Some(opt) = option {
            if !opt.is_empty() {
                msg["option"] = serde_json::Value::String(opt.to_string());
            }
        }
        msg.to_string()
    }

    async fn ws_loop(
        subs_arc: Arc<std::sync::Mutex<HashSet<(String, String, String)>>>,
        outgoing_arc: Arc<std::sync::Mutex<Vec<String>>>,
        data_cb_arc: Arc<std::sync::Mutex<Option<Py<PyAny>>>>,
        books_arc: Arc<std::sync::Mutex<std::collections::HashMap<String, OrderBook>>>,
        shutdown: Arc<AtomicBool>,
        connected: Arc<AtomicBool>,
        ws_rate_limit: TokenBucket,
    ) {
        let mut backoff_sec = 1u64;
        let max_backoff = 64u64;

        loop {
            if shutdown.load(Ordering::SeqCst) { return; }

            let ws_url = "wss://api.coin.z.com/ws/public/v1";

            match connect_async(ws_url).await {
                Ok((mut ws, _)) => {
                    info!("GMO: Connected to Public WebSocket");
                    backoff_sec = 1;
                    connected.store(true, Ordering::SeqCst);

                    // Collect all messages to send
                    let mut to_send: Vec<String> = Vec::new();

                    // Stored subscriptions
                    {
                        let subs: Vec<_> = {
                            let lock = subs_arc.lock().unwrap();
                            lock.iter().cloned().collect()
                        };
                        for (channel, symbol, opt) in &subs {
                            let option = if opt.is_empty() { None } else { Some(opt.as_str()) };
                            to_send.push(Self::build_subscribe_msg(channel, symbol, option));
                        }
                    }

                    // Queued outgoing messages
                    {
                        let mut queue = outgoing_arc.lock().unwrap();
                        to_send.extend(queue.drain(..));
                    }

                    // Deduplicate subscriptions
                    to_send.sort();
                    to_send.dedup();

                    // Send each subscription with rate limiting to avoid GMO Coin ERR-5003
                    for msg in to_send {
                        ws_rate_limit.acquire().await;
                        if let Err(e) = ws.send(Message::Text(msg.into())).await {
                            error!("GMO: Failed to send subscribe: {}", e);
                        }
                    }

                    // Main message loop
                    loop {
                        if shutdown.load(Ordering::SeqCst) {
                            let _ = ws.send(Message::Close(None)).await;
                            connected.store(false, Ordering::SeqCst);
                            return;
                        }

                        match ws.next().await {
                            Some(Ok(Message::Text(txt))) => {
                                // Check for queued outgoing messages between each received message
                                {
                                    let mut queue = outgoing_arc.lock().unwrap();
                                    for msg in queue.drain(..) {
                                        if let Err(e) = ws.send(Message::Text(msg.into())).await {
                                            error!("GMO: Failed to send msg: {}", e);
                                        }
                                    }
                                }

                                let txt_str: &str = txt.as_ref();
                                if let Ok(val) = serde_json::from_str::<Value>(txt_str) {
                                    // Check for error responses (ERR-5003 rate limit, etc.)
                                    if val.get("error").is_some() {
                                        warn!("GMO: WS error response: {}", txt_str);
                                        continue;
                                    }

                                    let channel = val.get("channel")
                                        .and_then(|c| c.as_str())
                                        .unwrap_or("")
                                        .to_string();
                                    if !channel.is_empty() {
                                        Self::dispatch_message(&channel, val, &data_cb_arc, &books_arc);
                                    }
                                }
                            }
                            Some(Ok(Message::Ping(data))) => {
                                // Process queued outgoing on ping too
                                {
                                    let mut queue = outgoing_arc.lock().unwrap();
                                    for msg in queue.drain(..) {
                                        if let Err(e) = ws.send(Message::Text(msg.into())).await {
                                            error!("GMO: Failed to send msg: {}", e);
                                        }
                                    }
                                }
                                let _ = ws.send(Message::Pong(data)).await;
                            }
                            Some(Ok(Message::Close(_))) => {
                                warn!("GMO: Public WS closed by server");
                                break;
                            }
                            Some(Err(e)) => {
                                error!("GMO: Public WS error: {}", e);
                                break;
                            }
                            None => {
                                warn!("GMO: Public WS stream ended");
                                break;
                            }
                            _ => {}
                        }
                    }

                    connected.store(false, Ordering::SeqCst);
                }
                Err(e) => {
                    error!("GMO: Public WS connection failed: {}. Retrying in {}s...", e, backoff_sec);
                }
            }

            if shutdown.load(Ordering::SeqCst) { return; }
            sleep(Duration::from_secs(backoff_sec)).await;
            backoff_sec = (backoff_sec * 2).min(max_backoff);
        }
    }

    fn dispatch_message(
        channel: &str,
        val: Value,
        data_cb_arc: &Arc<std::sync::Mutex<Option<Py<PyAny>>>>,
        books_arc: &Arc<std::sync::Mutex<std::collections::HashMap<String, OrderBook>>>,
    ) {
        match channel {
            "ticker" => {
                if let Ok(ticker) = serde_json::from_value::<crate::model::market_data::Ticker>(val) {
                    Python::try_attach(|py| {
                        let lock = data_cb_arc.lock().unwrap();
                        if let Some(cb) = lock.as_ref() {
                            let py_obj = Py::new(py, ticker).expect("Failed to create Python object");
                            let _ = cb.call1(py, ("ticker", py_obj)).ok();
                        }
                    });
                }
            }
            "orderbooks" => {
                if let Ok(depth) = serde_json::from_value::<crate::model::market_data::Depth>(val) {
                    let symbol = depth.symbol.clone();
                    let book_clone = {
                        let mut books = books_arc.lock().unwrap();
                        let book = books.entry(symbol.clone())
                            .or_insert_with(|| OrderBook::new(symbol.clone()));
                        book.apply_snapshot(depth);
                        book.clone()
                    };

                    Python::try_attach(|py| {
                        let lock = data_cb_arc.lock().unwrap();
                        if let Some(cb) = lock.as_ref() {
                            let py_obj = Py::new(py, book_clone).expect("Failed to create Python object");
                            let _ = cb.call1(py, ("orderbooks", py_obj)).ok();
                        }
                    });
                }
            }
            "trades" => {
                if let Ok(trade) = serde_json::from_value::<crate::model::market_data::Trade>(val) {
                    Python::try_attach(|py| {
                        let lock = data_cb_arc.lock().unwrap();
                        if let Some(cb) = lock.as_ref() {
                            let py_obj = Py::new(py, trade).expect("Failed to create Python object");
                            let _ = cb.call1(py, ("trades", py_obj)).ok();
                        }
                    });
                }
            }
            _ => {}
        }
    }
}
