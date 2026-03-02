use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::menu::{MenuItem, MenuState};

pub struct MainMenuScreen {
    menu: MenuState,
}

impl MainMenuScreen {
    pub fn new() -> Self {
        let items = vec![
            MenuItem::new("Generate Hypothetical", "create tort law scenarios"),
            MenuItem::new("Browse Corpus", "view and search entries"),
            MenuItem::new("Import & Preprocess", "OCR raw files into corpus"),
            MenuItem::new("Scrape SG Case Law", "fetch from legal databases"),
            MenuItem::new("Label Corpus", "tag entries with topics and quality"),
            MenuItem::new("Train ML Models", "classifier, regressor, clusterer"),
            MenuItem::new("Index Semantic Search", "embed corpus into vector store"),
            MenuItem::new("Export", "save generation to DOCX/PDF"),
            MenuItem::new("More", "history, stats, providers, settings, batch"),
        ];
        Self { menu: MenuState::new("Jikai", items) }
    }
}

impl Screen for MainMenuScreen {
    fn name(&self) -> &str { "Main" }

    fn handle_key(&mut self, key: KeyEvent, _ctx: &mut AppContext) -> ScreenAction {
        // global shortcuts
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc => return ScreenAction::Quit,
            KeyCode::Char('g') => return ScreenAction::Push(Box::new(super::generate::GenerateScreen::new())),
            KeyCode::Char('h') => return ScreenAction::Push(Box::new(super::history::HistoryScreen::new())),
            _ => {}
        }
        if let Some(idx) = self.menu.handle_key(key) {
            match idx {
                0 => ScreenAction::Push(Box::new(super::generate::GenerateScreen::new())),
                1 => ScreenAction::Push(Box::new(super::corpus::BrowseScreen::new())),
                2 => ScreenAction::Push(Box::new(super::preprocess::PreprocessScreen::new())),
                3 => ScreenAction::Push(Box::new(super::scrape::ScrapeScreen::new())),
                4 => ScreenAction::Push(Box::new(super::corpus::LabelScreen::new())),
                5 => ScreenAction::Push(Box::new(super::train::TrainScreen::new())),
                6 => ScreenAction::Push(Box::new(super::embed::EmbedScreen::new())),
                7 => ScreenAction::Push(Box::new(super::export::ExportScreen::new())),
                8 => ScreenAction::Push(Box::new(super::more::MoreScreen::new())),
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
