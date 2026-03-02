use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use crate::ui::theme;

/// live-updating text area for streaming LLM tokens
pub struct StreamView {
    pub buffer: String,
    pub scroll: u16,
    pub paused: bool,
    pub done: bool,
    pub token_count: usize,
    pub title: String,
}

impl StreamView {
    pub fn new(title: &str) -> Self {
        Self {
            buffer: String::new(),
            scroll: 0,
            paused: false,
            done: false,
            token_count: 0,
            title: title.into(),
        }
    }

    pub fn append(&mut self, text: &str) {
        self.buffer.push_str(text);
        self.token_count += 1;
        // auto-scroll to bottom
        let lines = self.buffer.lines().count() as u16;
        self.scroll = lines.saturating_sub(1);
    }

    pub fn toggle_pause(&mut self) { self.paused = !self.paused; }

    pub fn scroll_up(&mut self) { self.scroll = self.scroll.saturating_sub(1); }
    pub fn scroll_down(&mut self) { self.scroll += 1; }

    pub fn render(&self, f: &mut Frame, area: Rect) {
        let status = if self.done {
            format!("complete -- {} tokens", self.token_count)
        } else if self.paused {
            "paused (Space to resume)".into()
        } else {
            format!("streaming... {} tokens", self.token_count)
        };
        let block = Block::default()
            .title(Span::styled(format!(" {} ", self.title), theme::title()))
            .title_bottom(Span::styled(format!(" {} ", status), theme::dim()))
            .borders(Borders::ALL)
            .border_style(if self.done { theme::success() } else { theme::border() });
        let content = if self.buffer.is_empty() { "waiting for response..." } else { &self.buffer };
        let p = Paragraph::new(content)
            .wrap(Wrap { trim: false })
            .scroll((self.scroll, 0))
            .block(block);
        f.render_widget(p, area);
    }
}
