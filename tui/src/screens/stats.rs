use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::Spinner;

enum Phase {
    Loading(Spinner),
    Display(String),
    Error(String, MenuState),
}

pub struct StatsScreen {
    phase: Phase,
    pending: Option<tokio::task::JoinHandle<Result<serde_json::Value, anyhow::Error>>>,
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try loading again"),
        MenuItem::new("Go Back", "return to previous screen"),
    ])
}

impl StatsScreen {
    pub fn new() -> Self { Self { phase: Phase::Loading(Spinner::new("Loading statistics...")), pending: None } }
}

impl Screen for StatsScreen {
    fn name(&self) -> &str { "Statistics" }

    fn on_enter(&mut self, ctx: &mut AppContext) {
        self.phase = Phase::Loading(Spinner::new("Loading statistics..."));
        let api = ctx.api_url.clone();
        self.pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.get_statistics().await
        }));
    }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::Loading(_) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
            }
            Phase::Display(_) => {
                match key.code {
                    KeyCode::Esc | KeyCode::Char('q') | KeyCode::Enter => return ScreenAction::Pop,
                    _ => {}
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
            Phase::Display(text) => {
                let block = Block::default().title(Span::styled(" Statistics ", theme::title()))
                    .borders(Borders::ALL).border_style(theme::border());
                f.render_widget(Paragraph::new(text.as_str()).wrap(Wrap { trim: false }).block(block), area);
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
                    Ok(Ok(stats)) => {
                        self.phase = Phase::Display(serde_json::to_string_pretty(&stats).unwrap_or_else(|_| "No data".into()));
                    }
                    Ok(Err(e)) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                    Err(e) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                }
            }
        }
    }
}
