use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, List, ListItem, ListState};
use crate::ui::theme;

pub struct CheckboxItem {
    pub label: String,
    pub value: String,
    pub description: String,
    pub checked: bool,
    pub is_header: bool, // category separator, not selectable
}

impl CheckboxItem {
    pub fn option(label: &str, value: &str, desc: &str) -> Self {
        Self { label: label.into(), value: value.into(), description: desc.into(), checked: false, is_header: false }
    }
    pub fn header(label: &str) -> Self {
        Self { label: label.into(), value: String::new(), description: String::new(), checked: false, is_header: true }
    }
}

pub struct CheckboxState {
    pub items: Vec<CheckboxItem>,
    pub list_state: ListState,
    pub title: String,
}

impl CheckboxState {
    pub fn new(title: &str, items: Vec<CheckboxItem>) -> Self {
        let mut list_state = ListState::default();
        let first = items.iter().position(|i| !i.is_header).unwrap_or(0);
        list_state.select(Some(first));
        Self { items, list_state, title: title.into() }
    }

    pub fn selected_values(&self) -> Vec<String> {
        self.items.iter().filter(|i| i.checked && !i.is_header).map(|i| i.value.clone()).collect()
    }

    /// returns true if user pressed Enter to confirm
    pub fn handle_key(&mut self, key: KeyEvent) -> bool {
        match key.code {
            KeyCode::Up | KeyCode::Char('k') => { self.move_up(); false }
            KeyCode::Down | KeyCode::Char('j') => { self.move_down(); false }
            KeyCode::Char(' ') => { self.toggle(); false }
            KeyCode::Char('a') => { // toggle all
                let all_checked = self.items.iter().filter(|i| !i.is_header).all(|i| i.checked);
                for item in &mut self.items {
                    if !item.is_header { item.checked = !all_checked; }
                }
                false
            }
            KeyCode::Enter => true,
            _ => false,
        }
    }

    fn toggle(&mut self) {
        if let Some(i) = self.list_state.selected() {
            if let Some(item) = self.items.get_mut(i) {
                if !item.is_header { item.checked = !item.checked; }
            }
        }
    }

    fn move_up(&mut self) {
        let current = self.list_state.selected().unwrap_or(0);
        for offset in 1..self.items.len() {
            let idx = (current + self.items.len() - offset) % self.items.len();
            if !self.items[idx].is_header {
                self.list_state.select(Some(idx));
                return;
            }
        }
    }

    fn move_down(&mut self) {
        let current = self.list_state.selected().unwrap_or(0);
        for offset in 1..self.items.len() {
            let idx = (current + offset) % self.items.len();
            if !self.items[idx].is_header {
                self.list_state.select(Some(idx));
                return;
            }
        }
    }

    pub fn render(&mut self, f: &mut Frame, area: Rect) {
        let items: Vec<ListItem> = self.items.iter().enumerate().map(|(i, item)| {
            let is_selected = self.list_state.selected() == Some(i);
            if item.is_header {
                return ListItem::new(Line::from(vec![
                    Span::styled(format!("  {} {}", theme::SEPARATOR, item.label), theme::header()),
                ]));
            }
            let check = if item.checked { "[x]" } else { "[ ]" };
            let style = if is_selected { theme::selected() } else { theme::normal() };
            let prefix = if is_selected { "> " } else { "  " };
            let desc = if item.description.is_empty() { String::new() } else { format!("  {}", item.description) };
            ListItem::new(Line::from(vec![
                Span::styled(format!("{}{} {}", prefix, check, item.label), style),
                Span::styled(desc, theme::dim()),
            ]))
        }).collect();
        let block = Block::default()
            .title(Span::styled(format!(" {} ", self.title), theme::title()))
            .borders(Borders::ALL)
            .border_style(theme::border());
        let hint = Line::from(vec![
            Span::styled(" Space=toggle  a=all  Enter=confirm  Esc=back ", theme::dim()),
        ]);
        let list = List::new(items).block(block);
        f.render_stateful_widget(list, area, &mut self.list_state);
        // render hint at bottom of area if space allows
        if area.height > 2 {
            let hint_area = Rect::new(area.x, area.y + area.height - 1, area.width, 1);
            f.render_widget(ratatui::widgets::Paragraph::new(hint), hint_area);
        }
    }
}
