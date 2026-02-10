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
