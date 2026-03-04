use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crossterm::event::{KeyCode, KeyEvent};
use ratatui::layout::Rect;
use ratatui::Frame;

pub struct MoreScreen {
    menu: MenuState,
}

impl MoreScreen {
    pub fn new() -> Self {
        let items = vec![
            MenuItem::new("History", "browse past generations"),
            MenuItem::new("Statistics", "generation metrics dashboard"),
            MenuItem::new("Providers", "LLM provider health and selection"),
            MenuItem::new("Settings", "configuration and API keys"),
            MenuItem::new("Batch Operations", "bulk generate, import, label"),
            MenuItem::new("Guided Mode", "step-by-step walkthrough"),
            MenuItem::new("Cleanup", "remove logs, models, cache"),
        ];
        Self {
            menu: MenuState::new("More", items),
        }
    }
}

impl Screen for MoreScreen {
    fn name(&self) -> &str {
        "More"
    }

    fn handle_key(&mut self, key: KeyEvent, _ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        if let Some(idx) = self.menu.handle_key(key) {
            match idx {
                0 => ScreenAction::Push(Box::new(super::history::HistoryScreen::new())),
                1 => ScreenAction::Push(Box::new(super::stats::StatsScreen::new())),
                2 => ScreenAction::Push(Box::new(super::providers::ProvidersScreen::new())),
                3 => ScreenAction::Push(Box::new(super::settings::SettingsScreen::new())),
                4 => ScreenAction::Push(Box::new(super::batch::BatchScreen::new())),
                5 => ScreenAction::Push(Box::new(super::guided::GuidedScreen::new())),
                6 => ScreenAction::Push(Box::new(super::cleanup::CleanupScreen::new())),
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
