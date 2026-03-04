use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LastConfig {
    #[serde(default = "default_provider")]
    pub provider: String,
    pub model: Option<String>,
    #[serde(default = "default_temp")]
    pub temperature: f64,
    #[serde(default = "default_complexity")]
    pub complexity: String,
    #[serde(default = "default_parties")]
    pub parties: String,
    #[serde(default = "default_method")]
    pub method: String,
    #[serde(default = "default_true")]
    pub include_analysis: bool,
}
fn default_provider() -> String { "ollama".into() }
fn default_temp() -> f64 { 0.7 }
fn default_complexity() -> String { "3".into() }
fn default_parties() -> String { "2".into() }
fn default_method() -> String { "pure_llm".into() }
fn default_true() -> bool { true }

impl Default for LastConfig {
    fn default() -> Self {
        Self {
            provider: default_provider(),
            model: None,
            temperature: default_temp(),
            complexity: default_complexity(),
            parties: default_parties(),
            method: default_method(),
            include_analysis: true,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum UiMode {
    Chat,
    Traditional,
}

impl Default for UiMode {
    fn default() -> Self { Self::Chat }
}

impl UiMode {
    pub fn toggled(&self) -> Self {
        match self {
            Self::Chat => Self::Traditional,
            Self::Traditional => Self::Chat,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            Self::Chat => "chat-first",
            Self::Traditional => "traditional",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TuiState {
    pub last_config: LastConfig,
    #[serde(default)]
    pub ui_mode: UiMode,
}

impl TuiState {
    pub fn load() -> Self {
        let path = Self::state_path();
        std::fs::read_to_string(&path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default()
    }

    pub fn save(&self) {
        let path = Self::state_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let _ = std::fs::write(&path, serde_json::to_string_pretty(self).unwrap_or_default());
    }

    fn state_path() -> PathBuf {
        PathBuf::from("data/tui_state.json")
    }
}
