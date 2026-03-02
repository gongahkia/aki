use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::Paragraph;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::Spinner;

enum Phase {
    FormatSelect(MenuState),
    Running(Spinner),
    Done(String),
    Error(String),
}

pub struct ExportScreen { phase: Phase }

impl ExportScreen {
    pub fn new() -> Self {
        let items = vec![
            MenuItem::new("DOCX", "Microsoft Word document"),
            MenuItem::new("PDF", "portable document format"),
        ];
        Self { phase: Phase::FormatSelect(MenuState::new("Export Format", items)) }
    }
}

impl Screen for ExportScreen {
    fn name(&self) -> &str { "Export" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        match &mut self.phase {
            Phase::FormatSelect(menu) => {
                if let Some(idx) = menu.handle_key(key) {
                    let format = if idx == 0 { "docx" } else { "pdf" };
                    self.phase = Phase::Running(Spinner::new(&format!("Exporting as {}...", format)));
                    let api = ctx.api_url.clone();
                    let fmt = format.to_string();
                    tokio::spawn(async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let req = crate::api::types::ExportRequest {
                            generation_id: None,
                            hypothetical: Some("(last generated)".into()),
                            analysis: None,
                            model_answer: None,
                            format: fmt,
                            output_path: None,
                        };
                        let _ = client.start_export(&req).await;
                    });
                }
            }
            Phase::Done(_) | Phase::Error(_) => { if key.code == KeyCode::Enter { return ScreenAction::Pop; } }
            _ => {}
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::FormatSelect(menu) => menu.render(f, area),
            Phase::Running(s) => s.render(f, area),
            Phase::Done(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::success()), area); }
            Phase::Error(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::error()), area); }
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) { if let Phase::Running(s) = &mut self.phase { s.tick(); } }
}
