pub(crate) mod topics;

use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use crate::api::streaming::SseReader;
use crate::api::types::*;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::state::generation::TuiState;
use crate::ui::theme;
use crate::ui::widgets::checkbox::CheckboxState;
use crate::ui::widgets::confirm::Confirm;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::panel::Panel;
use crate::ui::widgets::progress::Spinner;
use crate::ui::widgets::stream_view::StreamView;

enum Phase {
    ModeSelect(MenuState),
    TopicSelect(CheckboxState),
    ConfigConfirm(Confirm),
    Streaming(StreamView),
    Generating(Spinner),
    Result(ResultView),
    PostGen(MenuState),
    Error(String, MenuState), // msg + action menu
}

struct GenerateConfig {
    topics: Vec<String>,
    provider: String,
    model: Option<String>,
    temperature: f64,
    complexity: u32,
    parties: u32,
    method: String,
    include_analysis: bool,
    red_herrings: bool,
}

impl Default for GenerateConfig {
    fn default() -> Self {
        let state = TuiState::load();
        Self {
            topics: Vec::new(),
            provider: state.last_config.provider,
            model: None,
            temperature: state.last_config.temperature,
            complexity: state.last_config.complexity.parse().unwrap_or(3),
            parties: state.last_config.parties.parse().unwrap_or(2),
            method: state.last_config.method,
            include_analysis: state.last_config.include_analysis,
            red_herrings: false,
        }
    }
}

struct ResultView {
    hypothetical: Panel,
    analysis: Option<Panel>,
    focus: usize, // 0 = hypo, 1 = analysis
}

pub struct GenerateScreen {
    phase: Phase,
    config: GenerateConfig,
    mode: String, // quick, exam, custom
    pending_response: Option<tokio::task::JoinHandle<Result<GenerationResponse, anyhow::Error>>>,
    sse_reader: SseReader,
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try generation again"),
        MenuItem::new("Change Settings", "go back to topic selection"),
        MenuItem::new("Go Back", "return to main menu"),
    ])
}

impl GenerateScreen {
    pub fn new() -> Self {
        let items = vec![
            MenuItem::new("Quick Generate", "topic only, use saved defaults"),
            MenuItem::new("Exam Practice", "realism-first preset"),
            MenuItem::new("Custom", "full configuration"),
        ];
        Self {
            phase: Phase::ModeSelect(MenuState::new("Generation Mode", items)),
            config: GenerateConfig::default(),
            mode: String::new(),
            pending_response: None,
            sse_reader: SseReader::new(),
        }
    }

    fn build_topic_checkbox(&self) -> CheckboxState {
        CheckboxState::new("Select Topics (Space=toggle, Enter=confirm)", topics::topic_items())
    }

    fn show_config_confirm(&self) -> Confirm {
        let summary = format!(
            "Topics: {}  Provider: {}  Temp: {:.1}  Complexity: {}  Parties: {}  Method: {}  Analysis: {}",
            if self.config.topics.is_empty() { "--".into() } else { self.config.topics.join(", ") },
            self.config.provider, self.config.temperature, self.config.complexity,
            self.config.parties, self.config.method,
            if self.config.include_analysis { "yes" } else { "no" },
        );
        Confirm::new(&format!("Proceed? {}", summary), true)
    }

    fn start_generation(&mut self, ctx: &mut AppContext) {
        let req = GenerationRequest {
            topics: self.config.topics.clone(),
            law_domain: "tort".into(),
            number_parties: self.config.parties,
            complexity_level: match self.config.complexity {
                1 => "beginner", 2 => "basic", 3 => "intermediate", 4 => "advanced", _ => "expert",
            }.into(),
            sample_size: 3,
            user_preferences: Some({
                let mut m = std::collections::HashMap::new();
                m.insert("temperature".into(), serde_json::json!(self.config.temperature));
                m.insert("red_herrings".into(), serde_json::json!(self.config.red_herrings));
                m
            }),
            method: self.config.method.clone(),
            provider: Some(self.config.provider.clone()),
            model: self.config.model.clone(),
            include_analysis: self.config.include_analysis,
            correlation_id: None,
        };
        self.phase = Phase::Generating(Spinner::new("Generating hypothetical..."));
        let api = ctx.api_url.clone();
        let handle = tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.generate(&req).await
        });
        self.pending_response = Some(handle);
    }

    fn show_result(&mut self, resp: GenerationResponse) {
        let analysis = if resp.analysis.is_empty() { None } else { Some(Panel::new("Legal Analysis", &resp.analysis)) };
        self.phase = Phase::Result(ResultView {
            hypothetical: Panel::new("Generated Hypothetical", &resp.hypothetical),
            analysis,
            focus: 0,
        });
        let mut state = TuiState::load();
        state.last_config.provider = self.config.provider.clone();
        state.last_config.model = self.config.model.clone();
        state.last_config.temperature = self.config.temperature;
        state.last_config.complexity = self.config.complexity.to_string();
        state.last_config.parties = self.config.parties.to_string();
        state.last_config.method = self.config.method.clone();
        state.last_config.include_analysis = self.config.include_analysis;
        state.save();
    }

    fn post_gen_menu(&self) -> MenuState {
        MenuState::new("Actions", vec![
            MenuItem::new("Done", "return to main menu"),
            MenuItem::new("Generate Another", "new hypothetical"),
            MenuItem::new("Report & Regenerate", "flag issues and retry"),
            MenuItem::new("Export", "save to DOCX/PDF"),
        ])
    }

    fn mode_select_menu() -> MenuState {
        MenuState::new("Generation Mode", vec![
            MenuItem::new("Quick Generate", "topic only, use saved defaults"),
            MenuItem::new("Exam Practice", "realism-first preset"),
            MenuItem::new("Custom", "full configuration"),
        ])
    }
}

impl Screen for GenerateScreen {
    fn name(&self) -> &str { "Generate" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc => {
                match &self.phase {
                    Phase::ModeSelect(_) => return ScreenAction::Pop,
                    Phase::PostGen(_) => return ScreenAction::Pop,
                    Phase::Error(_, _) => {
                        self.phase = Phase::ModeSelect(Self::mode_select_menu());
                        return ScreenAction::None;
                    }
                    _ => {
                        self.phase = Phase::ModeSelect(Self::mode_select_menu());
                        return ScreenAction::None;
                    }
                }
            }
            _ => {}
        }
        match &mut self.phase {
            Phase::ModeSelect(menu) => {
                if let Some(idx) = menu.handle_key(key) {
                    self.mode = match idx { 0 => "quick", 1 => "exam", _ => "custom" }.into();
                    if self.mode == "exam" {
                        self.config.temperature = 0.2;
                        self.config.complexity = 5;
                        self.config.parties = 4;
                        self.config.method = "hybrid".into();
                    }
                    self.phase = Phase::TopicSelect(self.build_topic_checkbox());
                }
            }
            Phase::TopicSelect(cb) => {
                if cb.handle_key(key) {
                    let selected = cb.selected_values();
                    if !selected.is_empty() {
                        self.config.topics = selected;
                        self.phase = Phase::ConfigConfirm(self.show_config_confirm());
                    }
                }
            }
            Phase::ConfigConfirm(confirm) => {
                if let Some(yes) = confirm.handle_key(key) {
                    if yes {
                        self.start_generation(ctx);
                    } else {
                        self.phase = Phase::TopicSelect(self.build_topic_checkbox());
                    }
                }
            }
            Phase::Streaming(sv) => {
                match key.code {
                    KeyCode::Char(' ') => sv.toggle_pause(),
                    KeyCode::Char('c') => {
                        sv.done = true;
                        self.phase = Phase::PostGen(self.post_gen_menu());
                    }
                    KeyCode::Up | KeyCode::Char('k') => sv.scroll_up(),
                    KeyCode::Down | KeyCode::Char('j') => sv.scroll_down(),
                    _ => {}
                }
            }
            Phase::Generating(_) => {} // wait for tick
            Phase::Result(rv) => {
                match key.code {
                    KeyCode::Up | KeyCode::Char('k') => {
                        match rv.focus {
                            0 => rv.hypothetical.scroll_up(),
                            _ => if let Some(a) = &mut rv.analysis { a.scroll_up(); },
                        }
                    }
                    KeyCode::Down | KeyCode::Char('j') => {
                        match rv.focus {
                            0 => rv.hypothetical.scroll_down(),
                            _ => if let Some(a) = &mut rv.analysis { a.scroll_down(); },
                        }
                    }
                    KeyCode::Tab => {
                        if rv.analysis.is_some() { rv.focus = (rv.focus + 1) % 2; }
                    }
                    KeyCode::Enter => {
                        self.phase = Phase::PostGen(self.post_gen_menu());
                    }
                    _ => {}
                }
            }
            Phase::PostGen(menu) => {
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => return ScreenAction::Pop,
                        1 => { self.phase = Phase::TopicSelect(self.build_topic_checkbox()); }
                        2 => {} // report -- TODO
                        3 => return ScreenAction::Push(Box::new(super::export::ExportScreen::new())),
                        _ => {}
                    }
                }
            }
            Phase::Error(_, menu) => {
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => self.start_generation(ctx), // retry
                        1 => { self.phase = Phase::TopicSelect(self.build_topic_checkbox()); }
                        _ => return ScreenAction::Pop,
                    }
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::ModeSelect(menu) => menu.render(f, area),
            Phase::TopicSelect(cb) => cb.render(f, area),
            Phase::ConfigConfirm(confirm) => {
                let layout = Layout::default().direction(Direction::Vertical)
                    .constraints([Constraint::Min(3), Constraint::Length(3)]).split(area);
                let summary = format!(
                    "Topics: {}\nProvider: {}\nTemperature: {:.1}\nComplexity: {}\nParties: {}\nMethod: {}\nAnalysis: {}",
                    self.config.topics.join(", "), self.config.provider,
                    self.config.temperature, self.config.complexity,
                    self.config.parties, self.config.method,
                    if self.config.include_analysis { "yes" } else { "no" },
                );
                let block = Block::default().title(Span::styled(" Configuration ", theme::title()))
                    .borders(Borders::ALL).border_style(theme::border());
                f.render_widget(Paragraph::new(summary).block(block), layout[0]);
                confirm.render(f, layout[1]);
            }
            Phase::Streaming(sv) => sv.render(f, area),
            Phase::Generating(spinner) => spinner.render(f, area),
            Phase::Result(rv) => {
                if rv.analysis.is_some() {
                    let layout = Layout::default().direction(Direction::Vertical)
                        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)]).split(area);
                    rv.hypothetical.render(f, layout[0]);
                    if let Some(a) = &rv.analysis { a.render(f, layout[1]); }
                } else {
                    rv.hypothetical.render(f, area);
                }
            }
            Phase::PostGen(menu) => menu.render(f, area),
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Phase::Generating(s) = &mut self.phase { s.tick(); }
        if let Some(handle) = &self.pending_response {
            if handle.is_finished() {
                let handle = self.pending_response.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(resp)) => self.show_result(resp),
                    Ok(Err(e)) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                    Err(e) => { let msg = format!("Task failed: {}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                }
            }
        }
    }
}
