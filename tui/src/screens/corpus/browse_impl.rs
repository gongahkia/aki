use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::Spinner;
use crate::ui::widgets::table::DataTable;
use crate::ui::widgets::panel::Panel;

enum Phase {
    Loading(Spinner),
    List(DataTable),
    Detail(Panel),
    Error(String, MenuState),
}

pub struct BrowseScreen {
    phase: Phase,
    entries: Vec<crate::api::types::CorpusEntry>,
    pending: Option<tokio::task::JoinHandle<Result<Vec<crate::api::types::CorpusEntry>, anyhow::Error>>>,
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try loading again"),
        MenuItem::new("Go Back", "return to previous screen"),
    ])
}

impl BrowseScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Loading(Spinner::new("Loading corpus...")), entries: Vec::new(), pending: None }
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
            Phase::List(table) => {
                if key.code == KeyCode::Esc || key.code == KeyCode::Char('q') { return ScreenAction::Pop; }
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
            Phase::List(table) => table.render(f, area),
            Phase::Detail(panel) => panel.render(f, area),
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Phase::Loading(s) = &mut self.phase { s.tick(); }
        if let Some(result) = crate::async_join::take_join_result_if_finished(&mut self.pending) {
            match result {
                Ok(Ok(entries)) => { self.entries = entries; self.rebuild_list(); }
                Ok(Err(e)) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                Err(e) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
            }
        }
    }
}
