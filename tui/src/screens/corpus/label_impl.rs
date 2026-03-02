use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::screens::generate::topics;
use crate::ui::theme;
use crate::ui::widgets::checkbox::{CheckboxItem, CheckboxState};
use crate::ui::widgets::panel::Panel;

enum Phase {
    Loading,
    Labelling { entry_idx: usize, panel: Panel, topics_cb: CheckboxState },
    Done(String),
    Error(String),
}

pub struct LabelScreen {
    phase: Phase,
    entries: Vec<crate::api::types::CorpusEntry>,
    labels: Vec<serde_json::Value>,
    pending: Option<tokio::task::JoinHandle<Result<Vec<crate::api::types::CorpusEntry>, anyhow::Error>>>,
}

impl LabelScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Loading, entries: Vec::new(), labels: Vec::new(), pending: None }
    }

    fn show_entry(&mut self, idx: usize) {
        if let Some(entry) = self.entries.get(idx) {
            let panel = Panel::new(&format!("Entry {}/{}", idx + 1, self.entries.len()), &entry.text);
            let cb = CheckboxState::new("Label topics (Space=toggle, Enter=confirm)", topics::topic_items());
            self.phase = Phase::Labelling { entry_idx: idx, panel, topics_cb: cb };
        } else {
            self.phase = Phase::Done(format!("Labelled {} entries.", self.labels.len()));
        }
    }
}

impl Screen for LabelScreen {
    fn name(&self) -> &str { "Label Corpus" }

    fn on_enter(&mut self, ctx: &mut AppContext) {
        let api = ctx.api_url.clone();
        self.pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.list_corpus_entries(None, 500).await
        }));
    }

    fn handle_key(&mut self, key: KeyEvent, _ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        match &mut self.phase {
            Phase::Labelling { entry_idx, panel, topics_cb } => {
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
            Phase::Done(_) | Phase::Error(_) => {
                if key.code == KeyCode::Enter { return ScreenAction::Pop; }
            }
            _ => {}
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Loading => { f.render_widget(Paragraph::new("Loading corpus...").style(theme::dim()), area); }
            Phase::Labelling { panel, topics_cb, .. } => {
                let layout = Layout::default().direction(Direction::Vertical)
                    .constraints([Constraint::Percentage(40), Constraint::Percentage(60)]).split(area);
                panel.render(f, layout[0]);
                topics_cb.render(f, layout[1]);
            }
            Phase::Done(msg) => {
                let block = Block::default().title(" Done ").borders(Borders::ALL).border_style(theme::success());
                f.render_widget(Paragraph::new(msg.as_str()).block(block), area);
            }
            Phase::Error(msg) => {
                f.render_widget(Paragraph::new(msg.as_str()).style(theme::error()), area);
            }
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Some(handle) = &self.pending {
            if handle.is_finished() {
                let handle = self.pending.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(entries)) => { self.entries = entries; self.show_entry(0); }
                    Ok(Err(e)) => self.phase = Phase::Error(format!("{}", e)),
                    Err(e) => self.phase = Phase::Error(format!("{}", e)),
                }
            }
        }
    }
}
