use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use crate::ui::theme;

pub struct TextInput {
    pub label: String,
    pub value: String,
    pub cursor: usize,
}

impl TextInput {
    pub fn new(label: &str, default: &str) -> Self {
        let len = default.len();
        Self { label: label.into(), value: default.into(), cursor: len }
    }

    /// returns true if Enter was pressed
    pub fn handle_key(&mut self, key: KeyEvent) -> bool {
        match key.code {
            KeyCode::Char(c) => {
                self.value.insert(self.cursor, c);
                self.cursor += 1;
                false
            }
            KeyCode::Backspace => {
                if self.cursor > 0 {
                    self.cursor -= 1;
                    self.value.remove(self.cursor);
                }
                false
            }
            KeyCode::Delete => {
                if self.cursor < self.value.len() {
                    self.value.remove(self.cursor);
                }
                false
            }
            KeyCode::Left => { if self.cursor > 0 { self.cursor -= 1; } false }
            KeyCode::Right => { if self.cursor < self.value.len() { self.cursor += 1; } false }
            KeyCode::Home => { self.cursor = 0; false }
            KeyCode::End => { self.cursor = self.value.len(); false }
            KeyCode::Enter => true,
            _ => false,
        }
    }

    pub fn render(&self, f: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(Span::styled(format!(" {} ", self.label), theme::title()))
            .borders(Borders::ALL)
            .border_style(theme::border());
        let display = format!("{}_", self.value); // show cursor
        let p = Paragraph::new(display).style(theme::input()).block(block);
        f.render_widget(p, area);
    }
}
