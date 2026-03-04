use crate::ui::theme;
use crossterm::event::{KeyCode, KeyEvent};
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Row, Table as RatatuiTable, TableState};
use ratatui::Frame;

pub struct DataTable {
    pub title: String,
    pub headers: Vec<String>,
    pub rows: Vec<Vec<String>>,
    pub widths: Vec<u16>,
    pub state: TableState,
}

impl DataTable {
    pub fn new(title: &str, headers: Vec<String>, widths: Vec<u16>) -> Self {
        Self {
            title: title.into(),
            headers,
            rows: Vec::new(),
            widths,
            state: TableState::default(),
        }
    }

    pub fn set_rows(&mut self, rows: Vec<Vec<String>>) {
        self.rows = rows;
        if !self.rows.is_empty() && self.state.selected().is_none() {
            self.state.select(Some(0));
        }
    }

    pub fn selected_index(&self) -> Option<usize> {
        self.state.selected()
    }

    pub fn handle_key(&mut self, key: KeyEvent) -> Option<usize> {
        match key.code {
            KeyCode::Up | KeyCode::Char('k') => {
                self.move_up();
                None
            }
            KeyCode::Down | KeyCode::Char('j') => {
                self.move_down();
                None
            }
            KeyCode::Enter => self.state.selected(),
            _ => None,
        }
    }

    fn move_up(&mut self) {
        let i = self.state.selected().unwrap_or(0);
        if i > 0 {
            self.state.select(Some(i - 1));
        }
    }

    fn move_down(&mut self) {
        let i = self.state.selected().unwrap_or(0);
        if i + 1 < self.rows.len() {
            self.state.select(Some(i + 1));
        }
    }

    pub fn render(&mut self, f: &mut Frame, area: Rect) {
        let header = Row::new(
            self.headers
                .iter()
                .map(|h| Span::styled(h.as_str(), theme::header())),
        );
        let widths: Vec<ratatui::layout::Constraint> = self
            .widths
            .iter()
            .map(|&w| ratatui::layout::Constraint::Length(w))
            .collect();
        let rows: Vec<Row> = self
            .rows
            .iter()
            .map(|row| Row::new(row.iter().map(|cell| Span::raw(cell.as_str()))))
            .collect();
        let block = Block::default()
            .title(Span::styled(format!(" {} ", self.title), theme::title()))
            .borders(Borders::ALL)
            .border_style(theme::border());
        let table = RatatuiTable::new(rows, &widths)
            .header(header)
            .block(block)
            .row_highlight_style(theme::selected());
        f.render_stateful_widget(table, area, &mut self.state);
    }
}
