use ratatui::style::{Color, Modifier, Style};

// -- base palette (no emojis, ASCII indicators only) --
pub const BG: Color = Color::Reset;
pub const FG: Color = Color::White;
pub const DIM: Color = Color::DarkGray;
pub const ACCENT: Color = Color::Cyan;
pub const SUCCESS: Color = Color::Green;
pub const WARN: Color = Color::Yellow;
pub const ERROR: Color = Color::Red;
pub const HIGHLIGHT_BG: Color = Color::DarkGray;

// -- semantic styles --
pub fn title() -> Style {
    Style::default().fg(ACCENT).add_modifier(Modifier::BOLD)
}
pub fn subtitle() -> Style {
    Style::default()
        .fg(Color::White)
        .add_modifier(Modifier::BOLD)
}
pub fn normal() -> Style {
    Style::default().fg(FG)
}
pub fn dim() -> Style {
    Style::default().fg(DIM)
}
pub fn selected() -> Style {
    Style::default().fg(Color::Black).bg(ACCENT)
}
pub fn success() -> Style {
    Style::default().fg(SUCCESS)
}
pub fn warn() -> Style {
    Style::default().fg(WARN)
}
pub fn error() -> Style {
    Style::default().fg(ERROR)
}
pub fn input() -> Style {
    Style::default().fg(Color::White).bg(Color::DarkGray)
}
pub fn border() -> Style {
    Style::default().fg(Color::DarkGray)
}
pub fn header() -> Style {
    Style::default().fg(ACCENT).add_modifier(Modifier::BOLD)
}

// -- status indicators (ASCII only) --
pub const STATUS_OK: &str = "[*]";
pub const STATUS_PENDING: &str = "[ ]";
pub const STATUS_WARN: &str = "[!]";
pub const STATUS_ERROR: &str = "[x]";
pub const SEPARATOR: &str = "--";
