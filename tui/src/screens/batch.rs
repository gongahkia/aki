use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crossterm::event::{KeyCode, KeyEvent};
use ratatui::layout::Rect;
use ratatui::Frame;

pub struct BatchScreen {
    menu: MenuState,
}

impl BatchScreen {
    pub fn new() -> Self {
        let items = vec![
            MenuItem::new("Batch Generate", "generate multiple hypotheticals"),
            MenuItem::new("Import SG Cases", "scrape and add to corpus"),
            MenuItem::new("Bulk Label", "label multiple entries"),
        ];
        Self {
            menu: MenuState::new("Batch Operations", items),
        }
    }
}

impl Screen for BatchScreen {
    fn name(&self) -> &str {
        "Batch Operations"
    }

    fn handle_key(&mut self, key: KeyEvent, _ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        if let Some(idx) = self.menu.handle_key(key) {
            match idx {
                0 => ScreenAction::Push(Box::new(super::generate::GenerateScreen::new())),
                1 => ScreenAction::Push(Box::new(super::scrape::ScrapeScreen::new())),
                2 => ScreenAction::Push(Box::new(super::corpus::LabelScreen::new())),
                _ => ScreenAction::None,
            }
        } else {
            ScreenAction::None
        }
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        self.menu.render(f, area);
    }
}
