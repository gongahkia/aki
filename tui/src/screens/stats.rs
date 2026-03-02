use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;

enum Phase {
    Loading,
    Display(String),
    Error(String),
}

pub struct StatsScreen {
    phase: Phase,
    pending: Option<tokio::task::JoinHandle<Result<serde_json::Value, anyhow::Error>>>,
}

impl StatsScreen {
    pub fn new() -> Self { Self { phase: Phase::Loading, pending: None } }
}

impl Screen for StatsScreen {
    fn name(&self) -> &str { "Statistics" }

    fn on_enter(&mut self, ctx: &mut AppContext) {
        let api = ctx.api_url.clone();
        self.pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.get_statistics().await
        }));
    }

    fn handle_key(&mut self, key: KeyEvent, _ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') | KeyCode::Enter => ScreenAction::Pop,
            _ => ScreenAction::None,
        }
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &self.phase {
            Phase::Loading => { f.render_widget(Paragraph::new("Loading statistics...").style(theme::dim()), area); }
            Phase::Display(text) => {
                let block = Block::default().title(Span::styled(" Statistics ", theme::title()))
                    .borders(Borders::ALL).border_style(theme::border());
                f.render_widget(Paragraph::new(text.as_str()).wrap(Wrap { trim: false }).block(block), area);
            }
            Phase::Error(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::error()), area); }
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Some(handle) = &self.pending {
            if handle.is_finished() {
                let handle = self.pending.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(stats)) => {
                        self.phase = Phase::Display(serde_json::to_string_pretty(&stats).unwrap_or_else(|_| "No data".into()));
                    }
                    Ok(Err(e)) => self.phase = Phase::Error(format!("{}", e)),
                    Err(e) => self.phase = Phase::Error(format!("{}", e)),
                }
            }
        }
    }
}
