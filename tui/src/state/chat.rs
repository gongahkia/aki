use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub const CHAT_SESSION_VERSION: u32 = 1;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ChatRole {
    User,
    Assistant,
    Meta,
}

impl ChatRole {
    pub fn prefix(&self) -> &'static str {
        match self {
            ChatRole::User => "you>",
            ChatRole::Assistant => "jikai>",
            ChatRole::Meta => "[meta]",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChatMessage {
    pub role: ChatRole,
    pub content: String,
}

impl ChatMessage {
    pub fn new(role: ChatRole, content: impl Into<String>) -> Self {
        Self {
            role,
            content: content.into(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatConfig {
    pub provider: String,
    pub model: Option<String>,
    pub temperature: f64,
    pub max_tokens: u32,
    pub system_prompt: Option<String>,
    pub context_turn_limit: usize,
}

impl Default for ChatConfig {
    fn default() -> Self {
        Self {
            provider: "ollama".into(),
            model: None,
            temperature: 0.7,
            max_tokens: 2048,
            system_prompt: Some(default_system_prompt()),
            context_turn_limit: 12,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SavedChatSessionV1 {
    pub version: u32,
    pub saved_at_unix: u64,
    pub config: ChatConfig,
    pub messages: Vec<ChatMessage>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct CommandArgs {
    pub positionals: Vec<String>,
    pub named: HashMap<String, String>,
}

impl CommandArgs {
    pub fn get(&self, key: &str) -> Option<&str> {
        self.named
            .get(&key.to_lowercase())
            .map(String::as_str)
            .or_else(|| {
                self.named
                    .get(&key.replace('_', "-").to_lowercase())
                    .map(String::as_str)
            })
    }

    pub fn first(&self) -> Option<&str> {
        self.positionals.first().map(String::as_str)
    }

    pub fn positional_joined(&self) -> String {
        self.positionals.join(" ")
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CommandMeta {
    pub name: &'static str,
    pub read_only: bool,
    pub requires_confirmation: bool,
    pub supports_suggestions: bool,
    pub help_text: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ChatCommand {
    Help,
    Clear,
    Menu,
    Yes,
    No,
    Provider(Option<String>),
    Model(Option<String>),
    Temp(Option<String>),
    Tokens,
    Hypo(CommandArgs),
    Regenerate(CommandArgs),
    Report(CommandArgs),
    Reports(CommandArgs),
    Generation(CommandArgs),
    Topics,
    Corpus(CommandArgs),
    Query(CommandArgs),
    Validate(CommandArgs),
    Preprocess(CommandArgs),
    Scrape(CommandArgs),
    Train(CommandArgs),
    Embed(CommandArgs),
    Export(CommandArgs),
    Cleanup(CommandArgs),
    Job(CommandArgs),
    History(CommandArgs),
    Stats,
    Providers,
    Models(CommandArgs),
    Settings(CommandArgs),
    Guided(CommandArgs),
    Label(CommandArgs),
    System(Option<String>),
    Save(Option<String>),
    Load(Option<String>),
    Quit,
    Unknown(String, CommandArgs),
    PlainPrompt(String),
    Empty,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ChatIntent {
    Command(ChatCommand),
    Ambiguous(Vec<String>),
    None,
}

pub fn default_system_prompt() -> String {
    "You are Jikai, a legal education assistant for Singapore Tort Law. \
You provide educational explanations and do not provide legal advice."
        .to_string()
}

pub fn parse_chat_command(input: &str) -> ChatCommand {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return ChatCommand::Empty;
    }

    if !trimmed.starts_with('/') {
        return ChatCommand::PlainPrompt(trimmed.to_string());
    }

    let raw = &trimmed[1..];
    let mut split = raw.splitn(2, char::is_whitespace);
    let command = split.next().unwrap_or_default().to_lowercase();
    let args = split.next().map(str::trim).unwrap_or_default();
    let args_opt = if args.is_empty() {
        None
    } else {
        Some(args.to_string())
    };
    let parsed_args = parse_command_args(args);

    match command.as_str() {
        "help" => ChatCommand::Help,
        "clear" => ChatCommand::Clear,
        "menu" => ChatCommand::Menu,
        "yes" => ChatCommand::Yes,
        "no" => ChatCommand::No,
        "provider" => ChatCommand::Provider(args_opt),
        "model" => ChatCommand::Model(args_opt),
        "temp" => ChatCommand::Temp(args_opt),
        "tokens" => ChatCommand::Tokens,
        "hypo" => ChatCommand::Hypo(parsed_args),
        "regenerate" => ChatCommand::Regenerate(parsed_args),
        "report" => ChatCommand::Report(parsed_args),
        "reports" => ChatCommand::Reports(parsed_args),
        "generation" => ChatCommand::Generation(parsed_args),
        "topics" => ChatCommand::Topics,
        "corpus" => ChatCommand::Corpus(parsed_args),
        "query" => ChatCommand::Query(parsed_args),
        "validate" => ChatCommand::Validate(parsed_args),
        "preprocess" => ChatCommand::Preprocess(parsed_args),
        "scrape" => ChatCommand::Scrape(parsed_args),
        "train" => ChatCommand::Train(parsed_args),
        "embed" => ChatCommand::Embed(parsed_args),
        "export" => ChatCommand::Export(parsed_args),
        "cleanup" => ChatCommand::Cleanup(parsed_args),
        "job" => ChatCommand::Job(parsed_args),
        "history" => ChatCommand::History(parsed_args),
        "stats" => ChatCommand::Stats,
        "providers" => ChatCommand::Providers,
        "models" => ChatCommand::Models(parsed_args),
        "settings" => ChatCommand::Settings(parsed_args),
        "guided" => ChatCommand::Guided(parsed_args),
        "label" => ChatCommand::Label(parsed_args),
        "system" => ChatCommand::System(args_opt),
        "save" => ChatCommand::Save(args_opt),
        "load" => ChatCommand::Load(args_opt),
        "quit" => ChatCommand::Quit,
        _ => ChatCommand::Unknown(command, parsed_args),
    }
}

pub fn infer_chat_intent(input: &str) -> ChatIntent {
    let trimmed = input.trim();
    if trimmed.is_empty() || trimmed.starts_with('/') {
        return ChatIntent::None;
    }

    let lower = trimmed.to_lowercase();

    if lower.contains("help") {
        return ChatIntent::Command(ChatCommand::Help);
    }
    if lower.contains("list topics") || lower.contains("show topics") {
        return ChatIntent::Command(ChatCommand::Topics);
    }
    if lower.contains("show history") || lower.contains("list history") {
        return ChatIntent::Command(ChatCommand::History(CommandArgs::default()));
    }
    if lower.contains("show stats") || lower.contains("statistics") {
        return ChatIntent::Command(ChatCommand::Stats);
    }
    if lower.contains("providers") || lower.contains("provider health") {
        return ChatIntent::Command(ChatCommand::Providers);
    }
    if lower.contains("preprocess") {
        return ChatIntent::Command(ChatCommand::Preprocess(CommandArgs::default()));
    }
    if lower.contains("train") && lower.contains("model") {
        return ChatIntent::Command(ChatCommand::Train(CommandArgs::default()));
    }
    if lower.contains("embed") || lower.contains("index corpus") {
        return ChatIntent::Command(ChatCommand::Embed(CommandArgs::default()));
    }
    if lower.contains("export") {
        let mut args = CommandArgs::default();
        if lower.contains("pdf") {
            args.named.insert("format".into(), "pdf".into());
        } else if lower.contains("docx") || lower.contains("word") {
            args.named.insert("format".into(), "docx".into());
        }
        return ChatIntent::Command(ChatCommand::Export(args));
    }
    if lower.contains("scrape") {
        let mut args = CommandArgs::default();
        for src in ["commonlii", "judiciary", "sicc", "gazette"] {
            if lower.contains(src) {
                args.named.insert("source".into(), src.into());
                return ChatIntent::Command(ChatCommand::Scrape(args));
            }
        }
        return ChatIntent::Ambiguous(vec![
            "/scrape source=commonlii".into(),
            "/scrape source=judiciary".into(),
            "/scrape source=sicc".into(),
        ]);
    }
    if lower.contains("generate") && lower.contains("hypo") {
        if let Some((_, rhs)) = lower.split_once("about") {
            let mut args = CommandArgs::default();
            args.positionals.push(rhs.trim().to_string());
            return ChatIntent::Command(ChatCommand::Hypo(args));
        }
        return ChatIntent::Ambiguous(vec![
            "/hypo negligence,causation".into(),
            "/topics".into(),
            "/query topics=negligence sample=3".into(),
        ]);
    }

    ChatIntent::None
}

pub fn command_meta(command: &ChatCommand) -> Option<CommandMeta> {
    let meta = match command {
        ChatCommand::Help => CommandMeta {
            name: "help",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Show command help",
        },
        ChatCommand::Clear => CommandMeta {
            name: "clear",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Clear transcript",
        },
        ChatCommand::Menu => CommandMeta {
            name: "menu",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Open legacy menu",
        },
        ChatCommand::Provider(_) => CommandMeta {
            name: "provider",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Show or set provider",
        },
        ChatCommand::Model(_) => CommandMeta {
            name: "model",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Show or set model",
        },
        ChatCommand::Temp(_) => CommandMeta {
            name: "temp",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Show or set temperature",
        },
        ChatCommand::Tokens => CommandMeta {
            name: "tokens",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "Show session cost and token totals",
        },
        ChatCommand::Hypo(_) => CommandMeta {
            name: "hypo",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Generate a hypothetical",
        },
        ChatCommand::Regenerate(_) => CommandMeta {
            name: "regenerate",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Regenerate from a generation id",
        },
        ChatCommand::Report(_) => CommandMeta {
            name: "report",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Submit issue report for generation",
        },
        ChatCommand::Reports(_) => CommandMeta {
            name: "reports",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "List reports for generation",
        },
        ChatCommand::Generation(_) => CommandMeta {
            name: "generation",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "Show generation details",
        },
        ChatCommand::Topics => CommandMeta {
            name: "topics",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "List corpus topics",
        },
        ChatCommand::Corpus(_) => CommandMeta {
            name: "corpus",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "List corpus entries",
        },
        ChatCommand::Query(_) => CommandMeta {
            name: "query",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "Query corpus by topics",
        },
        ChatCommand::Validate(_) => CommandMeta {
            name: "validate",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "Validate text against topics",
        },
        ChatCommand::Preprocess(_) => CommandMeta {
            name: "preprocess",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Preprocess raw corpus",
        },
        ChatCommand::Scrape(_) => CommandMeta {
            name: "scrape",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Run scrape job",
        },
        ChatCommand::Train(_) => CommandMeta {
            name: "train",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Train ML models",
        },
        ChatCommand::Embed(_) => CommandMeta {
            name: "embed",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Index embeddings",
        },
        ChatCommand::Export(_) => CommandMeta {
            name: "export",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Export generation",
        },
        ChatCommand::Cleanup(_) => CommandMeta {
            name: "cleanup",
            read_only: false,
            requires_confirmation: true,
            supports_suggestions: true,
            help_text: "Cleanup data targets",
        },
        ChatCommand::Job(args) => {
            let read_only = !args
                .first()
                .map(|v| v.eq_ignore_ascii_case("cancel"))
                .unwrap_or(false);
            CommandMeta {
                name: "job",
                read_only,
                requires_confirmation: !read_only,
                supports_suggestions: true,
                help_text: "Check or cancel job",
            }
        }
        ChatCommand::History(_) => CommandMeta {
            name: "history",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "Show generation history",
        },
        ChatCommand::Stats => CommandMeta {
            name: "stats",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Show generation statistics",
        },
        ChatCommand::Providers => CommandMeta {
            name: "providers",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "Show provider health",
        },
        ChatCommand::Models(_) => CommandMeta {
            name: "models",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Show models",
        },
        ChatCommand::Settings(args) => {
            let reset = args
                .first()
                .map(|v| v.eq_ignore_ascii_case("reset"))
                .unwrap_or(false);
            CommandMeta {
                name: "settings",
                read_only: !reset,
                requires_confirmation: reset,
                supports_suggestions: false,
                help_text: "View or reset settings",
            }
        }
        ChatCommand::Guided(_) => CommandMeta {
            name: "guided",
            read_only: true,
            requires_confirmation: false,
            supports_suggestions: true,
            help_text: "Guided workflow steps",
        },
        ChatCommand::Label(args) => {
            let done = args
                .first()
                .map(|v| v.eq_ignore_ascii_case("done"))
                .unwrap_or(false);
            CommandMeta {
                name: "label",
                read_only: !done,
                requires_confirmation: done,
                supports_suggestions: true,
                help_text: "Manage label workflow",
            }
        }
        ChatCommand::System(_) => CommandMeta {
            name: "system",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Show or set system prompt",
        },
        ChatCommand::Save(_) => CommandMeta {
            name: "save",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Save session",
        },
        ChatCommand::Load(_) => CommandMeta {
            name: "load",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Load session",
        },
        ChatCommand::Quit => CommandMeta {
            name: "quit",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Leave chat",
        },
        ChatCommand::Yes | ChatCommand::No => CommandMeta {
            name: "confirm",
            read_only: false,
            requires_confirmation: false,
            supports_suggestions: false,
            help_text: "Confirm or cancel pending command",
        },
        ChatCommand::Unknown(_, _) | ChatCommand::PlainPrompt(_) | ChatCommand::Empty => {
            return None
        }
    };
    Some(meta)
}

pub fn parse_hypo_topics(raw: &str) -> Result<Vec<String>, String> {
    if raw.trim().is_empty() {
        return Err("Usage: /hypo <topic1,topic2,...>".into());
    }

    let topics: Vec<String> = raw
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(normalize_topic)
        .collect();

    if topics.is_empty() {
        return Err("No topics supplied. Example: /hypo negligence,causation".into());
    }

    Ok(topics)
}

pub fn parse_csv(raw: &str) -> Vec<String> {
    raw.split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(String::from)
        .collect()
}

pub fn normalize_topic(topic: &str) -> String {
    topic.trim().to_lowercase().replace(' ', "_")
}

pub fn parse_command_args(input: &str) -> CommandArgs {
    let tokens = tokenize_with_quotes(input);
    let mut args = CommandArgs::default();

    for token in tokens {
        if let Some((key, value)) = token.split_once('=') {
            if !key.trim().is_empty() {
                args.named
                    .insert(key.trim().to_lowercase(), value.trim().to_string());
                continue;
            }
        }
        args.positionals.push(token);
    }

    args
}

fn tokenize_with_quotes(input: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut current = String::new();
    let mut quote: Option<char> = None;

    let mut chars = input.chars().peekable();
    while let Some(ch) = chars.next() {
        match quote {
            Some(q) => {
                if ch == q {
                    quote = None;
                } else if ch == '\\' {
                    if let Some(next) = chars.peek() {
                        if *next == q || *next == '\\' {
                            current.push(*next);
                            chars.next();
                        } else {
                            current.push(ch);
                        }
                    } else {
                        current.push(ch);
                    }
                } else {
                    current.push(ch);
                }
            }
            None => {
                if ch == '"' || ch == '\'' {
                    quote = Some(ch);
                } else if ch.is_whitespace() {
                    if !current.is_empty() {
                        out.push(current.clone());
                        current.clear();
                    }
                } else {
                    current.push(ch);
                }
            }
        }
    }

    if !current.is_empty() {
        out.push(current);
    }

    out
}

pub fn build_prompt(messages: &[ChatMessage], latest_user: &str, turn_limit: usize) -> String {
    let limit = turn_limit.max(1);
    let visible: Vec<&ChatMessage> = messages
        .iter()
        .filter(|m| matches!(m.role, ChatRole::User | ChatRole::Assistant))
        .collect();

    if visible.is_empty() {
        return latest_user.trim().to_string();
    }

    let max_messages = limit.saturating_mul(2);
    let start = visible.len().saturating_sub(max_messages);
    let mut prompt = String::from("You are continuing an existing conversation.\n");
    prompt.push_str("Conversation so far:\n");

    for msg in &visible[start..] {
        match msg.role {
            ChatRole::User => {
                prompt.push_str("User: ");
                prompt.push_str(msg.content.trim());
                prompt.push('\n');
            }
            ChatRole::Assistant => {
                prompt.push_str("Assistant: ");
                prompt.push_str(msg.content.trim());
                prompt.push('\n');
            }
            ChatRole::Meta => {}
        }
    }

    prompt.push_str("User: ");
    prompt.push_str(latest_user.trim());
    prompt.push_str("\nAssistant:");
    prompt
}

pub fn default_session_path() -> PathBuf {
    let now = current_unix_timestamp();
    PathBuf::from(format!("data/chat_sessions/session-{}.json", now))
}

pub fn save_session(
    config: &ChatConfig,
    messages: &[ChatMessage],
    path: Option<&str>,
) -> Result<PathBuf, String> {
    let target = path
        .map(str::trim)
        .filter(|p| !p.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(default_session_path);

    if let Some(parent) = target.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create directory: {e}"))?;
    }

    let payload = SavedChatSessionV1 {
        version: CHAT_SESSION_VERSION,
        saved_at_unix: current_unix_timestamp(),
        config: config.clone(),
        messages: messages.to_vec(),
    };

    let serialized = serde_json::to_string_pretty(&payload)
        .map_err(|e| format!("Failed to serialize session: {e}"))?;
    std::fs::write(&target, serialized).map_err(|e| format!("Failed to save session: {e}"))?;
    Ok(target)
}

pub fn load_session(path: impl AsRef<Path>) -> Result<SavedChatSessionV1, String> {
    let content = std::fs::read_to_string(path.as_ref())
        .map_err(|e| format!("Failed to read session file: {e}"))?;
    let session: SavedChatSessionV1 =
        serde_json::from_str(&content).map_err(|e| format!("Failed to parse session JSON: {e}"))?;

    if session.version != CHAT_SESSION_VERSION {
        return Err(format!(
            "Unsupported session version {} (expected {})",
            session.version, CHAT_SESSION_VERSION
        ));
    }

    Ok(session)
}

fn current_unix_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_core_commands() {
        assert_eq!(parse_chat_command("/help"), ChatCommand::Help);
        assert_eq!(parse_chat_command("/clear"), ChatCommand::Clear);
        assert_eq!(parse_chat_command("/quit"), ChatCommand::Quit);
        assert_eq!(
            parse_chat_command("hello"),
            ChatCommand::PlainPrompt("hello".into())
        );
    }

    #[test]
    fn parse_extended_commands() {
        assert_eq!(parse_chat_command("/menu"), ChatCommand::Menu);
        assert_eq!(parse_chat_command("/yes"), ChatCommand::Yes);
        assert_eq!(parse_chat_command("/no"), ChatCommand::No);
        assert_eq!(parse_chat_command("/topics"), ChatCommand::Topics);
        assert_eq!(parse_chat_command("/stats"), ChatCommand::Stats);
        assert_eq!(parse_chat_command("/providers"), ChatCommand::Providers);
    }

    #[test]
    fn parse_argument_commands() {
        assert_eq!(
            parse_chat_command("/provider anthropic"),
            ChatCommand::Provider(Some("anthropic".into()))
        );
        assert_eq!(
            parse_chat_command("/system you are concise"),
            ChatCommand::System(Some("you are concise".into()))
        );
        assert_eq!(parse_chat_command("/model"), ChatCommand::Model(None));
        assert_eq!(parse_chat_command("/save"), ChatCommand::Save(None));
        assert_eq!(
            parse_chat_command("/load foo.json"),
            ChatCommand::Load(Some("foo.json".into()))
        );

        if let ChatCommand::Report(args) =
            parse_chat_command("/report last issue=topic_mismatch comment=\"Needs better causation\"")
        {
            assert_eq!(args.first(), Some("last"));
            assert_eq!(args.get("issue"), Some("topic_mismatch"));
            assert_eq!(args.get("comment"), Some("Needs better causation"));
        } else {
            panic!("expected report command");
        }
    }

    #[test]
    fn parse_command_args_supports_quotes_and_key_values() {
        let args = parse_command_args("last issue=topic_mismatch comment=\"Need more detail\" format=pdf");
        assert_eq!(args.first(), Some("last"));
        assert_eq!(args.get("issue"), Some("topic_mismatch"));
        assert_eq!(args.get("comment"), Some("Need more detail"));
        assert_eq!(args.get("format"), Some("pdf"));
    }

    #[test]
    fn parse_hypo_topics_normalizes() {
        let topics = parse_hypo_topics("Negligence, proximate cause").expect("topics");
        assert_eq!(topics, vec!["negligence", "proximate_cause"]);
    }

    #[test]
    fn infer_chat_intent_maps_common_requests() {
        assert_eq!(
            infer_chat_intent("show topics"),
            ChatIntent::Command(ChatCommand::Topics)
        );
        assert_eq!(
            infer_chat_intent("show statistics"),
            ChatIntent::Command(ChatCommand::Stats)
        );

        match infer_chat_intent("scrape singapore cases") {
            ChatIntent::Ambiguous(s) => assert!(!s.is_empty()),
            other => panic!("expected ambiguous intent, got {other:?}"),
        }
    }

    #[test]
    fn build_prompt_ignores_meta_and_slides() {
        let messages = vec![
            ChatMessage::new(ChatRole::Meta, "m0"),
            ChatMessage::new(ChatRole::User, "u1"),
            ChatMessage::new(ChatRole::Assistant, "a1"),
            ChatMessage::new(ChatRole::User, "u2"),
            ChatMessage::new(ChatRole::Assistant, "a2"),
            ChatMessage::new(ChatRole::User, "u3"),
            ChatMessage::new(ChatRole::Assistant, "a3"),
        ];
        let prompt = build_prompt(&messages, "latest", 2);
        assert!(!prompt.contains("m0"));
        assert!(!prompt.contains("u1"));
        assert!(prompt.contains("u2"));
        assert!(prompt.contains("a2"));
        assert!(prompt.contains("u3"));
        assert!(prompt.contains("a3"));
        assert!(prompt.contains("User: latest"));
    }

    #[test]
    fn session_roundtrip() {
        let mut path = std::env::temp_dir();
        path.push(format!("jikai-chat-test-{}.json", current_unix_timestamp()));
        let config = ChatConfig::default();
        let messages = vec![
            ChatMessage::new(ChatRole::User, "hello"),
            ChatMessage::new(ChatRole::Assistant, "hi"),
        ];

        let saved = save_session(&config, &messages, path.to_str()).expect("save ok");
        let loaded = load_session(saved).expect("load ok");

        assert_eq!(loaded.version, CHAT_SESSION_VERSION);
        assert_eq!(loaded.messages.len(), 2);
    }
}
