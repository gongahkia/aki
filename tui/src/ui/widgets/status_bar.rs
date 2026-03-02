use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::Paragraph;
use crate::ui::theme;

pub struct StatusBar {
    pub provider: String,
    pub model: String,
    pub corpus_count: u64,
    pub search_indexed: bool,
    pub api_ok: bool,
    pub last_score: Option<f64>,
}

impl Default for StatusBar {
    fn default() -> Self {
        Self {
            provider: "ollama".into(),
            model: "--".into(),
            corpus_count: 0,
            search_indexed: false,
            api_ok: false,
            last_score: None,
        }
    }
}

impl StatusBar {
    pub fn render(&self, f: &mut Frame, area: Rect) {
        let api_status = if self.api_ok { theme::STATUS_OK } else { theme::STATUS_ERROR };
        let search = if self.search_indexed { "indexed" } else { "off" };
        let score = self.last_score.map(|s| format!("{:.1}", s)).unwrap_or_else(|| "--".into());
        let line = Line::from(vec![
            Span::styled(format!(" {}/{}", self.provider, self.model), theme::normal()),
            Span::styled(" | ", theme::dim()),
            Span::styled(format!("Corpus: {}", self.corpus_count), theme::normal()),
            Span::styled(" | ", theme::dim()),
            Span::styled(format!("Search: {}", search), theme::normal()),
            Span::styled(" | ", theme::dim()),
            Span::styled(format!("Score: {}", score), theme::normal()),
            Span::styled(" | ", theme::dim()),
            Span::styled(format!("API: {} ", api_status), if self.api_ok { theme::success() } else { theme::error() }),
        ]);
        f.render_widget(Paragraph::new(line).style(theme::dim()), area);
    }
}
