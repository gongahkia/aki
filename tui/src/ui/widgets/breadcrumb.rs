use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::Paragraph;
use crate::ui::theme;

pub fn render_breadcrumb(f: &mut Frame, area: Rect, path: &str) {
    let line = Line::from(vec![
        Span::styled(" ", theme::dim()),
        Span::styled(path, theme::dim()),
    ]);
    f.render_widget(Paragraph::new(line), area);
}
