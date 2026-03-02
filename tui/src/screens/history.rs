use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
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

pub struct HistoryScreen {
    phase: Phase,
    records: Vec<serde_json::Value>,
    pending: Option<tokio::task::JoinHandle<Result<Vec<crate::api::types::HistoryRecord>, anyhow::Error>>>,
}

impl HistoryScreen {
    pub fn new() -> Self {
        Self { phase: Phase::Loading, records: Vec::new(), pending: None }
    }
}

impl Screen for HistoryScreen {
    fn name(&self) -> &str { "History" }

    fn on_enter(&mut self, ctx: &mut AppContext) {
        let api = ctx.api_url.clone();
        self.pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.get_history(100).await
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
                    if let Some(record) = self.records.get(idx) {
                        let hypo = record["hypothetical"].as_str().unwrap_or("--");
                        let analysis = record["analysis"].as_str().unwrap_or("");
                        let content = if analysis.is_empty() {
                            hypo.to_string()
                        } else {
                            format!("{}\n\n--- Analysis ---\n\n{}", hypo, analysis)
                        };
                        self.phase = Phase::Detail(Panel::new("Generation Detail", &content));
                    }
                }
            }
            Phase::Detail(panel) => {
                match key.code {
                    KeyCode::Up | KeyCode::Char('k') => panel.scroll_up(),
                    KeyCode::Down | KeyCode::Char('j') => panel.scroll_down(),
                    KeyCode::Esc | KeyCode::Backspace => {
                        // rebuild list
                        let mut table = DataTable::new("History", vec!["ID".into(), "Topics".into(), "Score".into(), "Time".into()], vec![6, 30, 8, 20]);
                        let rows: Vec<Vec<String>> = self.records.iter().map(|r| vec![
                            r["id"].to_string(),
                            r["topics"].as_str().unwrap_or("--").to_string(),
                            format!("{:.1}", r["quality_score"].as_f64().unwrap_or(0.0)),
                            r["timestamp"].as_str().unwrap_or("--").to_string(),
                        ]).collect();
                        table.set_rows(rows);
                        self.phase = Phase::List(table);
                    }
                    _ => {}
                }
            }
            _ => {}
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Loading => {
                let p = Paragraph::new("Loading history...").style(theme::dim());
                f.render_widget(p, area);
            }
            Phase::List(table) => table.render(f, area),
            Phase::Detail(panel) => panel.render(f, area),
            Phase::Error(msg) => {
                let block = Block::default().title(" Error ").borders(Borders::ALL).border_style(theme::error());
                f.render_widget(Paragraph::new(msg.as_str()).block(block), area);
            }
        }
    }

    fn tick(&mut self, _ctx: &mut AppContext) {
        if let Some(handle) = &self.pending {
            if handle.is_finished() {
                let handle = self.pending.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(records)) => {
                        self.records = records.iter().map(|r| serde_json::to_value(r).unwrap_or_default()).collect();
                        let mut table = DataTable::new("History", vec!["ID".into(), "Topics".into(), "Score".into(), "Time".into()], vec![6, 30, 8, 20]);
                        let rows: Vec<Vec<String>> = records.iter().map(|r| vec![
                            r.id.to_string(),
                            r.topics.clone(),
                            format!("{:.1}", r.quality_score),
                            r.timestamp.clone(),
                        ]).collect();
                        table.set_rows(rows);
                        self.phase = Phase::List(table);
                    }
                    Ok(Err(e)) => self.phase = Phase::Error(format!("{}", e)),
                    Err(e) => self.phase = Phase::Error(format!("{}", e)),
                }
            }
        }
    }
}
