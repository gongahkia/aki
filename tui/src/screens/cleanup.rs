use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::Paragraph;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;
use crate::ui::widgets::checkbox::{CheckboxItem, CheckboxState};

enum Phase {
    Select(CheckboxState),
    Running(String),
    Done(String),
    Error(String),
}

pub struct CleanupScreen { phase: Phase }

impl CleanupScreen {
    pub fn new() -> Self {
        let items = vec![
            CheckboxItem::option("Logs", "logs", "logs/ directory"),
            CheckboxItem::option("Models", "models", "models/*.joblib"),
            CheckboxItem::option("Embeddings", "embeddings", "chroma_db/"),
            CheckboxItem::option("History JSON", "history", "data/history.json"),
            CheckboxItem::option("Labelled Data", "labelled", "corpus/labelled/"),
            CheckboxItem::option("Database", "database", "data/jikai.db"),
        ];
        Self { phase: Phase::Select(CheckboxState::new("Select items to remove", items)) }
    }
}

impl Screen for CleanupScreen {
    fn name(&self) -> &str { "Cleanup" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        match &mut self.phase {
            Phase::Select(cb) => {
                if cb.handle_key(key) {
                    let targets = cb.selected_values();
                    if targets.is_empty() { return ScreenAction::Pop; }
                    self.phase = Phase::Running("Cleaning up...".into());
                    let api = ctx.api_url.clone();
                    tokio::spawn(async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let _ = client.start_cleanup(&targets).await;
                    });
                }
            }
            Phase::Done(_) | Phase::Error(_) => {
                if key.code == KeyCode::Enter { return ScreenAction::Pop; }
            }
            _ => {}
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Select(cb) => cb.render(f, area),
            Phase::Running(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::dim()), area); }
            Phase::Done(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::success()), area); }
            Phase::Error(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::error()), area); }
        }
    }
}
