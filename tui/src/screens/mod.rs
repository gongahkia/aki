pub mod batch;
pub mod chat;
pub mod cleanup;
pub mod corpus;
pub mod embed;
pub mod export;
pub mod generate;
pub mod guided;
pub mod history;
pub mod main_menu;
pub mod more;
pub mod preprocess;
pub mod providers;
pub mod scrape;
pub mod settings;
pub mod stats;
pub mod train;

use crate::app::AppContext;
use crossterm::event::KeyEvent;
use ratatui::layout::Rect;
use ratatui::Frame;

/// unified screen trait
pub trait Screen {
    fn name(&self) -> &str;
    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction;
    fn render(&mut self, f: &mut Frame, area: Rect, ctx: &AppContext);
    fn on_enter(&mut self, _ctx: &mut AppContext) {} // called when screen is pushed
    fn tick(&mut self, _ctx: &mut AppContext) {} // called on timer
}

pub enum ScreenAction {
    None,
    Push(Box<dyn Screen + Send>),
    Pop,
    Replace(Box<dyn Screen + Send>),
    Quit,
}
