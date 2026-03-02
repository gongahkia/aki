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
    Running(Spinner, String), // spinner + job_id
    Done(String),
    Error(String),
}

pub struct PreprocessScreen { phase: Phase, poll_pending: Option<tokio::task::JoinHandle<Result<crate::api::types::JobStatus, anyhow::Error>>> }

impl PreprocessScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Confirm(Confirm::new("Preprocess raw corpus files?", true)), poll_pending: None }
    }
}

impl Screen for PreprocessScreen {
    fn name(&self) -> &str { "Import & Preprocess" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        match &mut self.phase {
            Phase::Confirm(confirm) => {
                if let Some(yes) = confirm.handle_key(key) {
                    if yes {
                        let api = ctx.api_url.clone();
                        let _handle = tokio::spawn(async move {
                            let client = crate::api::client::ApiClient::new(&api);
                            client.start_preprocess(None, None).await
                        });
                        // fire and check on tick
                        self.phase = Phase::Running(Spinner::new("Preprocessing..."), String::new());
                        // store handle differently -- start job inline
                        let api = ctx.api_url.clone();
                        tokio::spawn(async move {
                            let client = crate::api::client::ApiClient::new(&api);
                            let _ = client.start_preprocess(None, None).await;
                        });
                    } else {
                        return ScreenAction::Pop;
                    }
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
            Phase::Confirm(c) => c.render(f, area),
            Phase::Running(s, _) => s.render(f, area),
            Phase::Done(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::success()), area); }
            Phase::Error(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::error()), area); }
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Phase::Running(s, _) = &mut self.phase { s.tick(); }
    }
}
