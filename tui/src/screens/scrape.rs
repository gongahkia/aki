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
    SourceSelect(MenuState),
    Running(Spinner, String),
    Done(String),
    Error(String),
}

pub struct ScrapeScreen {
    phase: Phase,
}

impl ScrapeScreen {
    pub fn new() -> Self {
        let items = vec![
            MenuItem::new("CommonLII", "commonlii.org Singapore cases"),
            MenuItem::new("Judiciary.gov.sg", "official judiciary portal"),
            MenuItem::new("SICC", "Singapore International Commercial Court"),
            MenuItem::new("SG Law Gazette", "law gazette articles"),
        ];
        Self { phase: Phase::SourceSelect(MenuState::new("Select Source", items)) }
    }
}

impl Screen for ScrapeScreen {
    fn name(&self) -> &str { "Scrape SG Case Law" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        match &mut self.phase {
            Phase::SourceSelect(menu) => {
                if let Some(idx) = menu.handle_key(key) {
                    let source = match idx {
                        0 => "commonlii", 1 => "judiciary", 2 => "sicc", _ => "gazette",
                    };
                    self.phase = Phase::Running(Spinner::new(&format!("Scraping {}...", source)), source.into());
                    let api = ctx.api_url.clone();
                    let src = source.to_string();
                    tokio::spawn(async move {
                        let client = crate::api::client::ApiClient::new(&api);
                        let req = crate::api::types::ScrapeRequest {
                            source: src, courts: None, years: None, max_cases: 50, tort_only: true,
                        };
                        let _ = client.start_scrape(&req).await;
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
            Phase::SourceSelect(menu) => menu.render(f, area),
            Phase::Running(s, _) => s.render(f, area),
            Phase::Done(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::success()), area); }
            Phase::Error(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::error()), area); }
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Phase::Running(s, _) = &mut self.phase { s.tick(); }
    }
}
