use crossterm::event::{self, Event, KeyEvent};
use std::time::Duration;

pub enum AppEvent {
    Key(KeyEvent),
    Tick,
    Resize(u16, u16),
}

pub fn poll_event(tick_rate: Duration) -> Option<AppEvent> {
    if event::poll(tick_rate).unwrap_or(false) {
        match event::read() {
            Ok(Event::Key(key)) => Some(AppEvent::Key(key)),
            Ok(Event::Resize(w, h)) => Some(AppEvent::Resize(w, h)),
            _ => None,
        }
    } else {
        Some(AppEvent::Tick)
    }
}
