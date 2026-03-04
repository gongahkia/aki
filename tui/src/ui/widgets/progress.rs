use crate::ui::theme;
use ratatui::layout::Rect;
use ratatui::style::Style;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Gauge};
use ratatui::Frame;

pub struct ProgressBar {
    pub label: String,
    pub progress: f64,
    pub message: String,
}

impl ProgressBar {
    pub fn new(label: &str) -> Self {
        Self {
            label: label.into(),
            progress: 0.0,
            message: String::new(),
        }
    }

    pub fn set(&mut self, progress: f64, message: &str) {
        self.progress = progress.clamp(0.0, 1.0);
        self.message = message.into();
    }

    pub fn render(&self, f: &mut Frame, area: Rect) {
        let block = Block::default()
            .title(Span::styled(format!(" {} ", self.label), theme::title()))
            .borders(Borders::ALL)
            .border_style(theme::border());
        let pct = (self.progress * 100.0) as u16;
        let gauge = Gauge::default()
            .block(block)
            .gauge_style(theme::success())
            .percent(pct)
            .label(Span::styled(
                format!("{}% {}", pct, self.message),
                theme::normal(),
            ));
        f.render_widget(gauge, area);
    }
}

pub struct Spinner {
    pub label: String,
    pub frame: usize,
}

impl Spinner {
    const FRAMES: &'static [&'static str] = &["|", "/", "-", "\\"];

    pub fn new(label: &str) -> Self {
        Self {
            label: label.into(),
            frame: 0,
        }
    }
    pub fn tick(&mut self) {
        self.frame = (self.frame + 1) % Self::FRAMES.len();
    }

    pub fn render(&self, f: &mut Frame, area: Rect) {
        let accent = Style::default().fg(theme::ACCENT);
        let line = Line::from(vec![
            Span::styled(format!(" {} ", Self::FRAMES[self.frame]), accent),
            Span::styled(&self.label, theme::normal()),
        ]);
        f.render_widget(ratatui::widgets::Paragraph::new(line), area);
    }
}
