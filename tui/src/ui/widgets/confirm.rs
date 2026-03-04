use crate::ui::theme;
use crossterm::event::{KeyCode, KeyEvent};
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;

pub struct Confirm {
    pub message: String,
    pub yes_selected: bool,
}

impl Confirm {
    pub fn new(message: &str, default_yes: bool) -> Self {
        Self {
            message: message.into(),
            yes_selected: default_yes,
        }
    }

    /// returns Some(true/false) on Enter, None otherwise
    pub fn handle_key(&mut self, key: KeyEvent) -> Option<bool> {
        match key.code {
            KeyCode::Char('y') | KeyCode::Char('Y') => Some(true),
            KeyCode::Char('n') | KeyCode::Char('N') => Some(false),
            KeyCode::Left | KeyCode::Char('h') => {
                self.yes_selected = true;
                None
            }
            KeyCode::Right | KeyCode::Char('l') => {
                self.yes_selected = false;
                None
            }
            KeyCode::Enter => Some(self.yes_selected),
            KeyCode::Esc => Some(false),
            _ => None,
        }
    }

    pub fn render(&self, f: &mut Frame, area: Rect) {
        let yes_style = if self.yes_selected {
            theme::selected()
        } else {
            theme::normal()
        };
        let no_style = if !self.yes_selected {
            theme::selected()
        } else {
            theme::normal()
        };
        let line = Line::from(vec![
            Span::styled(&self.message, theme::normal()),
            Span::raw("  "),
            Span::styled(" Yes ", yes_style),
            Span::raw("  "),
            Span::styled(" No ", no_style),
        ]);
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(theme::border());
        f.render_widget(Paragraph::new(line).block(block), area);
    }
}
