use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::Paragraph;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;
use crate::ui::widgets::confirm::Confirm;
use crate::ui::widgets::progress::Spinner;

enum Phase {
    Confirm(Confirm),
    Running(Spinner),
    Done(String),
    Error(String),
}

pub struct TrainScreen { phase: Phase }

impl TrainScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Confirm(Confirm::new("Train ML models on labelled corpus?", true)) }
    }
}

impl Screen for TrainScreen {
    fn name(&self) -> &str { "Train ML Models" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        match &mut self.phase {
            Phase::Confirm(c) => {
                if let Some(yes) = c.handle_key(key) {
                    if yes {
                        self.phase = Phase::Running(Spinner::new("Training models..."));
                        let api = ctx.api_url.clone();
                        tokio::spawn(async move {
                            let client = crate::api::client::ApiClient::new(&api);
                            let _ = client.start_train("corpus/labelled/sample.csv", 5).await;
                        });
                    } else { return ScreenAction::Pop; }
                }
            }
            Phase::Done(_) | Phase::Error(_) => { if key.code == KeyCode::Enter { return ScreenAction::Pop; } }
            _ => {}
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Confirm(c) => c.render(f, area),
            Phase::Running(s) => s.render(f, area),
            Phase::Done(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::success()), area); }
            Phase::Error(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::error()), area); }
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) { if let Phase::Running(s) = &mut self.phase { s.tick(); } }
}
