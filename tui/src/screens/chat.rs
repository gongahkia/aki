use anyhow::Result;
use crossterm::event::{KeyCode, KeyEvent};
use futures::StreamExt;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Frame;
use tokio::sync::mpsc::error::TryRecvError;
use tokio::sync::mpsc::UnboundedReceiver;

use crate::api::streaming::{SseReader, StreamEvent};
use crate::api::types::{GenerationRequest, GenerationResponse, LlmRequest};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::state::chat::{
    build_prompt, default_system_prompt, load_session, parse_chat_command, parse_hypo_topics,
    save_session, ChatCommand, ChatConfig, ChatMessage, ChatRole,
};
use crate::state::generation::TuiState;
use crate::ui::theme;

const INPUT_HINT_IDLE: &str = "Enter=send  Esc=back  PgUp/PgDn=scroll  /help=commands";
const INPUT_HINT_BUSY: &str = "request in progress... wait or /quit";
const STREAM_ASSISTANT_TITLE: &str = "Chat";

enum PendingOp {
    Streaming(StreamOp),
    Hypo(tokio::task::JoinHandle<Result<GenerationResponse>>),
    Tokens(tokio::task::JoinHandle<Result<serde_json::Value>>),
}

struct StreamOp {
    receiver: UnboundedReceiver<StreamEvent>,
    handle: tokio::task::JoinHandle<()>,
    assistant_index: usize,
}

pub struct ChatScreen {
    messages: Vec<ChatMessage>,
    config: ChatConfig,
    input: String,
    cursor: usize,
    scroll: u16,
    pending: Option<PendingOp>,
}

impl ChatScreen {
    pub fn new() -> Self {
        let state = TuiState::load();
        let config = ChatConfig {
            provider: state.last_config.provider,
            model: state.last_config.model,
            temperature: state.last_config.temperature,
            max_tokens: 2048,
            system_prompt: Some(default_system_prompt()),
            context_turn_limit: 12,
        };
        let messages = vec![ChatMessage::new(
            ChatRole::Assistant,
            "Welcome to Jikai Chat. Educational use only; this is not legal advice. Type /help for commands.",
        )];

        Self {
            messages,
            config,
            input: String::new(),
            cursor: 0,
            scroll: 0,
            pending: None,
        }
    }

    fn is_busy(&self) -> bool {
        self.pending.is_some()
    }

    fn add_message(&mut self, role: ChatRole, content: impl Into<String>) {
        self.messages.push(ChatMessage::new(role, content));
        self.scroll_to_bottom();
    }

    fn add_meta(&mut self, content: impl Into<String>) {
        self.add_message(ChatRole::Meta, content);
    }

    fn scroll_to_bottom(&mut self) {
        let lines = self.transcript_text().lines().count();
        self.scroll = lines.saturating_sub(1) as u16;
    }

    fn update_input_from_key(&mut self, key: KeyEvent) -> bool {
        match key.code {
            KeyCode::Char(c) => {
                self.input.insert(self.cursor, c);
                self.cursor += 1;
                false
            }
            KeyCode::Backspace => {
                if self.cursor > 0 {
                    self.cursor -= 1;
                    self.input.remove(self.cursor);
                }
                false
            }
            KeyCode::Delete => {
                if self.cursor < self.input.len() {
                    self.input.remove(self.cursor);
                }
                false
            }
            KeyCode::Left => {
                self.cursor = self.cursor.saturating_sub(1);
                false
            }
            KeyCode::Right => {
                if self.cursor < self.input.len() {
                    self.cursor += 1;
                }
                false
            }
            KeyCode::Home => {
                self.cursor = 0;
                false
            }
            KeyCode::End => {
                self.cursor = self.input.len();
                false
            }
            KeyCode::Enter => true,
            _ => false,
        }
    }

    fn submit_input(&mut self, ctx: &mut AppContext) -> ScreenAction {
        let raw = self.input.trim().to_string();
        self.input.clear();
        self.cursor = 0;
        match parse_chat_command(&raw) {
            ChatCommand::Empty => ScreenAction::None,
            ChatCommand::Help => {
                self.add_meta(Self::help_text());
                ScreenAction::None
            }
            ChatCommand::Clear => {
                if self.is_busy() {
                    self.add_meta("Busy: wait for current request before clearing.");
                    return ScreenAction::None;
                }
                self.messages.clear();
                self.scroll = 0;
                ScreenAction::None
            }
            ChatCommand::Provider(provider) => {
                if self.is_busy() {
                    self.add_meta("Busy: wait for current request before changing provider.");
                    return ScreenAction::None;
                }
                match provider {
                    None => {
                        self.add_meta(format!("Current provider: {}", self.config.provider));
                    }
                    Some(name) => {
                        if !Self::valid_provider(&name) {
                            self.add_meta(format!(
                                "Invalid provider '{}'. Allowed: ollama, openai, anthropic, google, local",
                                name
                            ));
                        } else {
                            self.config.provider = name;
                            self.add_meta(format!("Provider set to {}", self.config.provider));
                        }
                    }
                }
                ScreenAction::None
            }
            ChatCommand::Model(model) => {
                if self.is_busy() {
                    self.add_meta("Busy: wait for current request before changing model.");
                    return ScreenAction::None;
                }
                match model {
                    None => self.add_meta(format!(
                        "Current model: {}",
                        self.config.model.as_deref().unwrap_or("(provider default)")
                    )),
                    Some(name) => {
                        self.config.model = Some(name.clone());
                        self.add_meta(format!("Model set to {}", name));
                    }
                }
                ScreenAction::None
            }
            ChatCommand::Temp(value) => {
                if self.is_busy() {
                    self.add_meta("Busy: wait for current request before changing temperature.");
                    return ScreenAction::None;
                }
                match value {
                    None => self.add_meta(format!(
                        "Current temperature: {:.2}",
                        self.config.temperature
                    )),
                    Some(raw_value) => match raw_value.parse::<f64>() {
                        Ok(parsed) if (0.0..=2.0).contains(&parsed) => {
                            self.config.temperature = parsed;
                            self.add_meta(format!("Temperature set to {:.2}", parsed));
                        }
                        _ => self.add_meta("Usage: /temp <value between 0.0 and 2.0>"),
                    },
                }
                ScreenAction::None
            }
            ChatCommand::Tokens => {
                if self.is_busy() {
                    self.add_meta("Busy: another request is already in progress.");
                    return ScreenAction::None;
                }
                self.start_tokens_request(ctx);
                ScreenAction::None
            }
            ChatCommand::Hypo(raw_topics) => {
                if self.is_busy() {
                    self.add_meta("Busy: another request is already in progress.");
                    return ScreenAction::None;
                }
                match parse_hypo_topics(&raw_topics) {
                    Ok(topics) => {
                        self.add_message(ChatRole::User, format!("/hypo {}", raw_topics.trim()));
                        self.add_meta(format!(
                            "Generating hypothetical for topics: {}",
                            topics.join(", ")
                        ));
                        self.start_hypo_request(ctx, topics);
                    }
                    Err(msg) => self.add_meta(msg),
                }
                ScreenAction::None
            }
            ChatCommand::System(system) => {
                if self.is_busy() {
                    self.add_meta("Busy: wait for current request before changing system prompt.");
                    return ScreenAction::None;
                }
                match system {
                    None => self.add_meta(format!(
                        "System prompt: {}",
                        self.config.system_prompt.as_deref().unwrap_or("(none)")
                    )),
                    Some(text) => {
                        self.config.system_prompt = Some(text.clone());
                        self.add_meta("System prompt updated.");
                    }
                }
                ScreenAction::None
            }
            ChatCommand::Save(path) => {
                if self.is_busy() {
                    self.add_meta("Busy: wait for current request before saving.");
                    return ScreenAction::None;
                }
                match save_session(&self.config, &self.messages, path.as_deref()) {
                    Ok(saved_path) => {
                        self.add_meta(format!("Session saved: {}", saved_path.display()));
                    }
                    Err(e) => {
                        self.add_meta(format!("Failed to save session: {}", e));
                    }
                }
                ScreenAction::None
            }
            ChatCommand::Load(path) => {
                if self.is_busy() {
                    self.add_meta("Busy: wait for current request before loading.");
                    return ScreenAction::None;
                }
                let Some(path) = path else {
                    self.add_meta("Usage: /load <path-to-session.json>");
                    return ScreenAction::None;
                };
                match load_session(&path) {
                    Ok(session) => {
                        self.config = session.config;
                        self.messages = session.messages;
                        self.scroll_to_bottom();
                    }
                    Err(e) => self.add_meta(format!("Failed to load session: {}", e)),
                }
                ScreenAction::None
            }
            ChatCommand::Quit => {
                self.cancel_pending();
                ScreenAction::Pop
            }
            ChatCommand::Unknown(name) => {
                self.add_meta(format!(
                    "Unknown command '/{}'. Type /help for usage.",
                    name
                ));
                ScreenAction::None
            }
            ChatCommand::PlainPrompt(user_text) => {
                if self.is_busy() {
                    self.add_meta("Busy: another request is already in progress.");
                    return ScreenAction::None;
                }
                let prompt =
                    build_prompt(&self.messages, &user_text, self.config.context_turn_limit);
                self.add_message(ChatRole::User, user_text);
                self.start_stream_request(ctx, prompt);
                ScreenAction::None
            }
        }
    }

    fn start_stream_request(&mut self, ctx: &AppContext, prompt: String) {
        let assistant_index = self.messages.len();
        self.add_message(ChatRole::Assistant, "");

        let api = ctx.api_url.clone();
        let provider = self.config.provider.clone();
        let request = LlmRequest {
            prompt,
            system_prompt: self.config.system_prompt.clone(),
            temperature: self.config.temperature,
            max_tokens: self.config.max_tokens,
            model: self.config.model.clone(),
            correlation_id: None,
            timeout_seconds: None,
        };
        let request_model = request.model.clone();
        let (sender, receiver) = tokio::sync::mpsc::unbounded_channel::<StreamEvent>();
        let handle = tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            let response = match client
                .llm_stream(&request, Some(provider.as_str()), request_model.as_deref())
                .await
            {
                Ok(resp) => resp,
                Err(e) => {
                    let _ = sender.send(StreamEvent::Error {
                        code: "request_failed".into(),
                        message: e.to_string(),
                    });
                    return;
                }
            };

            let status = response.status();
            if !status.is_success() {
                let body = response.text().await.unwrap_or_default();
                let message = if body.trim().is_empty() {
                    format!("HTTP {}", status)
                } else {
                    body
                };
                let _ = sender.send(StreamEvent::Error {
                    code: format!("http_{}", status.as_u16()),
                    message,
                });
                return;
            }

            let mut reader = SseReader::new();
            let mut bytes_stream = response.bytes_stream();
            while let Some(item) = bytes_stream.next().await {
                match item {
                    Ok(bytes) => {
                        for event in reader.feed(&bytes) {
                            let is_done = matches!(event, StreamEvent::Done { .. });
                            let _ = sender.send(event);
                            if is_done {
                                return;
                            }
                        }
                    }
                    Err(e) => {
                        let _ = sender.send(StreamEvent::Error {
                            code: "stream_read_failed".into(),
                            message: e.to_string(),
                        });
                        return;
                    }
                }
            }

            let _ = sender.send(StreamEvent::Done {
                finish_reason: "eof".into(),
            });
        });

        self.pending = Some(PendingOp::Streaming(StreamOp {
            receiver,
            handle,
            assistant_index,
        }));
    }

    fn start_tokens_request(&mut self, ctx: &AppContext) {
        self.add_meta("Fetching session token/cost usage...");
        let api = ctx.api_url.clone();
        let handle = tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.session_cost().await
        });
        self.pending = Some(PendingOp::Tokens(handle));
    }

    fn start_hypo_request(&mut self, ctx: &AppContext, topics: Vec<String>) {
        let state = TuiState::load();
        let complexity_num = state.last_config.complexity.parse::<u32>().unwrap_or(3);
        let number_parties = state.last_config.parties.parse::<u32>().unwrap_or(2);
        let complexity_level = Self::map_complexity(complexity_num).to_string();
        let mut user_preferences = std::collections::HashMap::new();
        user_preferences.insert(
            "temperature".into(),
            serde_json::json!(self.config.temperature),
        );

        let req = GenerationRequest {
            topics,
            law_domain: "tort".into(),
            number_parties,
            complexity_level,
            sample_size: 3,
            user_preferences: Some(user_preferences),
            method: state.last_config.method,
            provider: Some(self.config.provider.clone()),
            model: self.config.model.clone(),
            include_analysis: state.last_config.include_analysis,
            correlation_id: None,
        };

        let api = ctx.api_url.clone();
        let handle = tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.generate(&req).await
        });
        self.pending = Some(PendingOp::Hypo(handle));
    }

    fn map_complexity(value: u32) -> &'static str {
        match value {
            1 => "beginner",
            2 => "basic",
            3 => "intermediate",
            4 => "advanced",
            _ => "expert",
        }
    }

    fn valid_provider(value: &str) -> bool {
        matches!(
            value,
            "ollama" | "openai" | "anthropic" | "google" | "local"
        )
    }

    fn handle_stream_events(&mut self) {
        let mut clear_pending = false;
        let mut appended_token = false;

        if let Some(PendingOp::Streaming(stream)) = &mut self.pending {
            loop {
                match stream.receiver.try_recv() {
                    Ok(StreamEvent::Token(text)) => {
                        if let Some(msg) = self.messages.get_mut(stream.assistant_index) {
                            msg.content.push_str(&text);
                            appended_token = true;
                        }
                    }
                    Ok(StreamEvent::Done { finish_reason }) => {
                        if finish_reason != "stop" && finish_reason != "eof" {
                            self.add_meta(format!("Response finished: {}", finish_reason));
                        }
                        clear_pending = true;
                        break;
                    }
                    Ok(StreamEvent::Error { code, message }) => {
                        self.add_meta(format!("Stream error [{}]: {}", code, message));
                        clear_pending = true;
                        break;
                    }
                    Err(TryRecvError::Empty) => break,
                    Err(TryRecvError::Disconnected) => {
                        self.add_meta("Stream ended unexpectedly.");
                        clear_pending = true;
                        break;
                    }
                }
            }
        }

        if appended_token {
            self.scroll_to_bottom();
        }

        if clear_pending {
            self.pending = None;
        }
    }

    fn maybe_resolve_pending_jobs(&mut self) {
        let hypo_finished = matches!(
            self.pending.as_ref(),
            Some(PendingOp::Hypo(handle)) if handle.is_finished()
        );
        if hypo_finished {
            if let Some(PendingOp::Hypo(handle)) = self.pending.take() {
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(response)) => {
                        let mut content = format!("Hypothetical:\n\n{}", response.hypothetical);
                        if !response.analysis.trim().is_empty() {
                            content.push_str("\n\nAnalysis:\n\n");
                            content.push_str(response.analysis.trim());
                        }
                        self.add_message(ChatRole::Assistant, content);
                    }
                    Ok(Err(e)) => self.add_meta(format!("Hypothetical generation failed: {}", e)),
                    Err(e) => self.add_meta(format!("Hypothetical task failed: {}", e)),
                }
            }
        }

        let tokens_finished = matches!(
            self.pending.as_ref(),
            Some(PendingOp::Tokens(handle)) if handle.is_finished()
        );
        if tokens_finished {
            if let Some(PendingOp::Tokens(handle)) = self.pending.take() {
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(payload)) => {
                        let cost = payload
                            .get("total_cost_usd")
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0);
                        let in_tokens = payload
                            .get("total_input_tokens")
                            .and_then(|v| v.as_u64())
                            .unwrap_or(0);
                        let out_tokens = payload
                            .get("total_output_tokens")
                            .and_then(|v| v.as_u64())
                            .unwrap_or(0);
                        self.add_meta(format!(
                            "Session cost: ${:.6} | input tokens: {} | output tokens: {}",
                            cost, in_tokens, out_tokens
                        ));
                    }
                    Ok(Err(e)) => self.add_meta(format!("Failed to fetch session cost: {}", e)),
                    Err(e) => self.add_meta(format!("Session cost task failed: {}", e)),
                }
            }
        }
    }

    fn transcript_text(&self) -> String {
        let mut out = String::new();
        for message in &self.messages {
            let prefix = message.role.prefix();
            if message.content.is_empty() {
                out.push_str(prefix);
                out.push('\n');
                continue;
            }
            let mut line_count = 0usize;
            for line in message.content.lines() {
                if line_count == 0 {
                    out.push_str(prefix);
                    out.push(' ');
                    out.push_str(line);
                } else {
                    out.push_str("      ");
                    out.push_str(line);
                }
                out.push('\n');
                line_count += 1;
            }
            if line_count == 0 {
                out.push_str(prefix);
                out.push('\n');
            }
        }
        out
    }

    fn render_input_line(&self) -> String {
        let mut display = self.input.clone();
        let cursor = self.cursor.min(display.len());
        display.insert(cursor, '_');
        display
    }

    fn help_text() -> &'static str {
        "Commands:
/help                show this help
/clear               clear transcript
/provider [name]     show or set provider
/model [name]        show or set model
/temp [value]        show or set temperature (0.0-2.0)
/tokens              show session token/cost summary
/hypo t1,t2          generate hypothetical via workflow pipeline
/system [text]       show or set system prompt
/save [path]         save chat session to JSON
/load <path>         load chat session from JSON
/quit                leave chat"
    }

    fn cancel_pending(&mut self) {
        if let Some(pending) = self.pending.take() {
            match pending {
                PendingOp::Streaming(stream) => {
                    stream.handle.abort();
                }
                PendingOp::Hypo(handle) => {
                    handle.abort();
                }
                PendingOp::Tokens(handle) => {
                    handle.abort();
                }
            }
        }
    }
}

impl Screen for ChatScreen {
    fn name(&self) -> &str {
        "Chat"
    }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc => {
                self.cancel_pending();
                return ScreenAction::Pop;
            }
            KeyCode::Up => {
                self.scroll = self.scroll.saturating_sub(1);
                return ScreenAction::None;
            }
            KeyCode::Down => {
                self.scroll = self.scroll.saturating_add(1);
                return ScreenAction::None;
            }
            KeyCode::PageUp => {
                self.scroll = self.scroll.saturating_sub(8);
                return ScreenAction::None;
            }
            KeyCode::PageDown => {
                self.scroll = self.scroll.saturating_add(8);
                return ScreenAction::None;
            }
            _ => {}
        }

        if self.update_input_from_key(key) {
            return self.submit_input(ctx);
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Min(3), Constraint::Length(3)])
            .split(area);

        let transcript_title =
            Span::styled(format!(" {} ", STREAM_ASSISTANT_TITLE), theme::title());
        let transcript_block = Block::default()
            .title(transcript_title)
            .borders(Borders::ALL)
            .border_style(theme::border());
        let transcript_text = self.transcript_text();
        let transcript = Paragraph::new(transcript_text)
            .block(transcript_block)
            .wrap(Wrap { trim: false })
            .scroll((self.scroll, 0));
        f.render_widget(transcript, chunks[0]);

        let hint = if self.is_busy() {
            INPUT_HINT_BUSY
        } else {
            INPUT_HINT_IDLE
        };
        let input_block = Block::default()
            .title(Span::styled(" Input ", theme::title()))
            .title_bottom(Span::styled(format!(" {} ", hint), theme::dim()))
            .borders(Borders::ALL)
            .border_style(theme::border());
        let input = Paragraph::new(self.render_input_line()).block(input_block);
        f.render_widget(input, chunks[1]);
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        self.handle_stream_events();
        self.maybe_resolve_pending_jobs();
    }
}
