use std::io::{self, BufRead, BufReader, Write};
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

use anyhow::{Context, Result};
use crossterm::{
    event::{self, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Frame, Terminal,
};

#[derive(Clone)]
enum Entry {
    Out(String),  // uvicorn stdout (white)
    Err(String),  // uvicorn stderr (yellow — most uvicorn output goes here)
    Sys(String),  // monitor messages (dark gray italic)
}

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

fn main() -> Result<()> {
    let mut child = Command::new("uvicorn")
        .args(["src.api.main:app", "--host", "127.0.0.1", "--port", "8000"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .context("failed to spawn uvicorn — is it installed and on PATH?")?;

    let (tx, rx) = mpsc::channel::<Entry>();

    {
        let tx = tx.clone();
        let pipe = child.stdout.take().unwrap();
        thread::spawn(move || {
            BufReader::new(pipe)
                .lines()
                .flatten()
                .for_each(|l| { let _ = tx.send(Entry::Out(l)); });
        });
    }
    {
        let tx = tx.clone();
        let pipe = child.stderr.take().unwrap();
        thread::spawn(move || {
            BufReader::new(pipe)
                .lines()
                .flatten()
                .for_each(|l| { let _ = tx.send(Entry::Err(l)); });
        });
    }

    let mut terminal_guard = TerminalGuard::new();
    terminal_guard.enable_raw_mode()?;
    let mut stdout = io::stdout();
    terminal_guard.enter_alt_screen(&mut stdout)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut logs: Vec<Entry> = vec![
        Entry::Sys("jikai api monitor  •  uvicorn src.api.main:app --host 127.0.0.1 --port 8000".into()),
        Entry::Sys("q / ctrl+c: stop & exit  |  ↑↓ / pgup/pgdn: scroll  |  home: top  |  end: auto-scroll".into()),
        Entry::Sys("─".repeat(80)),
    ];
    let mut scroll: usize = 0;
    let mut auto_scroll = true;
    let mut api_running = true;

    loop {
        while let Ok(e) = rx.try_recv() {
            logs.push(e);
        }

        if api_running {
            match child.try_wait() {
                Ok(Some(st)) => {
                    api_running = false;
                    logs.push(Entry::Sys(format!("process exited  code={:?}", st.code())));
                }
                Ok(None) => {}
                Err(e) => {
                    api_running = false;
                    logs.push(Entry::Sys(format!("wait error: {e}")));
                }
            }
        }

        if auto_scroll {
            let h = terminal.size()?.height as usize;
            let visible = h.saturating_sub(6); // header(3) + footer(1) + log borders(2)
            scroll = logs.len().saturating_sub(visible);
        }

        let snap_scroll = scroll;
        let snap_total = logs.len();
        terminal.draw(|f| draw(f, &logs, snap_scroll, auto_scroll, api_running, snap_total))?;

        if event::poll(Duration::from_millis(50))? {
            if let Event::Key(k) = event::read()? {
                let h = terminal.size()?.height as usize;
                let visible = h.saturating_sub(6);
                match k.code {
                    KeyCode::Char('q') => {
                        if api_running { let _ = child.kill(); }
                        break;
                    }
                    KeyCode::Char('c') if k.modifiers.contains(KeyModifiers::CONTROL) => {
                        if api_running { let _ = child.kill(); }
                        break;
                    }
                    KeyCode::Up => {
                        auto_scroll = false;
                        scroll = scroll.saturating_sub(1);
                    }
                    KeyCode::Down => {
                        scroll += 1;
                        let max = logs.len().saturating_sub(visible);
                        if scroll >= max { scroll = max; auto_scroll = true; }
                    }
                    KeyCode::Home => { auto_scroll = false; scroll = 0; }
                    KeyCode::End => { auto_scroll = true; }
                    KeyCode::PageUp => {
                        auto_scroll = false;
                        scroll = scroll.saturating_sub(visible);
                    }
                    KeyCode::PageDown => {
                        let max = logs.len().saturating_sub(visible);
                        scroll = (scroll + visible).min(max);
                        if scroll >= max { auto_scroll = true; }
                    }
                    _ => {}
                }
            }
        }
    }

    terminal.show_cursor()?;
    Ok(())
}

fn draw(
    f: &mut Frame,
    logs: &[Entry],
    scroll: usize,
    auto_scroll: bool,
    api_running: bool,
    total: usize,
) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // header
            Constraint::Min(1),    // log view
            Constraint::Length(1), // footer
        ])
        .split(f.area());

    // header
    let status = if api_running {
        Span::styled("● RUNNING", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD))
    } else {
        Span::styled("■ STOPPED", Style::default().fg(Color::Red).add_modifier(Modifier::BOLD))
    };
    let scroll_tag = if !auto_scroll {
        Span::styled("  [scroll]", Style::default().fg(Color::Yellow))
    } else {
        Span::raw("")
    };
    let header = Paragraph::new(Line::from(vec![
        Span::styled("Jikai API", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        Span::raw("  127.0.0.1:8000  "),
        status,
        scroll_tag,
    ]))
    .block(Block::default().borders(Borders::ALL));
    f.render_widget(header, chunks[0]);

    // log list
    let inner_h = chunks[1].height.saturating_sub(2) as usize;
    let items: Vec<ListItem> = logs.iter().skip(scroll).take(inner_h).map(|e| {
        match e {
            Entry::Out(s) => ListItem::new(Line::from(Span::raw(s.as_str()))),
            Entry::Err(s) => ListItem::new(Line::from(
                Span::styled(s.as_str(), Style::default().fg(Color::Yellow))
            )),
            Entry::Sys(s) => ListItem::new(Line::from(
                Span::styled(s.as_str(), Style::default().fg(Color::DarkGray).add_modifier(Modifier::ITALIC))
            )),
        }
    }).collect();
    let log_title = format!(" logs  {}/{} ", scroll + inner_h.min(total.saturating_sub(scroll)), total);
    let log_list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title(log_title.as_str()));
    f.render_widget(log_list, chunks[1]);

    // footer
    let footer = Paragraph::new(
        "q/ctrl+c stop  |  ↑↓ scroll  |  pgup/pgdn page  |  home top  |  end auto-scroll"
    ).style(Style::default().fg(Color::DarkGray));
    f.render_widget(footer, chunks[2]);
}
