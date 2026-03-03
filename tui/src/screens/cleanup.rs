use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::checkbox::{CheckboxItem, CheckboxState};
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::ProgressBar;

enum Phase {
    Select(CheckboxState),
    Running(ProgressBar),
    Done(MenuState),
    Error(String, MenuState),
}

pub struct CleanupScreen {
    phase: Phase,
    start_pending: Option<tokio::task::JoinHandle<Result<serde_json::Value, anyhow::Error>>>,
}

fn cleanup_items() -> Vec<CheckboxItem> {
    vec![
        CheckboxItem::option("Logs", "logs", "logs/ directory"),
        CheckboxItem::option("Models", "models", "models/*.joblib"),
        CheckboxItem::option("Embeddings", "embeddings", "chroma_db/"),
        CheckboxItem::option("History JSON", "history", "data/history.json"),
        CheckboxItem::option("Labelled Data", "labelled", "corpus/labelled/"),
        CheckboxItem::option("Database", "database", "data/jikai.db"),
    ]
}

fn done_menu() -> MenuState {
    MenuState::new("Cleanup complete", vec![
        MenuItem::new("Done", "return to previous screen"),
        MenuItem::new("Clean More", "select more items"),
    ])
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try again"),
        MenuItem::new("Go Back", "return to previous screen"),
    ])
}

impl CleanupScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Select(CheckboxState::new("Select items to remove", cleanup_items())), start_pending: None }
    }

    fn start_cleanup(&mut self, targets: &[String], ctx: &mut AppContext) {
        let count = targets.len();
        self.phase = Phase::Running(ProgressBar::new(&format!("Cleaning {} items", count)));
        let api = ctx.api_url.clone();
        let t = targets.to_vec();
        self.start_pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.start_cleanup(&t).await
        }));
    }
}

impl Screen for CleanupScreen {
    fn name(&self) -> &str { "Cleanup" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::Select(cb) => {
                if key.code == KeyCode::Esc || key.code == KeyCode::Char('q') { return ScreenAction::Pop; }
                if cb.handle_key(key) {
                    let targets = cb.selected_values();
                    if targets.is_empty() { return ScreenAction::Pop; }
                    self.start_cleanup(&targets, ctx);
                }
            }
            Phase::Running(_) => {}
            Phase::Done(menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => return ScreenAction::Pop,
                        1 => self.phase = Phase::Select(CheckboxState::new("Select items to remove", cleanup_items())),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
            Phase::Error(_, menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => self.phase = Phase::Select(CheckboxState::new("Select items to remove", cleanup_items())),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Select(cb) => cb.render(f, area),
            Phase::Running(bar) => bar.render(f, area),
            Phase::Done(menu) => menu.render(f, area),
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        // cleanup returns immediately (not a polled job), so check start_pending
        if let Some(handle) = &self.start_pending {
            if handle.is_finished() {
                let handle = self.start_pending.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(_)) => {
                        // set bar to 100% briefly, then done
                        self.phase = Phase::Done(done_menu());
                    }
                    Ok(Err(e)) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                    Err(e) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                }
            }
        }
    }
}
