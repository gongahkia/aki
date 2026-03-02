use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, List, ListItem, ListState};
use crate::ui::theme;

pub struct MenuItem {
    pub label: String,
    pub description: String,
    pub enabled: bool,
}

impl MenuItem {
    pub fn new(label: &str, desc: &str) -> Self {
        Self { label: label.into(), description: desc.into(), enabled: true }
    }
    pub fn disabled(label: &str, desc: &str) -> Self {
        Self { label: label.into(), description: desc.into(), enabled: false }
    }
}

pub struct MenuState {
    pub items: Vec<MenuItem>,
    pub list_state: ListState,
    pub title: String,
}

impl MenuState {
    pub fn new(title: &str, items: Vec<MenuItem>) -> Self {
        let mut list_state = ListState::default();
        // select first enabled item
        let first = items.iter().position(|i| i.enabled).unwrap_or(0);
        list_state.select(Some(first));
        Self { items, list_state, title: title.into() }
    }

    pub fn selected_index(&self) -> Option<usize> {
        self.list_state.selected()
    }

    pub fn selected_label(&self) -> Option<&str> {
        self.list_state.selected().and_then(|i| self.items.get(i)).map(|item| item.label.as_str())
    }

    pub fn handle_key(&mut self, key: KeyEvent) -> Option<usize> {
        match key.code {
            KeyCode::Up | KeyCode::Char('k') => { self.move_up(); None }
            KeyCode::Down | KeyCode::Char('j') => { self.move_down(); None }
            KeyCode::Enter | KeyCode::Char(' ') => {
                if let Some(i) = self.list_state.selected() {
                    if self.items.get(i).map(|item| item.enabled).unwrap_or(false) {
                        return Some(i);
                    }
                }
                None
            }
            _ => None,
        }
    }

    fn move_up(&mut self) {
        let current = self.list_state.selected().unwrap_or(0);
        for offset in 1..self.items.len() {
            let idx = (current + self.items.len() - offset) % self.items.len();
            if self.items[idx].enabled {
                self.list_state.select(Some(idx));
                return;
            }
        }
    }

    fn move_down(&mut self) {
        let current = self.list_state.selected().unwrap_or(0);
        for offset in 1..self.items.len() {
            let idx = (current + offset) % self.items.len();
            if self.items[idx].enabled {
                self.list_state.select(Some(idx));
                return;
            }
        }
    }

    pub fn render(&mut self, f: &mut Frame, area: Rect) {
        let items: Vec<ListItem> = self.items.iter().enumerate().map(|(i, item)| {
            let is_selected = self.list_state.selected() == Some(i);
            let style = if !item.enabled {
                theme::dim()
            } else if is_selected {
                theme::selected()
            } else {
                theme::normal()
            };
            let prefix = if is_selected && item.enabled { "> " } else { "  " };
            let desc = if item.description.is_empty() { String::new() } else { format!("  {}", item.description) };
            ListItem::new(Line::from(vec![
                Span::styled(format!("{}{}", prefix, item.label), style),
                Span::styled(desc, theme::dim()),
            ]))
        }).collect();
        let block = Block::default()
            .title(Span::styled(format!(" {} ", self.title), theme::title()))
            .borders(Borders::ALL)
            .border_style(theme::border());
        let list = List::new(items).block(block);
        f.render_stateful_widget(list, area, &mut self.list_state);
    }
}
