use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;
use crate::ui::widgets::confirm::Confirm;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::Spinner;

enum Phase {
    Confirm(Confirm),
    Running(Spinner),
    Done(MenuState),
    Error(String, MenuState),
}

pub struct PreprocessScreen { phase: Phase }

fn done_menu(msg: &str) -> MenuState {
    MenuState::new(msg, vec![
        MenuItem::new("Done", "return to previous screen"),
        MenuItem::new("Run Again", "preprocess again"),
    ])
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try again"),
        MenuItem::new("Go Back", "return to previous screen"),
    ])
}

impl PreprocessScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Confirm(Confirm::new("Preprocess raw corpus files?", true)) }
    }
}

impl Screen for PreprocessScreen {
    fn name(&self) -> &str { "Import & Preprocess" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::Confirm(confirm) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(yes) = confirm.handle_key(key) {
                    if yes {
                        self.phase = Phase::Running(Spinner::new("Preprocessing..."));
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
            Phase::Running(_) => {
                if key.code == KeyCode::Esc {
                    self.phase = Phase::Done(done_menu("Cancelled"));
                }
            }
            Phase::Done(menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => return ScreenAction::Pop,
                        1 => {
                            self.phase = Phase::Running(Spinner::new("Preprocessing..."));
                            let api = ctx.api_url.clone();
                            tokio::spawn(async move {
                                let client = crate::api::client::ApiClient::new(&api);
                                let _ = client.start_preprocess(None, None).await;
                            });
                        }
                        _ => return ScreenAction::Pop,
                    }
                }
            }
            Phase::Error(_, menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => {
                            self.phase = Phase::Running(Spinner::new("Preprocessing..."));
                            let api = ctx.api_url.clone();
                            tokio::spawn(async move {
                                let client = crate::api::client::ApiClient::new(&api);
                                let _ = client.start_preprocess(None, None).await;
                            });
                        }
                        _ => return ScreenAction::Pop,
                    }
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Confirm(c) => c.render(f, area),
            Phase::Running(s) => s.render(f, area),
            Phase::Done(menu) => menu.render(f, area),
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Phase::Running(s) = &mut self.phase { s.tick(); }
    }
}
