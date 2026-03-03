use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::Spinner;

enum Phase {
    Loading(Spinner),
    List(MenuState),
    Detail(String),
    Error(String, MenuState),
}

pub struct ProvidersScreen {
    phase: Phase,
    health_data: Option<serde_json::Value>,
    models_data: Option<serde_json::Value>,
    pending: Option<tokio::task::JoinHandle<Result<(serde_json::Value, serde_json::Value), anyhow::Error>>>,
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try loading again"),
        MenuItem::new("Go Back", "return to previous screen"),
    ])
}

impl ProvidersScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Loading(Spinner::new("Checking providers...")), health_data: None, models_data: None, pending: None }
    }

    fn rebuild_list(&mut self) {
        let providers = ["ollama", "openai", "anthropic", "google"];
        let items: Vec<MenuItem> = providers.iter().map(|&p| {
            let healthy = self.health_data.as_ref()
                .and_then(|h| h.get(p))
                .and_then(|v| v.get("healthy"))
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            let status = if healthy { theme::STATUS_OK } else { theme::STATUS_ERROR };
            MenuItem::new(p, &format!("{} health", status))
        }).collect();
        self.phase = Phase::List(MenuState::new("Providers", items));
    }
}

impl Screen for ProvidersScreen {
    fn name(&self) -> &str { "Providers" }

    fn on_enter(&mut self, ctx: &mut AppContext) {
        self.phase = Phase::Loading(Spinner::new("Checking providers..."));
        let api = ctx.api_url.clone();
        self.pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            let health = client.llm_health(None).await?;
            let models = client.llm_models(None).await?;
            Ok((health, models))
        }));
    }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::Loading(_) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
            }
            Phase::List(menu) => {
                if key.code == KeyCode::Esc || key.code == KeyCode::Char('q') { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    if let Some(label) = menu.items.get(idx).map(|i| i.label.clone()) {
                        let detail = format!("Provider: {}\n\nHealth: {}\n\nModels: {}",
                            label,
                            self.health_data.as_ref().map(|h| serde_json::to_string_pretty(h).unwrap_or_default()).unwrap_or_else(|| "--".into()),
                            self.models_data.as_ref().map(|m| serde_json::to_string_pretty(m).unwrap_or_default()).unwrap_or_else(|| "--".into()),
                        );
                        self.phase = Phase::Detail(detail);
                    }
                }
            }
            Phase::Detail(_) => {
                if key.code == KeyCode::Esc || key.code == KeyCode::Backspace {
                    self.rebuild_list();
                }
            }
            Phase::Error(_, menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => self.on_enter(ctx),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Loading(spinner) => spinner.render(f, area),
            Phase::List(menu) => menu.render(f, area),
            Phase::Detail(text) => {
                let block = Block::default().title(Span::styled(" Provider Detail ", theme::title()))
                    .borders(Borders::ALL).border_style(theme::border());
                f.render_widget(Paragraph::new(text.as_str()).block(block), area);
            }
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Phase::Loading(s) = &mut self.phase { s.tick(); }
        if let Some(handle) = &self.pending {
            if handle.is_finished() {
                let handle = self.pending.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok((health, models))) => {
                        self.health_data = Some(health);
                        self.models_data = Some(models);
                        self.rebuild_list();
                    }
                    Ok(Err(e)) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                    Err(e) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                }
            }
        }
    }
}
