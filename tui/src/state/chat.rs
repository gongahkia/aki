use serde::{Deserialize, Serialize};
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ChatCommand {
    Help,
    Clear,
    Provider(Option<String>),
    Model(Option<String>),
    Temp(Option<String>),
    Tokens,
    Hypo(String),
    System(Option<String>),
    Save(Option<String>),
    Load(Option<String>),
    Quit,
    Unknown(String),
    PlainPrompt(String),
    Empty,
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
    let command = split.next().unwrap_or_default();
    let args = split.next().map(str::trim).unwrap_or_default();
    let args_opt = if args.is_empty() {
        None
    } else {
        Some(args.to_string())
    };

    match command {
        "help" => ChatCommand::Help,
        "clear" => ChatCommand::Clear,
        "provider" => ChatCommand::Provider(args_opt),
        "model" => ChatCommand::Model(args_opt),
        "temp" => ChatCommand::Temp(args_opt),
        "tokens" => ChatCommand::Tokens,
        "hypo" => ChatCommand::Hypo(args.to_string()),
        "system" => ChatCommand::System(args_opt),
        "save" => ChatCommand::Save(args_opt),
        "load" => ChatCommand::Load(args_opt),
        "quit" => ChatCommand::Quit,
        _ => ChatCommand::Unknown(command.to_string()),
    }
}

pub fn parse_hypo_topics(raw: &str) -> Result<Vec<String>, String> {
    if raw.trim().is_empty() {
        return Err("Usage: /hypo <topic1,topic2,...>".into());
    }

    let topics: Vec<String> = raw
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|topic| topic.to_lowercase().replace(' ', "_"))
        .collect();

    if topics.is_empty() {
        return Err("No topics supplied. Example: /hypo negligence,causation".into());
    }

    Ok(topics)
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

    let serialized =
        serde_json::to_string_pretty(&payload).map_err(|e| format!("Failed to serialize session: {e}"))?;
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
        assert_eq!(parse_chat_command("hello"), ChatCommand::PlainPrompt("hello".into()));
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
        assert_eq!(parse_chat_command("/load foo.json"), ChatCommand::Load(Some("foo.json".into())));
    }

    #[test]
    fn parse_hypo_topics_rejects_empty() {
        assert!(parse_hypo_topics("").is_err());
        assert!(parse_hypo_topics(" , , ").is_err());
    }

    #[test]
    fn parse_hypo_topics_normalizes() {
        let parsed = parse_hypo_topics("Duty Of Care, causation").unwrap();
        assert_eq!(parsed, vec!["duty_of_care".to_string(), "causation".to_string()]);
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
    fn save_load_round_trip() {
        let mut path = std::env::temp_dir();
        path.push(format!(
            "jikai-chat-test-{}.json",
            current_unix_timestamp()
        ));
        let config = ChatConfig::default();
        let messages = vec![
            ChatMessage::new(ChatRole::User, "hello"),
            ChatMessage::new(ChatRole::Assistant, "hi"),
        ];
        let saved = save_session(&config, &messages, Some(path.to_string_lossy().as_ref())).unwrap();
        let loaded = load_session(saved).unwrap();
        assert_eq!(loaded.version, CHAT_SESSION_VERSION);
        assert_eq!(loaded.messages, messages);
    }
}
