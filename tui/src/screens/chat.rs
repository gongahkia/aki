use crossterm::event::{KeyCode, KeyEvent};
use futures::StreamExt;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Frame;
use std::collections::HashMap;
use std::future::Future;
use tokio::sync::mpsc::error::TryRecvError;
use tokio::sync::mpsc::UnboundedReceiver;

use crate::api::streaming::{SseReader, StreamEvent};
use crate::api::types::{
    CorpusEntry, CorpusQueryRequest, CorpusQueryResponse, ExportRequest, GenerationReport,
    GenerationRequest, GenerationResponse, HistoryRecord, JobStatus, LlmRequest, RegenerateRequest,
    RegenerationResponse, ReportRequest, ScrapeRequest, ValidateRequest,
};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::state::chat::{
    build_prompt, command_meta, default_system_prompt, infer_chat_intent, load_session,
    normalize_topic, parse_chat_command, parse_csv, parse_hypo_topics, save_session, ChatCommand,
    ChatConfig, ChatIntent, ChatMessage, ChatRole, CommandArgs,
};
use crate::state::generation::TuiState;
use crate::ui::theme;

const INPUT_HINT_IDLE: &str =
    "Enter=send  Esc=back  PgUp/PgDn=scroll  /help=commands  /menu=legacy menu";
const INPUT_HINT_BUSY: &str = "request in progress... wait or /quit";
const STREAM_ASSISTANT_TITLE: &str = "Chat";
const DEFAULT_LABEL_OUTPUT_PATH: &str = "corpus/labelled/sample.csv";
const DEFAULT_LABEL_CORPUS_PATH: &str = "corpus/clean/tort/corpus.json";

#[derive(Debug)]
enum PendingOp {
    Streaming(StreamOp),
    Task(TaskOp),
}

#[derive(Debug)]
struct StreamOp {
    receiver: UnboundedReceiver<StreamEvent>,
    handle: tokio::task::JoinHandle<()>,
    assistant_index: usize,
}

#[derive(Debug)]
struct TaskOp {
    kind: TaskKind,
    handle: tokio::task::JoinHandle<anyhow::Result<TaskPayload>>,
}

#[derive(Debug, Clone)]
enum TaskKind {
    Tokens,
    Hypo,
    Regenerate,
    Report,
    Reports,
    Generation,
    Topics,
    Corpus,
    Query,
    Validate,
    Preprocess,
    Scrape,
    Train,
    Embed,
    Export,
    Cleanup,
    JobStatus,
    JobCancel,
    History,
    Stats,
    Providers,
    Models,
    LabelLoad {
        output_path: String,
        corpus_path: String,
    },
    LabelPersist,
}

#[derive(Debug)]
enum TaskPayload {
    Json(serde_json::Value),
    Generation(GenerationResponse),
    Regeneration(RegenerationResponse),
    Reports(Vec<GenerationReport>),
    Topics(Vec<String>),
    CorpusEntries(Vec<CorpusEntry>),
    CorpusQuery(CorpusQueryResponse),
    History(Vec<HistoryRecord>),
    JobId(String),
    JobStatus(JobStatus),
    Message(String),
}

#[derive(Debug, Clone)]
struct PendingConfirmation {
    command: ChatCommand,
    summary: String,
}

#[derive(Debug, Default, Clone)]
struct ChatRuntimeContext {
    last_generation_id: Option<i64>,
    last_job_id: Option<String>,
    last_hypothetical: Option<String>,
    last_topics: Vec<String>,
    last_export_path: Option<String>,
}

#[derive(Debug, Clone)]
struct LabelDraftEntry {
    text: String,
    topics: Vec<String>,
}

#[derive(Debug, Clone)]
struct LabelSession {
    entries: Vec<CorpusEntry>,
    labels: Vec<LabelDraftEntry>,
    current_idx: usize,
    output_path: String,
    corpus_path: String,
}

impl LabelSession {
    fn has_current(&self) -> bool {
        self.current_idx < self.entries.len()
    }

    fn current_entry(&self) -> Option<&CorpusEntry> {
        self.entries.get(self.current_idx)
    }
}

pub struct ChatScreen {
    messages: Vec<ChatMessage>,
    config: ChatConfig,
    input: String,
    cursor: usize,
    scroll: u16,
    pending: Option<PendingOp>,
    pending_confirmation: Option<PendingConfirmation>,
    runtime_ctx: ChatRuntimeContext,
    guided_step: Option<usize>,
    label_session: Option<LabelSession>,
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
            pending_confirmation: None,
            runtime_ctx: ChatRuntimeContext::default(),
            guided_step: None,
            label_session: None,
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

        let command = parse_chat_command(&raw);
        if !matches!(command, ChatCommand::Empty) {
            self.add_message(ChatRole::User, raw.clone());
        }

        if self.pending_confirmation.is_some() {
            match command {
                ChatCommand::Yes => return self.confirm_pending(ctx),
                ChatCommand::No => {
                    self.pending_confirmation = None;
                    self.add_meta("Cancelled pending command.");
                    return ScreenAction::None;
                }
                ChatCommand::Quit => {
                    self.cancel_pending();
                    self.pending_confirmation = None;
                    return ScreenAction::Pop;
                }
                _ => {
                    self.add_meta(
                        "Pending confirmation active. Use /yes to proceed or /no to cancel.",
                    );
                    return ScreenAction::None;
                }
            }
        }

        match command {
            ChatCommand::Empty => ScreenAction::None,
            ChatCommand::PlainPrompt(user_text) => self.handle_plain_prompt(ctx, user_text),
            ChatCommand::Unknown(name, _) => {
                let suggestions = self.unknown_command_suggestions(&name);
                self.add_meta(format!(
                    "Unknown command '/{}'. {}",
                    name,
                    if suggestions.is_empty() {
                        "Type /help for usage.".to_string()
                    } else {
                        format!("Try: {}", suggestions.join(" | "))
                    }
                ));
                ScreenAction::None
            }
            ChatCommand::Yes => {
                self.add_meta("No pending command to confirm.");
                ScreenAction::None
            }
            ChatCommand::No => {
                self.add_meta("No pending command to cancel.");
                ScreenAction::None
            }
            other => self.execute_command(ctx, other, false),
        }
    }

    fn handle_plain_prompt(&mut self, ctx: &mut AppContext, user_text: String) -> ScreenAction {
        if self.is_busy() {
            self.add_meta("Busy: another request is already in progress.");
            return ScreenAction::None;
        }

        match infer_chat_intent(&user_text) {
            ChatIntent::Command(command) => {
                self.add_meta(format!(
                    "Interpreted intent as /{}",
                    self.command_name(&command)
                ));
                self.execute_command(ctx, command, false)
            }
            ChatIntent::Ambiguous(suggestions) => {
                self.add_meta(format!(
                    "Ambiguous request. Try one of: {}",
                    suggestions.join(" | ")
                ));
                ScreenAction::None
            }
            ChatIntent::None => {
                let prompt =
                    build_prompt(&self.messages, &user_text, self.config.context_turn_limit);
                self.start_stream_request(ctx, prompt);
                ScreenAction::None
            }
        }
    }

    fn execute_command(
        &mut self,
        ctx: &mut AppContext,
        command: ChatCommand,
        bypass_confirmation: bool,
    ) -> ScreenAction {
        if self.is_busy() && !matches!(command, ChatCommand::Quit) {
            self.add_meta("Busy: another request is already in progress.");
            return ScreenAction::None;
        }

        if let Some(meta) = command_meta(&command) {
            if meta.requires_confirmation && !bypass_confirmation {
                let summary = self.command_summary(&command);
                self.pending_confirmation = Some(PendingConfirmation {
                    command: command.clone(),
                    summary: summary.clone(),
                });
                self.add_meta(format!(
                    "Confirm command: {}. Use /yes to proceed or /no to cancel.",
                    summary
                ));
                return ScreenAction::None;
            }
        }

        match command {
            ChatCommand::Help => {
                self.add_meta(Self::help_text());
                ScreenAction::None
            }
            ChatCommand::Clear => {
                self.messages.clear();
                self.scroll = 0;
                ScreenAction::None
            }
            ChatCommand::Menu => {
                ScreenAction::Push(Box::new(super::main_menu::MainMenuScreen::new()))
            }
            ChatCommand::Provider(provider) => {
                match provider {
                    None => self.add_meta(format!("Current provider: {}", self.config.provider)),
                    Some(name) => {
                        if !Self::valid_provider(&name) {
                            self.add_meta(format!(
                                "Invalid provider '{}'. Allowed: ollama, openai, anthropic, google, local",
                                name
                            ));
                        } else {
                            self.config.provider = name.clone();
                            self.add_meta(format!("Provider set to {}", name));
                        }
                    }
                }
                ScreenAction::None
            }
            ChatCommand::Model(model) => {
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
                self.start_task(TaskKind::Tokens, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let payload = client.session_cost().await?;
                        Ok(TaskPayload::Json(payload))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Hypo(args) => {
                let (req, topics) = match self.build_hypo_request(&args) {
                    Ok(v) => v,
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                self.runtime_ctx.last_topics = topics.clone();
                self.add_meta(format!(
                    "Generating hypothetical for topics: {}",
                    topics.join(", ")
                ));
                self.start_task(TaskKind::Hypo, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let response = client.generate(&req).await?;
                        Ok(TaskPayload::Generation(response))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Regenerate(args) => {
                let generation_id = match self.resolve_generation_ref(
                    args.first()
                        .or(args.get("generation_id"))
                        .or(args.get("generation")),
                ) {
                    Ok(id) => id,
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                let req = RegenerateRequest {
                    generation_id,
                    correlation_id: None,
                    fallback_request: None,
                };
                self.start_task(TaskKind::Regenerate, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let response = client.regenerate(&req).await?;
                        Ok(TaskPayload::Regeneration(response))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Report(args) => {
                let generation_id = match self.resolve_generation_ref(
                    args.first()
                        .or(args.get("generation_id"))
                        .or(args.get("generation")),
                ) {
                    Ok(id) => id,
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                let issue_raw = args
                    .get("issue")
                    .or(args.get("issues"))
                    .or_else(|| args.positionals.get(1).map(String::as_str))
                    .unwrap_or("");
                let issue_types = parse_csv(issue_raw);
                if issue_types.is_empty() {
                    self.add_meta(
                        "Usage: /report <generation_id|last> issue=<csv> [comment=\"...\"]",
                    );
                    return ScreenAction::None;
                }
                let comment = args.get("comment").map(str::to_string);
                let req = ReportRequest {
                    generation_id,
                    issue_types,
                    comment,
                    correlation_id: None,
                    is_locked: true,
                };
                self.start_task(TaskKind::Report, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let report_id = client.save_report(&req).await?;
                        Ok(TaskPayload::Message(format!(
                            "Report saved with ID {}",
                            report_id
                        )))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Reports(args) => {
                let generation_id = match self.resolve_generation_ref(
                    args.first()
                        .or(args.get("generation_id"))
                        .or(args.get("generation")),
                ) {
                    Ok(id) => id,
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                self.start_task(TaskKind::Reports, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let reports = client.list_reports(generation_id).await?;
                        Ok(TaskPayload::Reports(reports))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Generation(args) => {
                let generation_id = match self.resolve_generation_ref(
                    args.first()
                        .or(args.get("generation_id"))
                        .or(args.get("generation")),
                ) {
                    Ok(id) => id,
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                self.start_task(TaskKind::Generation, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let payload = client.get_generation(generation_id).await?;
                        Ok(TaskPayload::Json(payload))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Topics => {
                self.start_task(TaskKind::Topics, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let topics = client.list_topics().await?;
                        Ok(TaskPayload::Topics(topics))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Corpus(args) => {
                let topic = args
                    .get("topic")
                    .or_else(|| args.first())
                    .map(str::to_string);
                let limit = match self
                    .parse_u32_option(args.get("limit").or_else(|| args.get("n")), "limit")
                {
                    Ok(v) => v.unwrap_or(20),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                self.start_task(TaskKind::Corpus, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let entries = client.list_corpus_entries(topic.as_deref(), limit).await?;
                        Ok(TaskPayload::CorpusEntries(entries))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Query(args) => {
                let topics_raw = args.get("topics").or_else(|| args.first()).unwrap_or("");
                let mut topics: Vec<String> = parse_csv(topics_raw)
                    .into_iter()
                    .map(|v| normalize_topic(&v))
                    .collect();
                if topics.is_empty() {
                    self.add_meta("Usage: /query topics=<topic1,topic2> [sample=5] [overlap=1]");
                    return ScreenAction::None;
                }
                topics.sort();
                topics.dedup();

                let sample_size = match self.parse_u32_option(
                    args.get("sample").or_else(|| args.get("sample_size")),
                    "sample",
                ) {
                    Ok(v) => v.unwrap_or(5),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                let overlap = match self.parse_u32_option(
                    args.get("overlap")
                        .or_else(|| args.get("min_topic_overlap")),
                    "overlap",
                ) {
                    Ok(v) => v.unwrap_or(1),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };

                let req = CorpusQueryRequest {
                    topics,
                    sample_size,
                    exclude_ids: vec![],
                    min_topic_overlap: overlap,
                };
                self.start_task(TaskKind::Query, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let response = client.query_corpus(&req).await?;
                        Ok(TaskPayload::CorpusQuery(response))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Validate(args) => {
                let required_raw = args
                    .get("required")
                    .or_else(|| args.get("topics"))
                    .unwrap_or("");
                let required_topics: Vec<String> = parse_csv(required_raw)
                    .into_iter()
                    .map(|v| normalize_topic(&v))
                    .collect();
                if required_topics.is_empty() {
                    self.add_meta(
                        "Usage: /validate required=<topic1,topic2> [parties=2] [text=\"...\"]",
                    );
                    return ScreenAction::None;
                }

                let expected_parties = match self.parse_u32_option(args.get("parties"), "parties") {
                    Ok(v) => v.unwrap_or(2),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };

                let text = if let Some(value) = args.get("text") {
                    value.to_string()
                } else if let Some(last) = &self.runtime_ctx.last_hypothetical {
                    last.clone()
                } else {
                    self.add_meta("Validation text missing. Provide text=\"...\" or generate a hypothetical first.");
                    return ScreenAction::None;
                };

                let req = ValidateRequest {
                    text,
                    required_topics,
                    expected_parties,
                    law_domain: "tort".into(),
                    fast_mode: false,
                };
                self.start_task(TaskKind::Validate, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let payload = client.validate(&req).await?;
                        Ok(TaskPayload::Json(payload))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Preprocess(args) => {
                let merge_existing = match self.parse_bool_option(args.get("merge"), "merge") {
                    Ok(v) => v.unwrap_or(true),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                let include_non_tort = match self
                    .parse_bool_option(args.get("include_non_tort"), "include_non_tort")
                {
                    Ok(v) => v.unwrap_or(false),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };

                let raw_dir = args.get("raw_dir").map(str::to_string);
                let output_path = args.get("output_path").map(str::to_string);
                self.start_task(TaskKind::Preprocess, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let job_id = client
                            .start_preprocess_with_options(
                                raw_dir.as_deref(),
                                output_path.as_deref(),
                                merge_existing,
                                include_non_tort,
                            )
                            .await?;
                        Ok(TaskPayload::JobId(job_id))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Scrape(args) => {
                let source = args
                    .get("source")
                    .or_else(|| args.first())
                    .map(str::to_string);
                let Some(source) = source else {
                    self.add_meta(
                        "Usage: /scrape source=<commonlii|judiciary|sicc|gazette> [max_cases=50] [courts=csv] [years=csv] [tort_only=true|false]",
                    );
                    return ScreenAction::None;
                };
                if !matches!(
                    source.as_str(),
                    "commonlii" | "judiciary" | "sicc" | "gazette"
                ) {
                    self.add_meta(
                        "Invalid source. Use one of: commonlii, judiciary, sicc, gazette.",
                    );
                    return ScreenAction::None;
                }
                let max_cases = match self.parse_u32_option(args.get("max_cases"), "max_cases") {
                    Ok(v) => v.unwrap_or(50),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                let tort_only = match self.parse_bool_option(args.get("tort_only"), "tort_only") {
                    Ok(v) => v.unwrap_or(true),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                let courts = args.get("courts").map(parse_csv).filter(|v| !v.is_empty());
                let years = args
                    .get("years")
                    .map(parse_csv)
                    .filter(|v| !v.is_empty())
                    .map(|vals| {
                        vals.into_iter()
                            .filter_map(|raw| raw.parse::<i32>().ok())
                            .collect::<Vec<i32>>()
                    })
                    .filter(|v| !v.is_empty());

                let req = ScrapeRequest {
                    source,
                    courts,
                    years,
                    max_cases,
                    tort_only,
                };
                self.start_task(TaskKind::Scrape, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let job_id = client.start_scrape(&req).await?;
                        Ok(TaskPayload::JobId(job_id))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Train(args) => {
                let data_path = args
                    .get("data_path")
                    .unwrap_or("corpus/labelled/sample.csv")
                    .to_string();
                let n_clusters = match self.parse_u32_option(args.get("n_clusters"), "n_clusters") {
                    Ok(v) => v.unwrap_or(5),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                let models = args.get("models").map(parse_csv).filter(|v| !v.is_empty());

                self.start_task(TaskKind::Train, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let job_id = client
                            .start_train_with_options(&data_path, n_clusters, models.as_deref())
                            .await?;
                        Ok(TaskPayload::JobId(job_id))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Embed(args) => {
                let corpus_path = args
                    .get("corpus_path")
                    .unwrap_or("corpus/clean/tort/corpus.json")
                    .to_string();
                let batch_size = match self.parse_u32_option(args.get("batch_size"), "batch_size") {
                    Ok(v) => v.unwrap_or(20),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };

                self.start_task(TaskKind::Embed, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let job_id = client
                            .start_embed_with_options(&corpus_path, batch_size)
                            .await?;
                        Ok(TaskPayload::JobId(job_id))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Export(args) => {
                let format = args.get("format").unwrap_or("docx").to_lowercase();
                if !matches!(format.as_str(), "docx" | "pdf") {
                    self.add_meta("Invalid export format. Use docx or pdf.");
                    return ScreenAction::None;
                }
                let output_path = args.get("output_path").map(str::to_string);

                let generation_id = match args
                    .get("generation_id")
                    .or(args.get("generation"))
                    .or(args.first())
                {
                    Some(raw) => match self.resolve_generation_ref(Some(raw)) {
                        Ok(id) => Some(id),
                        Err(msg) => {
                            self.add_meta(msg);
                            return ScreenAction::None;
                        }
                    },
                    None => self.runtime_ctx.last_generation_id,
                };

                let req = if generation_id.is_some() {
                    ExportRequest {
                        generation_id,
                        hypothetical: None,
                        analysis: None,
                        model_answer: None,
                        format,
                        output_path,
                    }
                } else {
                    let Some(hypothetical) = self.runtime_ctx.last_hypothetical.clone() else {
                        self.add_meta("No generation context found. Use generation_id=<id|last> or generate first.");
                        return ScreenAction::None;
                    };
                    ExportRequest {
                        generation_id: None,
                        hypothetical: Some(hypothetical),
                        analysis: None,
                        model_answer: None,
                        format,
                        output_path,
                    }
                };

                self.start_task(TaskKind::Export, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let job_id = client.start_export(&req).await?;
                        Ok(TaskPayload::JobId(job_id))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Cleanup(args) => {
                let targets = parse_csv(args.get("targets").or_else(|| args.first()).unwrap_or(""));
                if targets.is_empty() {
                    self.add_meta(
                        "Usage: /cleanup targets=config,models,history,embeddings,logs,labelled,database",
                    );
                    return ScreenAction::None;
                }
                self.start_task(TaskKind::Cleanup, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let payload = client.start_cleanup(&targets).await?;
                        Ok(TaskPayload::Json(payload))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Job(args) => {
                let mut positionals = args.positionals.clone();
                let mut subcommand = positionals.first().map(|v| v.to_lowercase());
                if subcommand.is_none() {
                    subcommand = Some("status".into());
                }

                let mut job_ref = args.get("job_id").or(args.get("id")).map(str::to_string);
                if job_ref.is_none() {
                    if let Some(cmd) = subcommand.as_deref() {
                        if cmd == "status" || cmd == "cancel" {
                            if positionals.len() >= 2 {
                                job_ref = Some(positionals.remove(1));
                            }
                        } else {
                            job_ref = Some(positionals.remove(0));
                            subcommand = Some("status".into());
                        }
                    }
                }

                let action = subcommand.unwrap_or_else(|| "status".into());
                match action.as_str() {
                    "status" => {
                        let job_id = match self.resolve_job_ref(job_ref.as_deref()) {
                            Ok(v) => v,
                            Err(msg) => {
                                self.add_meta(msg);
                                return ScreenAction::None;
                            }
                        };
                        self.start_task(TaskKind::JobStatus, {
                            let api = ctx.api_url.clone();
                            async move {
                                let client = crate::api::client::ApiClient::new(&api);
                                let status = client.job_status(&job_id).await?;
                                Ok(TaskPayload::JobStatus(status))
                            }
                        });
                    }
                    "cancel" => {
                        let job_id = match self.resolve_job_ref(job_ref.as_deref()) {
                            Ok(v) => v,
                            Err(msg) => {
                                self.add_meta(msg);
                                return ScreenAction::None;
                            }
                        };
                        self.start_task(TaskKind::JobCancel, {
                            let api = ctx.api_url.clone();
                            async move {
                                let client = crate::api::client::ApiClient::new(&api);
                                let payload = client.cancel_job(&job_id).await?;
                                Ok(TaskPayload::Json(payload))
                            }
                        });
                    }
                    _ => {
                        self.add_meta(
                            "Usage: /job status <job_id|last> OR /job cancel <job_id|last>",
                        );
                    }
                }

                ScreenAction::None
            }
            ChatCommand::History(args) => {
                let limit = match self
                    .parse_u32_option(args.get("limit").or_else(|| args.first()), "limit")
                {
                    Ok(v) => v.unwrap_or(20),
                    Err(msg) => {
                        self.add_meta(msg);
                        return ScreenAction::None;
                    }
                };
                self.start_task(TaskKind::History, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let records = client.get_history(limit).await?;
                        Ok(TaskPayload::History(records))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Stats => {
                self.start_task(TaskKind::Stats, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let payload = client.get_statistics().await?;
                        Ok(TaskPayload::Json(payload))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Providers => {
                self.start_task(TaskKind::Providers, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let health = client.llm_health(None).await?;
                        let models = client.llm_models(None).await?;
                        Ok(TaskPayload::Json(serde_json::json!({
                            "health": health,
                            "models": models,
                        })))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Models(args) => {
                let provider = args
                    .get("provider")
                    .or_else(|| args.first())
                    .map(str::to_string);
                self.start_task(TaskKind::Models, {
                    let api = ctx.api_url.clone();
                    async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let payload = client.llm_models(provider.as_deref()).await?;
                        Ok(TaskPayload::Json(payload))
                    }
                });
                ScreenAction::None
            }
            ChatCommand::Settings(args) => {
                let action = args.first().unwrap_or("view").to_lowercase();
                if action == "reset" {
                    let state = TuiState::default();
                    state.save();
                    self.add_meta("Settings reset to defaults.");
                } else {
                    let state = TuiState::load();
                    let text = format!(
                        "Provider: {}\nModel: {}\nTemperature: {:.1}\nComplexity: {}\nParties: {}\nMethod: {}\nInclude Analysis: {}",
                        state.last_config.provider,
                        state.last_config.model.as_deref().unwrap_or("default"),
                        state.last_config.temperature,
                        state.last_config.complexity,
                        state.last_config.parties,
                        state.last_config.method,
                        if state.last_config.include_analysis {
                            "yes"
                        } else {
                            "no"
                        },
                    );
                    self.add_meta(text);
                }
                ScreenAction::None
            }
            ChatCommand::Guided(args) => {
                let action = args.first().unwrap_or("start").to_lowercase();
                self.handle_guided_action(&action);
                ScreenAction::None
            }
            ChatCommand::Label(args) => {
                let action = args.first().unwrap_or("start").to_lowercase();
                match action.as_str() {
                    "start" => {
                        let limit = match self.parse_u32_option(
                            args.get("limit")
                                .or_else(|| args.positionals.get(1).map(String::as_str)),
                            "limit",
                        ) {
                            Ok(v) => v.unwrap_or(20),
                            Err(msg) => {
                                self.add_meta(msg);
                                return ScreenAction::None;
                            }
                        };
                        let output_path = args
                            .get("output_path")
                            .unwrap_or(DEFAULT_LABEL_OUTPUT_PATH)
                            .to_string();
                        let corpus_path = args
                            .get("corpus_path")
                            .unwrap_or(DEFAULT_LABEL_CORPUS_PATH)
                            .to_string();
                        self.start_task(
                            TaskKind::LabelLoad {
                                output_path,
                                corpus_path,
                            },
                            {
                                let api = ctx.api_url.clone();
                                async move {
                                    let client = crate::api::client::ApiClient::new(&api);
                                    let entries = client.list_corpus_entries(None, limit).await?;
                                    Ok(TaskPayload::CorpusEntries(entries))
                                }
                            },
                        );
                    }
                    "set" => {
                        let mut topics_raw = args
                            .positionals
                            .get(1)
                            .cloned()
                            .unwrap_or_else(|| args.get("topics").unwrap_or("").to_string());
                        if topics_raw.is_empty() {
                            topics_raw = args
                                .positionals
                                .iter()
                                .skip(1)
                                .cloned()
                                .collect::<Vec<String>>()
                                .join(",");
                        }
                        self.label_set_topics(&topics_raw);
                    }
                    "skip" => {
                        self.label_skip_current();
                    }
                    "done" => {
                        if let Some(session) = self.label_session.clone() {
                            if session.labels.is_empty() {
                                self.add_meta("No label entries captured. Use /label set first.");
                                return ScreenAction::None;
                            }
                            let entries = session
                                .labels
                                .iter()
                                .map(|entry| {
                                    serde_json::json!({
                                        "text": entry.text,
                                        "topics": entry.topics,
                                        "quality_score": 5.0,
                                        "difficulty_level": "medium",
                                    })
                                })
                                .collect::<Vec<serde_json::Value>>();
                            let output = session.output_path.clone();
                            let corpus_path = session.corpus_path.clone();

                            self.start_task(TaskKind::LabelPersist, {
                                let api = ctx.api_url.clone();
                                async move {
                                    let client = crate::api::client::ApiClient::new(&api);
                                    let payload = client
                                        .label_entries(
                                            &corpus_path,
                                            &output,
                                            &serde_json::json!(entries),
                                        )
                                        .await?;
                                    Ok(TaskPayload::Json(payload))
                                }
                            });
                        } else {
                            self.add_meta("Label session not active. Start with /label start.");
                        }
                    }
                    _ => {
                        self.add_meta("Usage: /label start [limit=20] [output_path=...] | /label set <topic1,topic2> | /label skip | /label done");
                    }
                }
                ScreenAction::None
            }
            ChatCommand::System(system) => {
                match system {
                    None => self.add_meta(format!(
                        "System prompt: {}",
                        self.config.system_prompt.as_deref().unwrap_or("(none)")
                    )),
                    Some(text) => {
                        self.config.system_prompt = Some(text);
                        self.add_meta("System prompt updated.");
                    }
                }
                ScreenAction::None
            }
            ChatCommand::Save(path) => {
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
                let Some(path) = path else {
                    self.add_meta("Usage: /load <path-to-session.json>");
                    return ScreenAction::None;
                };
                match load_session(&path) {
                    Ok(session) => {
                        self.config = session.config;
                        self.messages = session.messages;
                        self.scroll_to_bottom();
                        self.add_meta("Session loaded.");
                    }
                    Err(e) => self.add_meta(format!("Failed to load session: {}", e)),
                }
                ScreenAction::None
            }
            ChatCommand::Quit => {
                self.cancel_pending();
                ScreenAction::Pop
            }
            ChatCommand::Unknown(_, _) | ChatCommand::PlainPrompt(_) | ChatCommand::Empty => {
                ScreenAction::None
            }
            ChatCommand::Yes | ChatCommand::No => ScreenAction::None,
        }
    }

    fn confirm_pending(&mut self, ctx: &mut AppContext) -> ScreenAction {
        let Some(confirmation) = self.pending_confirmation.take() else {
            self.add_meta("No pending command to confirm.");
            return ScreenAction::None;
        };
        self.add_meta(format!("Confirmed: {}", confirmation.summary));
        self.execute_command(ctx, confirmation.command, true)
    }

    fn start_task<F>(&mut self, kind: TaskKind, fut: F)
    where
        F: Future<Output = anyhow::Result<TaskPayload>> + Send + 'static,
    {
        self.pending = Some(PendingOp::Task(TaskOp {
            kind,
            handle: tokio::spawn(fut),
        }));
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

    fn build_hypo_request(
        &self,
        args: &CommandArgs,
    ) -> std::result::Result<(GenerationRequest, Vec<String>), String> {
        let raw_topics = if let Some(raw) = args.get("topics") {
            raw.to_string()
        } else if !args.positionals.is_empty() {
            args.positionals.join(",")
        } else {
            return Err(
                "Usage: /hypo <topic1,topic2,...> [complexity=1-5|level] [parties=2-5] [method=hybrid|pure_llm] [analysis=true|false]"
                    .into(),
            );
        };
        let topics = parse_hypo_topics(&raw_topics)?;

        let state = TuiState::load();

        let complexity_level = if let Some(raw) = args.get("complexity") {
            self.map_complexity_text(raw)
        } else {
            self.map_complexity_text(&state.last_config.complexity)
        };

        let number_parties = if let Some(raw) = args.get("parties") {
            self.parse_u32(raw, "parties")?
        } else {
            state.last_config.parties.parse::<u32>().unwrap_or(2)
        };

        let method = args
            .get("method")
            .map(str::to_string)
            .unwrap_or(state.last_config.method);

        let include_analysis = if let Some(raw) = args.get("analysis") {
            self.parse_bool(raw).ok_or_else(|| {
                "Invalid analysis value. Use true/false (or yes/no, 1/0).".to_string()
            })?
        } else {
            state.last_config.include_analysis
        };

        let mut user_preferences = HashMap::new();
        user_preferences.insert(
            "temperature".into(),
            serde_json::json!(self.config.temperature),
        );

        let request = GenerationRequest {
            topics: topics.clone(),
            law_domain: "tort".into(),
            number_parties,
            complexity_level,
            sample_size: 3,
            user_preferences: Some(user_preferences),
            method,
            provider: Some(self.config.provider.clone()),
            model: self.config.model.clone(),
            include_analysis,
            correlation_id: None,
        };

        Ok((request, topics))
    }

    fn resolve_generation_ref(&self, raw: Option<&str>) -> std::result::Result<i64, String> {
        let token = raw.unwrap_or("last").trim().to_lowercase();
        if token.is_empty() || token == "last" || token == "current" || token == "me" {
            return self
                .runtime_ctx
                .last_generation_id
                .ok_or_else(|| "No previous generation in context.".to_string());
        }
        let id = token.parse::<i64>().map_err(|_| {
            format!(
                "Invalid generation reference '{}'. Use an integer or 'last'.",
                token
            )
        })?;
        if id <= 0 {
            return Err("Generation ID must be positive.".into());
        }
        Ok(id)
    }

    fn resolve_job_ref(&self, raw: Option<&str>) -> std::result::Result<String, String> {
        let token = raw.unwrap_or("last").trim();
        if token.is_empty()
            || token.eq_ignore_ascii_case("last")
            || token.eq_ignore_ascii_case("current")
        {
            return self
                .runtime_ctx
                .last_job_id
                .clone()
                .ok_or_else(|| "No previous job in context.".to_string());
        }
        Ok(token.to_string())
    }

    fn map_complexity_text(&self, value: &str) -> String {
        let normalized = value.trim().to_lowercase();
        match normalized.as_str() {
            "1" | "beginner" => "beginner".into(),
            "2" | "basic" => "basic".into(),
            "3" | "intermediate" => "intermediate".into(),
            "4" | "advanced" => "advanced".into(),
            "5" | "expert" => "expert".into(),
            _ => "intermediate".into(),
        }
    }

    fn parse_u32_option(
        &self,
        raw: Option<&str>,
        field: &str,
    ) -> std::result::Result<Option<u32>, String> {
        let Some(raw) = raw else {
            return Ok(None);
        };
        self.parse_u32(raw, field).map(Some)
    }

    fn parse_u32(&self, raw: &str, field: &str) -> std::result::Result<u32, String> {
        raw.parse::<u32>().map_err(|_| {
            format!(
                "Invalid {} value '{}'. Must be a positive integer.",
                field, raw
            )
        })
    }

    fn parse_bool_option(
        &self,
        raw: Option<&str>,
        field: &str,
    ) -> std::result::Result<Option<bool>, String> {
        let Some(raw) = raw else {
            return Ok(None);
        };
        self.parse_bool(raw)
            .map(Some)
            .ok_or_else(|| format!("Invalid {} value '{}'. Use true/false.", field, raw))
    }

    fn parse_bool(&self, raw: &str) -> Option<bool> {
        match raw.trim().to_lowercase().as_str() {
            "true" | "yes" | "y" | "1" | "on" => Some(true),
            "false" | "no" | "n" | "0" | "off" => Some(false),
            _ => None,
        }
    }

    fn label_set_topics(&mut self, raw_topics: &str) {
        let Some(session) = &mut self.label_session else {
            self.add_meta("Label session not active. Start with /label start.");
            return;
        };
        if !session.has_current() {
            self.add_meta(
                "No active entry. Use /label done to persist or /label start to restart.",
            );
            return;
        }

        let topics: Vec<String> = parse_csv(raw_topics)
            .into_iter()
            .map(|v| normalize_topic(&v))
            .collect();
        if topics.is_empty() {
            self.add_meta("Usage: /label set <topic1,topic2>");
            return;
        }

        if let Some(entry) = session.current_entry() {
            session.labels.push(LabelDraftEntry {
                text: entry.text.clone(),
                topics,
            });
        }
        session.current_idx += 1;
        self.show_label_progress();
    }

    fn label_skip_current(&mut self) {
        let Some(session) = &mut self.label_session else {
            self.add_meta("Label session not active. Start with /label start.");
            return;
        };
        if !session.has_current() {
            self.add_meta(
                "No active entry. Use /label done to persist or /label start to restart.",
            );
            return;
        }
        session.current_idx += 1;
        self.show_label_progress();
    }

    fn show_label_progress(&mut self) {
        let Some(session) = &self.label_session else {
            return;
        };
        if let Some(entry) = session.current_entry() {
            let snippet = Self::clip_text(&entry.text, 320);
            self.add_meta(format!(
                "Label entry {}/{} (captured: {}). Topics hint: {}\n{}\nCommands: /label set <topic1,topic2> | /label skip | /label done",
                session.current_idx + 1,
                session.entries.len(),
                session.labels.len(),
                if entry.topics.is_empty() {
                    "(none)".into()
                } else {
                    entry.topics.join(", ")
                },
                snippet,
            ));
            self.emit_suggestions("label");
        } else {
            self.add_meta(format!(
                "Label queue complete. Captured {} entries. Run /label done to persist or /label start to restart.",
                session.labels.len()
            ));
            self.emit_suggestions("label_done_pending");
        }
    }

    fn handle_guided_action(&mut self, action: &str) {
        const STEPS: [&str; 4] = [
            "Step 1: Check corpus readiness with /corpus limit=20 or /topics.",
            "Step 2: If corpus is stale, run /preprocess (and optionally /scrape).",
            "Step 3: Generate with /hypo negligence,causation (adjust complexity/parties as needed).",
            "Step 4: Export with /export generation_id=last format=docx (or pdf).",
        ];

        match action {
            "start" => {
                self.guided_step = Some(0);
                self.add_meta(STEPS[0]);
                self.emit_suggestions("guided");
            }
            "next" => {
                let next = self.guided_step.unwrap_or(0) + 1;
                if next >= STEPS.len() {
                    self.guided_step = Some(STEPS.len() - 1);
                    self.add_meta("Guided flow complete. Use /guided stop to exit guidance.");
                    self.emit_suggestions("guided_complete");
                } else {
                    self.guided_step = Some(next);
                    self.add_meta(STEPS[next]);
                    self.emit_suggestions("guided");
                }
            }
            "stop" => {
                self.guided_step = None;
                self.add_meta("Guided flow stopped.");
            }
            _ => self.add_meta("Usage: /guided start | /guided next | /guided stop"),
        }
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
                        self.add_meta(Self::format_stream_error(&code, &message));
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
            self.emit_suggestions("chat_response");
        }
    }

    fn maybe_resolve_pending_task(&mut self) {
        let finished = matches!(
            self.pending.as_ref(),
            Some(PendingOp::Task(task)) if task.handle.is_finished()
        );
        if !finished {
            return;
        }

        let Some(PendingOp::Task(task)) = self.pending.take() else {
            return;
        };

        let kind = task.kind;
        match tokio::runtime::Handle::current().block_on(task.handle) {
            Ok(Ok(payload)) => self.resolve_task_success(kind, payload),
            Ok(Err(e)) => {
                self.add_meta(format!("Command failed: {}", Self::format_anyhow(&e)));
                self.emit_suggestions("error");
            }
            Err(e) => {
                self.add_meta(format!("Command task failed: {}", e));
                self.emit_suggestions("error");
            }
        }
    }

    fn resolve_task_success(&mut self, kind: TaskKind, payload: TaskPayload) {
        match (kind, payload) {
            (TaskKind::Tokens, TaskPayload::Json(payload)) => {
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
                self.emit_suggestions("tokens");
            }
            (TaskKind::Hypo, TaskPayload::Generation(response)) => {
                let mut content = format!("Hypothetical:\n\n{}", response.hypothetical);
                if !response.analysis.trim().is_empty() {
                    content.push_str("\n\nAnalysis:\n\n");
                    content.push_str(response.analysis.trim());
                }
                self.add_message(ChatRole::Assistant, content);

                if let Some(id) = response
                    .metadata
                    .get("generation_id")
                    .and_then(|v| v.as_i64())
                {
                    self.runtime_ctx.last_generation_id = Some(id);
                }
                self.runtime_ctx.last_hypothetical = Some(response.hypothetical.clone());
                if let Some(topics) = response.metadata.get("topics").and_then(|v| v.as_array()) {
                    self.runtime_ctx.last_topics = topics
                        .iter()
                        .filter_map(|v| v.as_str().map(str::to_string))
                        .collect();
                }
                self.emit_suggestions("generation");
            }
            (TaskKind::Regenerate, TaskPayload::Regeneration(response)) => {
                let mut content = format!(
                    "Regenerated (source generation {}):\n\n{}",
                    response.source_generation_id, response.regenerated.hypothetical
                );
                if !response.regenerated.analysis.trim().is_empty() {
                    content.push_str("\n\nAnalysis:\n\n");
                    content.push_str(response.regenerated.analysis.trim());
                }
                if !response.feedback_context.trim().is_empty() {
                    content.push_str("\n\nFeedback context used:\n");
                    content.push_str(response.feedback_context.trim());
                }
                self.add_message(ChatRole::Assistant, content);
                if let Some(id) = response
                    .regenerated
                    .metadata
                    .get("generation_id")
                    .and_then(|v| v.as_i64())
                {
                    self.runtime_ctx.last_generation_id = Some(id);
                }
                self.runtime_ctx.last_hypothetical =
                    Some(response.regenerated.hypothetical.clone());
                self.emit_suggestions("generation");
            }
            (TaskKind::Report, TaskPayload::Message(message)) => {
                self.add_meta(message);
                self.emit_suggestions("report");
            }
            (TaskKind::Reports, TaskPayload::Reports(reports)) => {
                if reports.is_empty() {
                    self.add_meta("No reports found for this generation.");
                } else {
                    let mut lines = vec![format!("Reports: {}", reports.len())];
                    for report in reports.iter().take(10) {
                        lines.push(format!(
                            "- #{} issues=[{}] comment={} at={}",
                            report.id.unwrap_or_default(),
                            report.issue_types.join(","),
                            report.comment.as_deref().unwrap_or("-"),
                            report.created_at.as_deref().unwrap_or("-")
                        ));
                    }
                    self.add_meta(lines.join("\n"));
                }
                self.emit_suggestions("report");
            }
            (TaskKind::Generation, TaskPayload::Json(payload)) => {
                if payload.get("error").and_then(|v| v.as_str()) == Some("not_found") {
                    self.add_meta("Generation not found.");
                    self.emit_suggestions("error");
                    return;
                }
                if let Some(id) = payload.get("id").and_then(|v| v.as_i64()) {
                    self.runtime_ctx.last_generation_id = Some(id);
                }
                let hypothetical = payload
                    .get("response")
                    .and_then(|r| r.get("hypothetical"))
                    .and_then(|v| v.as_str())
                    .map(str::to_string)
                    .or_else(|| {
                        payload
                            .get("hypothetical")
                            .and_then(|v| v.as_str())
                            .map(str::to_string)
                    });
                if let Some(h) = hypothetical {
                    self.runtime_ctx.last_hypothetical = Some(h);
                }
                self.add_message(
                    ChatRole::Assistant,
                    format!("Generation detail:\n{}", Self::pretty_json(&payload)),
                );
                self.emit_suggestions("generation");
            }
            (TaskKind::Topics, TaskPayload::Topics(mut topics)) => {
                topics.sort();
                self.add_meta(format!("Topics ({}): {}", topics.len(), topics.join(", ")));
                self.emit_suggestions("topics");
            }
            (TaskKind::Corpus, TaskPayload::CorpusEntries(entries)) => {
                if entries.is_empty() {
                    self.add_meta("No corpus entries found.");
                } else {
                    let mut lines = vec![format!("Corpus entries: {}", entries.len())];
                    for (idx, entry) in entries.iter().take(8).enumerate() {
                        lines.push(format!(
                            "{}. [{}] {}",
                            idx + 1,
                            if entry.topics.is_empty() {
                                "-".into()
                            } else {
                                entry.topics.join(",")
                            },
                            Self::clip_text(&entry.text, 120)
                        ));
                    }
                    self.add_meta(lines.join("\n"));
                }
                self.emit_suggestions("corpus");
            }
            (TaskKind::Query, TaskPayload::CorpusQuery(response)) => {
                if response.entries.is_empty() {
                    self.add_meta("Corpus query returned 0 entries.");
                } else {
                    let mut lines =
                        vec![format!("Corpus query matched {} entries", response.count)];
                    for (idx, entry) in response.entries.iter().take(8).enumerate() {
                        lines.push(format!(
                            "{}. [{}] {}",
                            idx + 1,
                            if entry.topics.is_empty() {
                                "-".into()
                            } else {
                                entry.topics.join(",")
                            },
                            Self::clip_text(&entry.text, 120)
                        ));
                    }
                    self.add_meta(lines.join("\n"));
                }
                self.emit_suggestions("query");
            }
            (TaskKind::Validate, TaskPayload::Json(payload)) => {
                self.add_meta(format!("Validation:\n{}", Self::pretty_json(&payload)));
                self.emit_suggestions("validate");
            }
            (
                TaskKind::Preprocess
                | TaskKind::Scrape
                | TaskKind::Train
                | TaskKind::Embed
                | TaskKind::Export,
                TaskPayload::JobId(job_id),
            ) => {
                self.runtime_ctx.last_job_id = Some(job_id.clone());
                self.add_meta(format!("Job started: {}", job_id));
                self.emit_suggestions("job_started");
            }
            (TaskKind::Cleanup, TaskPayload::Json(payload)) => {
                let removed = payload
                    .get("removed")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|v| v.as_str())
                            .collect::<Vec<&str>>()
                            .join(", ")
                    })
                    .unwrap_or_else(|| "(none)".into());
                self.add_meta(format!("Cleanup complete. Removed: {}", removed));
                self.emit_suggestions("cleanup");
            }
            (TaskKind::JobStatus, TaskPayload::JobStatus(status)) => {
                self.add_meta(format!(
                    "Job status: type={} status={} progress={} error={}",
                    status.job_type,
                    status.status,
                    status.progress,
                    status.error.as_deref().unwrap_or("-")
                ));

                if let Some(result) = &status.result {
                    if let Some(path) = result.get("output_path").and_then(|v| v.as_str()) {
                        self.runtime_ctx.last_export_path = Some(path.to_string());
                    }
                    self.add_meta(format!("Job result: {}", Self::pretty_json(result)));
                }
                self.emit_suggestions("job_status");
            }
            (TaskKind::JobCancel, TaskPayload::Json(payload)) => {
                let cancelled = payload
                    .get("cancelled")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                if cancelled {
                    self.add_meta("Job cancelled.");
                } else {
                    self.add_meta(format!("Cancel response: {}", Self::pretty_json(&payload)));
                }
                self.emit_suggestions("job_status");
            }
            (TaskKind::History, TaskPayload::History(records)) => {
                if records.is_empty() {
                    self.add_meta("No generation history available.");
                } else {
                    let mut lines = vec![format!("History records: {}", records.len())];
                    for record in records.iter().take(12) {
                        lines.push(format!(
                            "- #{} topics={} quality={:.2} at={} ",
                            record.id, record.topics, record.quality_score, record.timestamp
                        ));
                    }
                    self.add_meta(lines.join("\n"));
                }
                self.emit_suggestions("history");
            }
            (TaskKind::Stats, TaskPayload::Json(payload)) => {
                self.add_meta(format!("Statistics:\n{}", Self::pretty_json(&payload)));
                self.emit_suggestions("stats");
            }
            (TaskKind::Providers, TaskPayload::Json(payload)) => {
                self.add_meta(format!("Providers:\n{}", Self::pretty_json(&payload)));
                self.emit_suggestions("providers");
            }
            (TaskKind::Models, TaskPayload::Json(payload)) => {
                self.add_meta(format!("Models:\n{}", Self::pretty_json(&payload)));
                self.emit_suggestions("models");
            }
            (
                TaskKind::LabelLoad {
                    output_path,
                    corpus_path,
                },
                TaskPayload::CorpusEntries(entries),
            ) => {
                if entries.is_empty() {
                    self.add_meta("No corpus entries available for labeling.");
                    self.emit_suggestions("error");
                } else {
                    self.label_session = Some(LabelSession {
                        entries,
                        labels: Vec::new(),
                        current_idx: 0,
                        output_path,
                        corpus_path,
                    });
                    self.add_meta("Label session started.");
                    self.show_label_progress();
                }
            }
            (TaskKind::LabelPersist, TaskPayload::Json(payload)) => {
                let count = payload
                    .get("labelled_count")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                let output_path = payload
                    .get("output_path")
                    .and_then(|v| v.as_str())
                    .unwrap_or(DEFAULT_LABEL_OUTPUT_PATH);
                self.add_meta(format!(
                    "Label persistence complete. labelled_count={} output_path={}",
                    count, output_path
                ));
                self.label_session = None;
                self.emit_suggestions("label_saved");
            }
            (_, TaskPayload::Message(message)) => {
                self.add_meta(message);
                self.emit_suggestions("default");
            }
            (kind, payload) => {
                self.add_meta(format!(
                    "Unexpected response for task {:?}: {}",
                    kind,
                    Self::task_payload_type(&payload)
                ));
                self.emit_suggestions("error");
            }
        }
    }

    fn unknown_command_suggestions(&self, name: &str) -> Vec<String> {
        let known = [
            "help",
            "clear",
            "menu",
            "provider",
            "model",
            "temp",
            "tokens",
            "hypo",
            "regenerate",
            "report",
            "reports",
            "generation",
            "topics",
            "corpus",
            "query",
            "validate",
            "preprocess",
            "scrape",
            "train",
            "embed",
            "export",
            "cleanup",
            "job",
            "history",
            "stats",
            "providers",
            "models",
            "settings",
            "guided",
            "label",
            "system",
            "save",
            "load",
            "quit",
        ];

        let mut matches = known
            .iter()
            .filter(|candidate| candidate.starts_with(name) || candidate.contains(name))
            .take(4)
            .map(|candidate| format!("/{}", candidate))
            .collect::<Vec<String>>();
        if matches.is_empty() {
            matches.push("/help".into());
            matches.push("/topics".into());
            matches.push("/hypo negligence,causation".into());
        }
        matches
    }

    fn autocomplete_hint(&self) -> Option<String> {
        let trimmed = self.input.trim_start();
        if !trimmed.starts_with('/') {
            return None;
        }

        let raw = &trimmed[1..];
        if raw.is_empty() {
            return Some("Autocomplete: /help  /hypo  /topics  /history".into());
        }

        let mut split = raw.splitn(2, char::is_whitespace);
        let cmd = split.next().unwrap_or_default().to_lowercase();
        let has_args = split.next().is_some();

        if has_args {
            return Self::command_usage_hint(&cmd).map(|usage| format!("Usage: {}", usage));
        }

        let matches: Vec<&str> = Self::command_catalog()
            .iter()
            .copied()
            .filter(|candidate| candidate.starts_with(&cmd))
            .take(4)
            .collect();

        if matches.is_empty() {
            return Some("Autocomplete: /help  /topics  /hypo".into());
        }

        if matches.len() == 1 && matches[0] == cmd {
            if let Some(usage) = Self::command_usage_hint(&cmd) {
                return Some(format!("Usage: {}", usage));
            }
        }

        Some(format!(
            "Autocomplete: {}",
            matches
                .iter()
                .map(|name| format!("/{}", name))
                .collect::<Vec<String>>()
                .join("  ")
        ))
    }

    fn command_catalog() -> &'static [&'static str] {
        &[
            "help",
            "clear",
            "menu",
            "yes",
            "no",
            "provider",
            "model",
            "temp",
            "tokens",
            "hypo",
            "regenerate",
            "report",
            "reports",
            "generation",
            "topics",
            "corpus",
            "query",
            "validate",
            "preprocess",
            "scrape",
            "train",
            "embed",
            "export",
            "cleanup",
            "job",
            "history",
            "stats",
            "providers",
            "models",
            "settings",
            "guided",
            "label",
            "system",
            "save",
            "load",
            "quit",
        ]
    }

    fn command_usage_hint(command: &str) -> Option<&'static str> {
        match command {
            "help" => Some("/help"),
            "menu" => Some("/menu"),
            "provider" => Some("/provider [ollama|openai|anthropic|google|local]"),
            "model" => Some("/model [name]"),
            "temp" => Some("/temp <0.0-2.0>"),
            "hypo" => Some("/hypo <topic1,topic2,...> [complexity=] [parties=] [method=]"),
            "regenerate" => Some("/regenerate <generation_id|last>"),
            "report" => Some("/report <generation_id|last> issue=<csv> [comment=\"...\"]"),
            "reports" => Some("/reports <generation_id|last>"),
            "generation" => Some("/generation <generation_id|last>"),
            "topics" => Some("/topics"),
            "corpus" => Some("/corpus [topic=<topic>] [limit=<n>]"),
            "query" => Some("/query topics=<csv> [sample=<n>] [overlap=<n>]"),
            "validate" => Some("/validate required=<csv> [parties=<n>] [text=\"...\"]"),
            "preprocess" => Some("/preprocess [raw_dir=] [output_path=] [merge=true|false]"),
            "scrape" => Some("/scrape source=<commonlii|judiciary|sicc|gazette>"),
            "train" => Some("/train [data_path=] [n_clusters=]"),
            "embed" => Some("/embed [corpus_path=] [batch_size=]"),
            "export" => Some("/export [format=docx|pdf] [generation_id=<id|last>]"),
            "cleanup" => Some("/cleanup targets=<csv>"),
            "job" => Some("/job status <job_id|last> | /job cancel <job_id|last>"),
            "history" => Some("/history [limit=<n>]"),
            "stats" => Some("/stats"),
            "providers" => Some("/providers"),
            "models" => Some("/models [provider=<name>]"),
            "settings" => Some("/settings view | /settings reset"),
            "guided" => Some("/guided start | /guided next | /guided stop"),
            "label" => Some("/label start | /label set <topics> | /label skip | /label done"),
            "system" => Some("/system [text]"),
            "save" => Some("/save [path]"),
            "load" => Some("/load <path>"),
            "quit" => Some("/quit"),
            _ => None,
        }
    }

    fn command_name(&self, command: &ChatCommand) -> String {
        command_meta(command)
            .map(|m| m.name.to_string())
            .unwrap_or_else(|| "command".into())
    }

    fn command_summary(&self, command: &ChatCommand) -> String {
        match command {
            ChatCommand::Hypo(args) => format!("/hypo {}", args.positionals.join(" ")),
            ChatCommand::Regenerate(args) => {
                format!("/regenerate {}", args.first().unwrap_or("last"))
            }
            ChatCommand::Report(args) => {
                format!("/report {}", args.positionals.join(" "))
            }
            ChatCommand::Preprocess(_) => "/preprocess".into(),
            ChatCommand::Scrape(args) => format!("/scrape {}", args.positional_joined()),
            ChatCommand::Train(args) => format!("/train {}", args.positional_joined()),
            ChatCommand::Embed(args) => format!("/embed {}", args.positional_joined()),
            ChatCommand::Export(args) => format!("/export {}", args.positional_joined()),
            ChatCommand::Cleanup(args) => format!("/cleanup {}", args.positional_joined()),
            ChatCommand::Job(args) => format!("/job {}", args.positional_joined()),
            ChatCommand::Settings(args) => format!("/settings {}", args.positional_joined()),
            ChatCommand::Label(args) => format!("/label {}", args.positional_joined()),
            other => format!("/{}", self.command_name(other)),
        }
    }

    fn emit_suggestions(&mut self, key: &str) {
        let suggestions = match key {
            "topics" => vec![
                "/hypo negligence,causation",
                "/query topics=negligence sample=3",
                "/corpus limit=20",
            ],
            "generation" => vec![
                "/report last issue=topic_mismatch comment=\"needs better coverage\"",
                "/regenerate last",
                "/export generation_id=last format=docx",
                "/history limit=20",
            ],
            "job_started" => vec!["/job status last", "/job cancel last", "/history limit=20"],
            "job_status" => vec!["/job status last", "/history limit=20", "/stats"],
            "history" => vec!["/generation last", "/regenerate last", "/stats"],
            "label" => vec!["/label set negligence", "/label skip", "/label done"],
            "label_done_pending" => vec!["/label done", "/label start", "/topics"],
            "label_saved" => vec!["/train", "/embed", "/history limit=20"],
            "providers" => vec!["/models", "/provider ollama", "/hypo negligence,causation"],
            "corpus" => vec![
                "/query topics=negligence sample=3",
                "/topics",
                "/hypo negligence,causation",
            ],
            "query" => vec!["/hypo negligence,causation", "/corpus limit=20", "/topics"],
            "report" => vec!["/regenerate last", "/reports last", "/history limit=20"],
            "guided" => vec!["/guided next", "/guided stop", "/help"],
            "guided_complete" => vec![
                "/hypo negligence,causation",
                "/export generation_id=last format=docx",
                "/guided stop",
            ],
            "cleanup" => vec!["/history limit=20", "/topics", "/help"],
            "chat_response" => vec!["/hypo negligence,causation", "/topics", "/history limit=20"],
            "tokens" => vec!["/provider ollama", "/model", "/hypo negligence,causation"],
            "stats" => vec!["/history limit=20", "/providers", "/topics"],
            "validate" => vec![
                "/report last issue=topic_mismatch",
                "/regenerate last",
                "/hypo negligence,causation",
            ],
            "models" => vec![
                "/provider ollama",
                "/model llama2:7b",
                "/hypo negligence,causation",
            ],
            "error" | "default" | _ => vec!["/help", "/topics", "/history limit=20"],
        };
        if !suggestions.is_empty() {
            self.add_meta(Self::format_next_actions(&suggestions));
        }
    }

    fn format_next_actions(suggestions: &[&str]) -> String {
        let mut lines = Vec::with_capacity(suggestions.len() + 1);
        lines.push("Next actions:".to_string());
        for suggestion in suggestions.iter().take(4) {
            lines.push(format!("- {}", suggestion));
        }
        lines.join("\n")
    }

    fn format_stream_error(code: &str, message: &str) -> String {
        let lower = message.to_lowercase();
        if lower.contains("all connection attempts failed")
            || (lower.contains("ollama") && lower.contains("connection"))
        {
            return format!(
                "Stream error [{}]: cannot reach Ollama. Start `ollama serve`, then retry or switch provider with /provider.",
                code
            );
        }
        if message.chars().count() > 220 {
            return format!(
                "Stream error [{}]: {}",
                code,
                Self::clip_text(message, 220)
            );
        }
        format!("Stream error [{}]: {}", code, message)
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

    fn clip_text(input: &str, max: usize) -> String {
        let compact = input.replace('\n', " ").replace('\r', " ");
        if compact.chars().count() <= max {
            compact
        } else {
            let clipped = compact.chars().take(max).collect::<String>();
            format!("{}...", clipped)
        }
    }

    fn pretty_json(value: &serde_json::Value) -> String {
        serde_json::to_string_pretty(value).unwrap_or_else(|_| value.to_string())
    }

    fn format_anyhow(err: &anyhow::Error) -> String {
        let mut message = err.to_string();
        if let Some(pos) = message.find("\n") {
            message = message[..pos].to_string();
        }
        message
    }

    fn task_payload_type(payload: &TaskPayload) -> &'static str {
        match payload {
            TaskPayload::Json(_) => "json",
            TaskPayload::Generation(_) => "generation",
            TaskPayload::Regeneration(_) => "regeneration",
            TaskPayload::Reports(_) => "reports",
            TaskPayload::Topics(_) => "topics",
            TaskPayload::CorpusEntries(_) => "corpus_entries",
            TaskPayload::CorpusQuery(_) => "corpus_query",
            TaskPayload::History(_) => "history",
            TaskPayload::JobId(_) => "job_id",
            TaskPayload::JobStatus(_) => "job_status",
            TaskPayload::Message(_) => "message",
        }
    }

    fn valid_provider(value: &str) -> bool {
        matches!(
            value,
            "ollama" | "openai" | "anthropic" | "google" | "local"
        )
    }

    fn help_text() -> &'static str {
        "Commands:
/core
/help
/clear
/menu
/yes | /no
/save [path]
/load <path>
/quit

/llm
/provider [name]
/model [name]
/temp [value 0.0-2.0]
/tokens
/system [text]
/models [provider=<name>]
/providers

/generation
/hypo <topic1,topic2,...> [complexity=1-5|level] [parties=<n>] [method=<name>] [analysis=true|false]
/regenerate <generation_id|last>
/report <generation_id|last> issue=<csv> [comment=\"...\"]
/reports <generation_id|last>
/generation <generation_id|last>

/corpus
/topics
/corpus [topic=<topic>] [limit=<n>]
/query topics=<csv> [sample=<n>] [overlap=<n>]
/validate required=<csv> [parties=<n>] [text=\"...\"]

/jobs
/preprocess [raw_dir=<path>] [output_path=<path>] [merge=true|false] [include_non_tort=true|false]
/scrape source=<commonlii|judiciary|sicc|gazette> [max_cases=<n>] [courts=<csv>] [years=<csv>] [tort_only=true|false]
/train [data_path=<path>] [n_clusters=<n>]
/embed [corpus_path=<path>] [batch_size=<n>]
/export [format=docx|pdf] [generation_id=<id|last>] [output_path=<path>]
/cleanup targets=<csv>
/job status <job_id|last>
/job cancel <job_id|last>

/insights
/history [limit=<n>]
/stats
/settings view
/settings reset

/guided
/guided start
/guided next
/guided stop

/label
/label start [limit=<n>] [output_path=<path>]
/label set <topic1,topic2>
/label skip
/label done"
    }

    fn cancel_pending(&mut self) {
        if let Some(pending) = self.pending.take() {
            match pending {
                PendingOp::Streaming(stream) => {
                    stream.handle.abort();
                }
                PendingOp::Task(task) => {
                    task.handle.abort();
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
            INPUT_HINT_BUSY.to_string()
        } else if let Some(autocomplete) = self.autocomplete_hint() {
            autocomplete
        } else {
            INPUT_HINT_IDLE.to_string()
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
        self.maybe_resolve_pending_task();
    }
}
