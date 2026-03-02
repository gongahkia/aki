use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use crate::ui::theme;

pub struct Panel {
    pub title: String,
    pub content: String,
    pub scroll: u16,
}

impl Panel {
    pub fn new(title: &str, content: &str) -> Self {
        Self { title: title.into(), content: content.into(), scroll: 0 }
    }

    pub fn scroll_up(&mut self) { self.scroll = self.scroll.saturating_sub(1); }
    pub fn scroll_down(&mut self) { self.scroll += 1; }

    pub fn render(&self, f: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(Span::styled(format!(" {} ", self.title), theme::title()))
            .borders(Borders::ALL)
            .border_style(theme::border());
        let p = Paragraph::new(self.content.as_str())
            .wrap(Wrap { trim: false })
            .scroll((self.scroll, 0))
            .block(block);
        f.render_widget(p, area);
    }
}
