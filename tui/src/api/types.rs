use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub services: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmRequest {
    pub prompt: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_prompt: Option<String>,
    #[serde(default = "default_temperature")]
    pub temperature: f64,
    #[serde(default = "default_max_tokens")]
    pub max_tokens: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub correlation_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout_seconds: Option<u32>,
}
fn default_temperature() -> f64 { 0.7 }
fn default_max_tokens() -> u32 { 2048 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmResponse {
    pub content: String,
    pub model: String,
    #[serde(default)]
    pub usage: HashMap<String, i64>,
    #[serde(default = "default_finish_reason")]
    pub finish_reason: String,
    #[serde(default)]
    pub response_time: f64,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}
fn default_finish_reason() -> String { "stop".into() }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerationRequest {
    pub topics: Vec<String>,
    #[serde(default = "default_law_domain")]
    pub law_domain: String,
    #[serde(default = "default_parties")]
    pub number_parties: u32,
    #[serde(default = "default_complexity")]
    pub complexity_level: String,
    #[serde(default = "default_sample_size")]
    pub sample_size: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_preferences: Option<HashMap<String, serde_json::Value>>,
    #[serde(default = "default_method")]
    pub method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provider: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(default = "default_true")]
    pub include_analysis: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub correlation_id: Option<String>,
}
fn default_law_domain() -> String { "tort".into() }
fn default_parties() -> u32 { 3 }
fn default_complexity() -> String { "intermediate".into() }
fn default_sample_size() -> u32 { 3 }
fn default_method() -> String { "pure_llm".into() }
fn default_true() -> bool { true }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerationResponse {
    pub hypothetical: String,
    #[serde(default)]
    pub analysis: String,
    #[serde(default)]
    pub generation_time: f64,
    #[serde(default)]
    pub validation_results: HashMap<String, serde_json::Value>,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegenerateRequest {
    pub generation_id: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub correlation_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fallback_request: Option<HashMap<String, serde_json::Value>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegenerationResponse {
    pub source_generation_id: i64,
    pub feedback_context: String,
    pub request_data: HashMap<String, serde_json::Value>,
    pub regenerated: GenerationResponse,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReportRequest {
    pub generation_id: i64,
    #[serde(default)]
    pub issue_types: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub comment: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub correlation_id: Option<String>,
    #[serde(default = "default_true")]
    pub is_locked: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerationReport {
    pub id: Option<i64>,
    pub generation_id: i64,
    #[serde(default)]
    pub issue_types: Vec<String>,
    pub comment: Option<String>,
    pub correlation_id: Option<String>,
    #[serde(default = "default_true")]
    pub is_locked: bool,
    pub created_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryRecord {
    pub id: i64,
    #[serde(default)]
    pub timestamp: String,
    #[serde(default)]
    pub topics: String,
    #[serde(default)]
    pub complexity_level: String,
    #[serde(default)]
    pub hypothetical: String,
    #[serde(default)]
    pub analysis: String,
    #[serde(default)]
    pub quality_score: f64,
    #[serde(default)]
    pub generation_time: f64,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CorpusEntry {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
    pub text: String,
    #[serde(default)]
    pub topics: Vec<String>,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CorpusQueryRequest {
    pub topics: Vec<String>,
    #[serde(default = "default_sample_size")]
    pub sample_size: u32,
    #[serde(default)]
    pub exclude_ids: Vec<String>,
    #[serde(default = "default_min_topic_overlap")]
    pub min_topic_overlap: u32,
}
fn default_min_topic_overlap() -> u32 { 1 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CorpusQueryResponse {
    #[serde(default)]
    pub entries: Vec<CorpusEntry>,
    #[serde(default)]
    pub count: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobStatus {
    #[serde(rename = "type")]
    pub job_type: String,
    pub status: String, // running, completed, failed, cancelled
    #[serde(default)]
    pub progress: u32,
    pub result: Option<serde_json::Value>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiError {
    pub code: String,
    pub message: String,
    #[serde(default)]
    pub hint: String,
    #[serde(default)]
    pub retryable: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidateRequest {
    pub text: String,
    pub required_topics: Vec<String>,
    #[serde(default = "default_expected_parties")]
    pub expected_parties: u32,
    #[serde(default = "default_law_domain")]
    pub law_domain: String,
    #[serde(default)]
    pub fast_mode: bool,
}
fn default_expected_parties() -> u32 { 2 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScrapeRequest {
    pub source: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub courts: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub years: Option<Vec<i32>>,
    #[serde(default = "default_max_cases")]
    pub max_cases: u32,
    #[serde(default = "default_true")]
    pub tort_only: bool,
}
fn default_max_cases() -> u32 { 50 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub generation_id: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hypothetical: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub analysis: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_answer: Option<String>,
    #[serde(default = "default_format")]
    pub format: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
}
fn default_format() -> String { "docx".into() }
