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

/// Open position (leverage)
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Position {
    #[serde(rename = "positionId")]
    pub position_id: u64,
    pub symbol: String,
    pub side: String,
    pub size: String,
    #[serde(rename = "orderdSize")]
    pub ordered_size: Option<String>,
    pub price: String,
    #[serde(rename = "lossGain")]
    pub loss_gain: Option<String>,
    pub leverage: Option<String>,
    #[serde(rename = "losscutPrice")]
    pub losscut_price: Option<String>,
    pub timestamp: String,
}

/// Container for positions list response
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct PositionsList {
    #[serde(default)]
    pub list: Vec<Position>,
}

/// Position summary
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct PositionSummary {
    pub symbol: String,
    pub side: String,
    #[serde(rename = "sumPositionQuantity")]
    pub sum_position_quantity: String,
    #[serde(rename = "sumOrderQuantity")]
    pub sum_order_quantity: Option<String>,
    #[serde(rename = "averagePositionRate")]
    pub average_position_rate: String,
    #[serde(rename = "positionLossGain")]
    pub position_loss_gain: String,
}

/// Container for position summary list response
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct PositionSummaryList {
    #[serde(default)]
    pub list: Vec<PositionSummary>,
}
