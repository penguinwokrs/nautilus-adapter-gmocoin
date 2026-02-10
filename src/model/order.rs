use serde::{Deserialize, Serialize};

#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Order {
    #[serde(rename = "orderId")]
    pub order_id: u64,
    #[serde(rename = "rootOrderId")]
    pub root_order_id: Option<u64>,
    pub symbol: String,
    pub side: String,
    #[serde(rename = "executionType")]
    pub execution_type: String,
    #[serde(rename = "settleType")]
    pub settle_type: Option<String>,
    pub size: String,
    #[serde(rename = "executedSize")]
    pub executed_size: String,
    pub price: Option<String>,
    #[serde(rename = "losscutPrice")]
    pub losscut_price: Option<String>,
    pub status: String,
    #[serde(rename = "timeInForce")]
    pub time_in_force: Option<String>,
    pub timestamp: String,
}

#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Execution {
    #[serde(rename = "executionId")]
    pub execution_id: u64,
    #[serde(rename = "orderId")]
    pub order_id: u64,
    pub symbol: String,
    pub side: String,
    #[serde(rename = "settleType")]
    pub settle_type: Option<String>,
    pub size: String,
    pub price: String,
    #[serde(rename = "lossGain")]
    pub loss_gain: Option<String>,
    pub fee: String,
    pub timestamp: String,
}

/// Container for orders list response
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct OrdersList {
    #[serde(default)]
    pub list: Vec<Order>,
}

/// Container for executions list response
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct ExecutionsList {
    #[serde(default)]
    pub list: Vec<Execution>,
}
