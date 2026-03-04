use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::screens::generate::topics;
use crate::ui::widgets::checkbox::CheckboxState;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::panel::Panel;
use crate::ui::widgets::progress::Spinner;

enum Phase {
    Loading(Spinner),
    Labelling { entry_idx: usize, panel: Panel, topics_cb: CheckboxState },
    Done(MenuState),
    Error(String, MenuState),
}

pub struct LabelScreen {
    phase: Phase,
    entries: Vec<crate::api::types::CorpusEntry>,
    labels: Vec<serde_json::Value>,
    pending: Option<tokio::task::JoinHandle<Result<Vec<crate::api::types::CorpusEntry>, anyhow::Error>>>,
}

fn done_menu(count: usize) -> MenuState {
    MenuState::new(&format!("Labelled {} entries", count), vec![
        MenuItem::new("Done", "return to previous screen"),
        MenuItem::new("Label More", "reload and continue"),
    ])
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try loading again"),
        MenuItem::new("Go Back", "return to previous screen"),
    ])
}

impl LabelScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Loading(Spinner::new("Loading corpus...")), entries: Vec::new(), labels: Vec::new(), pending: None }
    }

    fn show_entry(&mut self, idx: usize) {
        if let Some(entry) = self.entries.get(idx) {
            let panel = Panel::new(&format!("Entry {}/{}", idx + 1, self.entries.len()), &entry.text);
            let cb = CheckboxState::new("Label topics (Space=toggle, Enter=confirm)", topics::topic_items());
            self.phase = Phase::Labelling { entry_idx: idx, panel, topics_cb: cb };
        } else {
            self.phase = Phase::Done(done_menu(self.labels.len()));
        }
    }
}

impl Screen for LabelScreen {
    fn name(&self) -> &str { "Label Corpus" }

    fn on_enter(&mut self, ctx: &mut AppContext) {
        self.phase = Phase::Loading(Spinner::new("Loading corpus..."));
        let api = ctx.api_url.clone();
        self.pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.list_corpus_entries(None, 500).await
        }));
    }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::Loading(_) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
            }
            Phase::Labelling { entry_idx, panel, topics_cb } => {
                if key.code == KeyCode::Esc {
                    self.phase = Phase::Done(done_menu(self.labels.len()));
                    return ScreenAction::None;
                }
                if topics_cb.handle_key(key) {
                    let selected = topics_cb.selected_values();
                    if !selected.is_empty() {
                        let entry = &self.entries[*entry_idx];
                        self.labels.push(serde_json::json!({
                            "text": entry.text,
                            "topics": selected,
                            "quality_score": 5.0,
                            "difficulty_level": "medium",
                        }));
                    }
                    let next = *entry_idx + 1;
                    self.show_entry(next);
                } else {
                    match key.code {
                        KeyCode::Up | KeyCode::Char('k') => panel.scroll_up(),
                        KeyCode::Down | KeyCode::Char('j') => panel.scroll_down(),
                        _ => {}
                    }
                }
            }
            Phase::Done(menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => return ScreenAction::Pop,
                        1 => self.on_enter(ctx),
                        _ => return ScreenAction::Pop,
                    }
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
            Phase::Labelling { panel, topics_cb, .. } => {
                let layout = Layout::default().direction(Direction::Vertical)
                    .constraints([Constraint::Percentage(40), Constraint::Percentage(60)]).split(area);
                panel.render(f, layout[0]);
                topics_cb.render(f, layout[1]);
            }
            Phase::Done(menu) => menu.render(f, area),
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Phase::Loading(s) = &mut self.phase { s.tick(); }
        if let Some(result) = crate::async_join::take_join_result_if_finished(&mut self.pending) {
            match result {
                Ok(Ok(entries)) => { self.entries = entries; self.show_entry(0); }
                Ok(Err(e)) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                Err(e) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
            }
        }
    }
}
