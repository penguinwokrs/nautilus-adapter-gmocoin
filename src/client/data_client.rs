use pyo3::prelude::*;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::{SinkExt, StreamExt};
use std::sync::Arc;
use url::Url;
use serde_json::Value;
use std::collections::HashSet;
use tokio::time::{sleep, Duration};
use std::sync::atomic::{AtomicBool, Ordering};

use crate::model::orderbook::OrderBook;

#[pyclass]
#[derive(Clone)]
pub struct GmocoinDataClient {
    data_callback: Arc<std::sync::Mutex<Option<PyObject>>>,
    subscriptions: Arc<std::sync::Mutex<HashSet<(String, String)>>>,
    outgoing: Arc<std::sync::Mutex<Vec<String>>>,
    books: Arc<std::sync::Mutex<std::collections::HashMap<String, OrderBook>>>,
    shutdown: Arc<AtomicBool>,
    connected: Arc<AtomicBool>,
}

#[pymethods]
impl GmocoinDataClient {
    #[new]
    pub fn new() -> Self {
        Self {
            data_callback: Arc::new(std::sync::Mutex::new(None)),
            subscriptions: Arc::new(std::sync::Mutex::new(HashSet::new())),
            outgoing: Arc::new(std::sync::Mutex::new(Vec::new())),
            books: Arc::new(std::sync::Mutex::new(std::collections::HashMap::new())),
            shutdown: Arc::new(AtomicBool::new(false)),
            connected: Arc::new(AtomicBool::new(false)),
        }
    }

    pub fn set_data_callback(&self, callback: PyObject) {
        let mut lock = self.data_callback.lock().unwrap();
        *lock = Some(callback);
    }

    pub fn connect(&self, py: Python) -> PyResult<PyObject> {
        let data_cb_arc = self.data_callback.clone();
        let subs_arc = self.subscriptions.clone();
        let outgoing_arc = self.outgoing.clone();
        let books_arc = self.books.clone();
        let shutdown = self.shutdown.clone();
        let connected = self.connected.clone();

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
                        subs_arc, outgoing_arc, data_cb_arc, books_arc, shutdown, connected,
                    ));
                })
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    format!("Failed to spawn WS thread: {}", e)
                ))?;

            Ok("Connected")
        };

        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn subscribe(&self, py: Python, channel: String, symbol: String) -> PyResult<PyObject> {
        let subs_arc = self.subscriptions.clone();
        let outgoing_arc = self.outgoing.clone();
        let connected = self.connected.clone();

        let future = async move {
            // Always store for reconnection
            {
                let mut subs = subs_arc.lock().unwrap();
                subs.insert((channel.clone(), symbol.clone()));
            }

            // If already connected, queue the subscribe message for immediate sending.
            // The WS thread will pick it up between messages.
            // If not yet connected, the WS thread will read from subs_arc upon connection.
            if connected.load(Ordering::SeqCst) {
                let msg = serde_json::json!({
                    "command": "subscribe",
                    "channel": channel,
                    "symbol": symbol,
                });
                let mut queue = outgoing_arc.lock().unwrap();
                queue.push(msg.to_string());
            }

            Ok("Subscribe command stored")
        };

        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }

    pub fn disconnect(&self, py: Python) -> PyResult<PyObject> {
        let shutdown = self.shutdown.clone();
        let future = async move {
            shutdown.store(true, Ordering::SeqCst);
            Ok("Disconnected")
        };
        pyo3_asyncio::tokio::future_into_py(py, future).map(|f| f.into())
    }
}

impl GmocoinDataClient {
    async fn ws_loop(
        subs_arc: Arc<std::sync::Mutex<HashSet<(String, String)>>>,
        outgoing_arc: Arc<std::sync::Mutex<Vec<String>>>,
        data_cb_arc: Arc<std::sync::Mutex<Option<PyObject>>>,
        books_arc: Arc<std::sync::Mutex<std::collections::HashMap<String, OrderBook>>>,
        shutdown: Arc<AtomicBool>,
        connected: Arc<AtomicBool>,
    ) {
        let mut backoff_sec = 1u64;
        let max_backoff = 64u64;

        loop {
            if shutdown.load(Ordering::SeqCst) { return; }

            let url = Url::parse("wss://api.coin.z.com/ws/public/v1").unwrap();

            match connect_async(url).await {
                Ok((mut ws, _)) => {
                    eprintln!("GMO: Connected to Public WebSocket");
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
                        for (channel, symbol) in &subs {
                            let msg = serde_json::json!({
                                "command": "subscribe",
                                "channel": channel,
                                "symbol": symbol,
                            });
                            to_send.push(msg.to_string());
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

                    // Send each subscription with 2s delay to avoid GMO Coin rate limit (ERR-5003)
                    for msg in to_send {
                        if let Err(e) = ws.send(Message::Text(msg)).await {
                            eprintln!("GMO: Failed to send subscribe: {}", e);
                        }
                        sleep(Duration::from_millis(2000)).await;
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
                                        if let Err(e) = ws.send(Message::Text(msg)).await {
                                            eprintln!("GMO: Failed to send msg: {}", e);
                                        }
                                    }
                                }

                                if let Ok(val) = serde_json::from_str::<Value>(&txt) {
                                    // Check for error responses (ERR-5003 rate limit, etc.)
                                    if val.get("error").is_some() {
                                        eprintln!("GMO: WS error response: {}", txt);
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
                                        if let Err(e) = ws.send(Message::Text(msg)).await {
                                            eprintln!("GMO: Failed to send msg: {}", e);
                                        }
                                    }
                                }
                                let _ = ws.send(Message::Pong(data)).await;
                            }
                            Some(Ok(Message::Close(_))) => {
                                eprintln!("GMO: Public WS closed by server");
                                break;
                            }
                            Some(Err(e)) => {
                                eprintln!("GMO: Public WS error: {}", e);
                                break;
                            }
                            None => {
                                eprintln!("GMO: Public WS stream ended");
                                break;
                            }
                            _ => {}
                        }
                    }

                    connected.store(false, Ordering::SeqCst);
                }
                Err(e) => {
                    eprintln!("GMO: Public WS connection failed: {}. Retrying in {}s...", e, backoff_sec);
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
        data_cb_arc: &Arc<std::sync::Mutex<Option<PyObject>>>,
        books_arc: &Arc<std::sync::Mutex<std::collections::HashMap<String, OrderBook>>>,
    ) {
        match channel {
            "ticker" => {
                if let Ok(ticker) = serde_json::from_value::<crate::model::market_data::Ticker>(val) {
                    let cb_opt = { data_cb_arc.lock().unwrap().clone() };
                    if let Some(cb) = cb_opt {
                        Python::with_gil(|py| {
                            let py_obj = ticker.into_py(py);
                            let _ = cb.call1(py, ("ticker", py_obj));
                        });
                    }
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

                    let cb_opt = { data_cb_arc.lock().unwrap().clone() };
                    if let Some(cb) = cb_opt {
                        Python::with_gil(|py| {
                            let py_obj = book_clone.into_py(py);
                            let _ = cb.call1(py, ("orderbooks", py_obj));
                        });
                    }
                }
            }
            "trades" => {
                if let Ok(trade) = serde_json::from_value::<crate::model::market_data::Trade>(val) {
                    let cb_opt = { data_cb_arc.lock().unwrap().clone() };
                    if let Some(cb) = cb_opt {
                        Python::with_gil(|py| {
                            let py_obj = trade.into_py(py);
                            let _ = cb.call1(py, ("trades", py_obj));
                        });
                    }
                }
            }
            _ => {}
        }
    }
}
