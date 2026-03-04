use ratatui::layout::{Constraint, Direction, Layout, Rect};

/// split frame into [breadcrumb(1) | body(fill) | status(1)]
pub fn main_layout(area: Rect) -> (Rect, Rect, Rect) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1), // breadcrumb
            Constraint::Min(3),    // body
            Constraint::Length(1), // status bar
        ])
        .split(area);
    (chunks[0], chunks[1], chunks[2])
}

/// center a block of given width/height inside area
pub fn centered_rect(width: u16, height: u16, area: Rect) -> Rect {
    let x = area.x + area.width.saturating_sub(width) / 2;
    let y = area.y + area.height.saturating_sub(height) / 2;
    Rect::new(x, y, width.min(area.width), height.min(area.height))
}
