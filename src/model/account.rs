use serde::{Deserialize, Serialize};

#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Asset {
    pub amount: String,
    pub available: String,
    #[serde(rename = "conversionRate")]
    pub conversion_rate: Option<String>,
    pub symbol: String,
}

/// Container for assets list response
#[derive(Deserialize, Serialize, Debug, Clone)]
#[allow(dead_code)]
pub struct AssetsList(pub Vec<Asset>);

/// Margin (leverage account) information
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Margin {
    #[serde(rename = "profitLoss")]
    pub profit_loss: Option<String>,
    #[serde(rename = "actualProfitLoss")]
    pub actual_profit_loss: Option<String>,
    pub margin: Option<String>,
    #[serde(rename = "availableAmount")]
    pub available_amount: String,
    #[serde(rename = "marginRate")]
    pub margin_rate: Option<String>,
}
