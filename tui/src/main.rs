mod api;
mod app;
mod config;
mod event;
mod screens;
mod state;
mod ui;

use std::io;
use std::time::Duration;
use anyhow::Result;
use clap::Parser;
use crossterm::{
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::backend::CrosstermBackend;
use ratatui::Terminal;
use crate::config::Config;

#[tokio::main]
async fn main() -> Result<()> {
    let cfg = Config::parse();
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.clear()?;
    let mut app = app::App::new(cfg.api_url);
    let tick_rate = Duration::from_millis(100);
    while app.running {
        terminal.draw(|f| app.draw(f))?;
        if let Some(evt) = event::poll_event(tick_rate) {
            match evt {
                event::AppEvent::Key(key) => app.handle_key(key),
                event::AppEvent::Tick => app.tick(),
                event::AppEvent::Resize(_, _) => {} // terminal auto-redraws
            }
        }
    }
    disable_raw_mode()?;
    execute!(io::stdout(), LeaveAlternateScreen)?;
    Ok(())
}
