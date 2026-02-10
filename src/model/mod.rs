pub mod market_data;
pub mod order;
pub mod account;
pub mod orderbook;

use serde::Deserialize;

#[derive(Deserialize, Debug)]
#[allow(dead_code)]
pub struct GmocoinResponse<T> {
    pub status: i32,
    pub data: T,
    #[serde(rename = "responsetime")]
    pub response_time: String,
}

#[derive(Deserialize, Debug)]
#[allow(dead_code)]
pub struct GmocoinErrorMessage {
    pub message_code: String,
    pub message_string: String,
}

#[derive(Deserialize, Debug)]
#[allow(dead_code)]
pub struct GmocoinErrorResponse {
    pub status: i32,
    pub messages: Vec<GmocoinErrorMessage>,
    #[serde(rename = "responsetime")]
    pub response_time: String,
}
