use anyhow::Result;
use reqwest::Client;
use crate::api::types::*;

pub struct ApiClient {
    client: Client,
    base_url: String,
}

impl ApiClient {
    pub fn new(base_url: &str) -> Self {
        Self {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(180))
                .build()
                .unwrap_or_default(),
            base_url: base_url.trim_end_matches('/').to_string(),
        }
    }

    fn url(&self, path: &str) -> String {
        format!("{}{}", self.base_url, path)
    }

    // -- health --

    pub async fn health(&self) -> Result<HealthResponse> {
        Ok(self.client.get(self.url("/health")).send().await?.json().await?)
    }

    pub async fn version(&self) -> Result<serde_json::Value> {
        Ok(self.client.get(self.url("/version")).send().await?.json().await?)
    }

    // -- llm --

    pub async fn llm_health(&self, provider: Option<&str>) -> Result<serde_json::Value> {
        let mut url = self.url("/llm/health");
        if let Some(p) = provider { url = format!("{}?provider={}", url, p); }
        Ok(self.client.get(&url).send().await?.json().await?)
    }

    pub async fn llm_models(&self, provider: Option<&str>) -> Result<serde_json::Value> {
        let mut url = self.url("/llm/models");
        if let Some(p) = provider { url = format!("{}?provider={}", url, p); }
        Ok(self.client.get(&url).send().await?.json().await?)
    }

    pub async fn llm_generate(&self, req: &LlmRequest) -> Result<LlmResponse> {
        let resp = self.client.post(self.url("/llm/generate")).json(req).send().await?;
        if !resp.status().is_success() {
            let text = resp.text().await.unwrap_or_default();
            anyhow::bail!("LLM generate failed: {}", text);
        }
        Ok(resp.json().await?)
    }

    pub async fn llm_stream(&self, req: &LlmRequest, provider: Option<&str>, model: Option<&str>) -> Result<reqwest::Response> {
        let mut url = self.url("/llm/stream");
        let mut params = vec![];
        if let Some(p) = provider { params.push(format!("provider={}", p)); }
        if let Some(m) = model { params.push(format!("model={}", m)); }
        if !params.is_empty() { url = format!("{}?{}", url, params.join("&")); }
        let resp = self.client.post(&url).json(req).send().await?;
        Ok(resp)
    }

    pub async fn select_provider(&self, name: &str) -> Result<serde_json::Value> {
        Ok(self.client.post(self.url("/llm/select-provider"))
            .json(&serde_json::json!({"name": name})).send().await?.json().await?)
    }

    pub async fn select_model(&self, name: &str) -> Result<serde_json::Value> {
        Ok(self.client.post(self.url("/llm/select-model"))
            .json(&serde_json::json!({"name": name})).send().await?.json().await?)
    }

    pub async fn session_cost(&self) -> Result<serde_json::Value> {
        Ok(self.client.get(self.url("/llm/session-cost")).send().await?.json().await?)
    }

    // -- corpus --

    pub async fn list_topics(&self) -> Result<Vec<String>> {
        let resp: serde_json::Value = self.client.get(self.url("/corpus/topics")).send().await?.json().await?;
        Ok(resp["topics"].as_array().map(|a| a.iter().filter_map(|v| v.as_str().map(String::from)).collect()).unwrap_or_default())
    }

    pub async fn list_corpus_entries(&self, topic: Option<&str>, limit: u32) -> Result<Vec<CorpusEntry>> {
        let mut url = format!("{}?limit={}", self.url("/corpus/entries"), limit);
        if let Some(t) = topic { url = format!("{}&topic={}", url, t); }
        let resp: serde_json::Value = self.client.get(&url).send().await?.json().await?;
        let entries = serde_json::from_value(resp["entries"].clone()).unwrap_or_default();
        Ok(entries)
    }

    pub async fn query_corpus(&self, req: &CorpusQueryRequest) -> Result<CorpusQueryResponse> {
        let resp = self.client.post(self.url("/corpus/query")).json(req).send().await?;
        if !resp.status().is_success() {
            let text = resp.text().await.unwrap_or_default();
            anyhow::bail!("Corpus query failed: {}", text);
        }
        Ok(resp.json().await?)
    }

    pub async fn corpus_health(&self) -> Result<serde_json::Value> {
        Ok(self.client.get(self.url("/corpus/health")).send().await?.json().await?)
    }

    // -- workflow --

    pub async fn generate(&self, req: &GenerationRequest) -> Result<GenerationResponse> {
        let resp = self.client.post(self.url("/workflow/generate")).json(req).send().await?;
        if !resp.status().is_success() {
            let text = resp.text().await.unwrap_or_default();
            if let Ok(err) = serde_json::from_str::<serde_json::Value>(&text) {
                if let Some(detail) = err.get("detail") {
                    let api_err: ApiError = serde_json::from_value(detail.clone()).unwrap_or(ApiError {
                        code: "unknown".into(), message: text.clone(), hint: String::new(), retryable: false,
                    });
                    anyhow::bail!("{}: {} {}", api_err.code, api_err.message, if api_err.hint.is_empty() { String::new() } else { format!("({})", api_err.hint) });
                }
            }
            anyhow::bail!("Generation failed: {}", text);
        }
        Ok(resp.json().await?)
    }

    pub async fn regenerate(&self, req: &RegenerateRequest) -> Result<RegenerationResponse> {
        let resp = self.client.post(self.url("/workflow/regenerate")).json(req).send().await?;
        if !resp.status().is_success() {
            let text = resp.text().await.unwrap_or_default();
            anyhow::bail!("Regeneration failed: {}", text);
        }
        Ok(resp.json().await?)
    }

    pub async fn save_report(&self, req: &ReportRequest) -> Result<i64> {
        let resp: serde_json::Value = self.client.post(self.url("/workflow/report")).json(req).send().await?.json().await?;
        Ok(resp["report_id"].as_i64().unwrap_or(0))
    }

    pub async fn list_reports(&self, generation_id: i64) -> Result<Vec<GenerationReport>> {
        let resp: serde_json::Value = self.client.get(self.url(&format!("/workflow/reports/{}", generation_id))).send().await?.json().await?;
        Ok(serde_json::from_value(resp["reports"].clone()).unwrap_or_default())
    }

    // -- database --

    pub async fn get_history(&self, limit: u32) -> Result<Vec<HistoryRecord>> {
        let resp: serde_json::Value = self.client.get(self.url(&format!("/db/history?limit={}", limit))).send().await?.json().await?;
        Ok(serde_json::from_value(resp["records"].clone()).unwrap_or_default())
    }

    pub async fn get_generation(&self, id: i64) -> Result<serde_json::Value> {
        Ok(self.client.get(self.url(&format!("/db/generation/{}", id))).send().await?.json().await?)
    }

    pub async fn get_count(&self) -> Result<u64> {
        let resp: serde_json::Value = self.client.get(self.url("/db/count")).send().await?.json().await?;
        Ok(resp["count"].as_u64().unwrap_or(0))
    }

    pub async fn get_statistics(&self) -> Result<serde_json::Value> {
        Ok(self.client.get(self.url("/db/statistics")).send().await?.json().await?)
    }

    // -- validation --

    pub async fn validate(&self, req: &ValidateRequest) -> Result<serde_json::Value> {
        Ok(self.client.post(self.url("/validation/validate")).json(req).send().await?.json().await?)
    }

    // -- jobs --

    pub async fn start_preprocess(&self, raw_dir: Option<&str>, output_path: Option<&str>) -> Result<String> {
        self.start_preprocess_with_options(raw_dir, output_path, true, false).await
    }

    pub async fn start_preprocess_with_options(
        &self,
        raw_dir: Option<&str>,
        output_path: Option<&str>,
        merge_existing: bool,
        include_non_tort: bool,
    ) -> Result<String> {
        let body = serde_json::json!({
            "raw_dir": raw_dir,
            "output_path": output_path,
            "merge_existing": merge_existing,
            "include_non_tort": include_non_tort,
        });
        let resp: serde_json::Value = self.client.post(self.url("/jobs/preprocess")).json(&body).send().await?.json().await?;
        Ok(resp["job_id"].as_str().unwrap_or("").to_string())
    }

    pub async fn start_scrape(&self, req: &ScrapeRequest) -> Result<String> {
        let resp: serde_json::Value = self.client.post(self.url("/jobs/scrape")).json(req).send().await?.json().await?;
        Ok(resp["job_id"].as_str().unwrap_or("").to_string())
    }

    pub async fn start_train(&self, data_path: &str, n_clusters: u32) -> Result<String> {
        self.start_train_with_options(data_path, n_clusters, None).await
    }

    pub async fn start_train_with_options(
        &self,
        data_path: &str,
        n_clusters: u32,
        models: Option<&[String]>,
    ) -> Result<String> {
        let body = serde_json::json!({
            "data_path": data_path,
            "n_clusters": n_clusters,
            "models": models,
        });
        let resp: serde_json::Value = self.client.post(self.url("/jobs/train")).json(&body).send().await?.json().await?;
        Ok(resp["job_id"].as_str().unwrap_or("").to_string())
    }

    pub async fn start_embed(&self, corpus_path: &str) -> Result<String> {
        self.start_embed_with_options(corpus_path, 20).await
    }

    pub async fn start_embed_with_options(&self, corpus_path: &str, batch_size: u32) -> Result<String> {
        let body = serde_json::json!({"corpus_path": corpus_path, "batch_size": batch_size});
        let resp: serde_json::Value = self.client.post(self.url("/jobs/embed")).json(&body).send().await?.json().await?;
        Ok(resp["job_id"].as_str().unwrap_or("").to_string())
    }

    pub async fn start_export(&self, req: &ExportRequest) -> Result<String> {
        let resp: serde_json::Value = self.client.post(self.url("/jobs/export")).json(req).send().await?.json().await?;
        Ok(resp["job_id"].as_str().unwrap_or("").to_string())
    }

    pub async fn start_cleanup(&self, targets: &[String]) -> Result<serde_json::Value> {
        let body = serde_json::json!({"targets": targets});
        Ok(self.client.post(self.url("/jobs/cleanup")).json(&body).send().await?.json().await?)
    }

    pub async fn label_entries(&self, corpus_path: &str, output_path: &str, entries: &serde_json::Value) -> Result<serde_json::Value> {
        let body = serde_json::json!({"corpus_path": corpus_path, "output_path": output_path, "entries": entries});
        Ok(self.client.post(self.url("/jobs/label")).json(&body).send().await?.json().await?)
    }

    pub async fn job_status(&self, job_id: &str) -> Result<JobStatus> {
        Ok(self.client.get(self.url(&format!("/jobs/{}/status", job_id))).send().await?.json().await?)
    }

    pub async fn cancel_job(&self, job_id: &str) -> Result<serde_json::Value> {
        Ok(self.client.post(self.url(&format!("/jobs/{}/cancel", job_id))).send().await?.json().await?)
    }
}
