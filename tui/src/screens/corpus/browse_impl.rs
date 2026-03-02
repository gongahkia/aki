use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::Paragraph;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;
use crate::ui::widgets::table::DataTable;
use crate::ui::widgets::panel::Panel;

enum Phase {
    Loading,
    List(DataTable),
    Detail(Panel),
    Error(String),
}

pub struct BrowseScreen {
    phase: Phase,
    entries: Vec<crate::api::types::CorpusEntry>,
    pending: Option<tokio::task::JoinHandle<Result<Vec<crate::api::types::CorpusEntry>, anyhow::Error>>>,
}

impl BrowseScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Loading, entries: Vec::new(), pending: None }
    }

    fn rebuild_list(&mut self) {
        let mut table = DataTable::new("Corpus", vec!["#".into(), "Topics".into(), "Length".into()], vec![5, 40, 8]);
        let rows: Vec<Vec<String>> = self.entries.iter().enumerate().map(|(i, e)| vec![
            (i + 1).to_string(),
            e.topics.join(", "),
            e.text.len().to_string(),
        ]).collect();
        table.set_rows(rows);
        self.phase = Phase::List(table);
    }
}

impl Screen for BrowseScreen {
    fn name(&self) -> &str { "Browse Corpus" }

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
            Phase::List(table) => {
                if let Some(idx) = table.handle_key(key) {
                    if let Some(entry) = self.entries.get(idx) {
                        let content = format!("Topics: {}\n\n{}", entry.topics.join(", "), entry.text);
                        self.phase = Phase::Detail(Panel::new("Entry", &content));
                    }
                }
            }
            Phase::Detail(panel) => {
                match key.code {
                    KeyCode::Up | KeyCode::Char('k') => panel.scroll_up(),
                    KeyCode::Down | KeyCode::Char('j') => panel.scroll_down(),
                    KeyCode::Esc | KeyCode::Backspace => self.rebuild_list(),
                    _ => {}
                }
            }
            _ => {}
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Loading => { f.render_widget(Paragraph::new("Loading corpus...").style(theme::dim()), area); }
            Phase::List(table) => table.render(f, area),
            Phase::Detail(panel) => panel.render(f, area),
            Phase::Error(msg) => { f.render_widget(Paragraph::new(msg.as_str()).style(theme::error()), area); }
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Some(handle) = &self.pending {
            if handle.is_finished() {
                let handle = self.pending.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(entries)) => { self.entries = entries; self.rebuild_list(); }
                    Ok(Err(e)) => self.phase = Phase::Error(format!("{}", e)),
                    Err(e) => self.phase = Phase::Error(format!("{}", e)),
                }
            }
        }
    }
}
