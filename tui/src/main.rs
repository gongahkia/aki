mod api;
mod async_join;
mod app;
mod config;
mod event;
mod screens;
mod state;
mod ui;

use std::io;
use std::io::Write;
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

struct TerminalGuard {
    raw_mode_enabled: bool,
    alt_screen_enabled: bool,
}

impl TerminalGuard {
    fn new() -> Self {
        Self { raw_mode_enabled: false, alt_screen_enabled: false }
    }

    fn enable_raw_mode(&mut self) -> io::Result<()> {
        enable_raw_mode()?;
        self.raw_mode_enabled = true;
        Ok(())
    }

    fn enter_alt_screen<W: Write>(&mut self, writer: &mut W) -> io::Result<()> {
        execute!(writer, EnterAlternateScreen)?;
        self.alt_screen_enabled = true;
        Ok(())
    }

    fn restore(&mut self) {
        if self.raw_mode_enabled {
            let _ = disable_raw_mode();
            self.raw_mode_enabled = false;
        }
        if self.alt_screen_enabled {
            let _ = execute!(io::stdout(), LeaveAlternateScreen);
            self.alt_screen_enabled = false;
        }
    }
}

impl Drop for TerminalGuard {
    fn drop(&mut self) {
        self.restore();
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let cfg = Config::parse();
    let mut terminal_guard = TerminalGuard::new();
    terminal_guard.enable_raw_mode()?;
    let mut stdout = io::stdout();
    terminal_guard.enter_alt_screen(&mut stdout)?;
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
    terminal.show_cursor()?;
    Ok(())
}
