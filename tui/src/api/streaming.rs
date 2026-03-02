use anyhow::Result;
use futures::StreamExt;

#[derive(Debug, Clone)]
pub enum StreamEvent {
    Token(String),
    Done { finish_reason: String },
    Error { code: String, message: String },
}

/// parse SSE events from a reqwest streaming response
pub async fn parse_sse_stream(resp: reqwest::Response) -> Result<Vec<StreamEvent>> {
    let mut events = Vec::new();
    let mut bytes = resp.bytes_stream();
    let mut buffer = String::new();
    while let Some(chunk) = bytes.next().await {
        let chunk = chunk?;
        buffer.push_str(&String::from_utf8_lossy(&chunk));
        while let Some(pos) = buffer.find("\n\n") {
            let block = buffer[..pos].to_string();
            buffer = buffer[pos + 2..].to_string();
            if let Some(event) = parse_sse_block(&block) {
                events.push(event);
            }
        }
    }
    if !buffer.trim().is_empty() {
        if let Some(event) = parse_sse_block(&buffer) {
            events.push(event);
        }
    }
    Ok(events)
}

/// incrementally yield SSE events for use in a TUI event loop
pub struct SseReader {
    buffer: String,
}

impl SseReader {
    pub fn new() -> Self { Self { buffer: String::new() } }

    pub fn feed(&mut self, data: &[u8]) -> Vec<StreamEvent> {
        self.buffer.push_str(&String::from_utf8_lossy(data));
        let mut events = Vec::new();
        while let Some(pos) = self.buffer.find("\n\n") {
            let block = self.buffer[..pos].to_string();
            self.buffer = self.buffer[pos + 2..].to_string();
            if let Some(event) = parse_sse_block(&block) {
                events.push(event);
            }
        }
        events
    }
}

fn parse_sse_block(block: &str) -> Option<StreamEvent> {
    let mut event_type = String::new();
    let mut data = String::new();
    for line in block.lines() {
        if let Some(rest) = line.strip_prefix("event: ") {
            event_type = rest.trim().to_string();
        } else if let Some(rest) = line.strip_prefix("data: ") {
            data = rest.trim().to_string();
        }
    }
    if data.is_empty() { return None; }
    match event_type.as_str() {
        "token" => {
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&data) {
                Some(StreamEvent::Token(v["text"].as_str().unwrap_or("").to_string()))
            } else {
                Some(StreamEvent::Token(data))
            }
        }
        "done" => {
            let reason = serde_json::from_str::<serde_json::Value>(&data)
                .ok()
                .and_then(|v| v["finish_reason"].as_str().map(String::from))
                .unwrap_or_else(|| "stop".into());
            Some(StreamEvent::Done { finish_reason: reason })
        }
        "error" => {
            let v = serde_json::from_str::<serde_json::Value>(&data).unwrap_or_default();
            Some(StreamEvent::Error {
                code: v["code"].as_str().unwrap_or("unknown").to_string(),
                message: v["message"].as_str().unwrap_or(&data).to_string(),
            })
        }
        _ => None,
    }
}
