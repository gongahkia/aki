use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crossterm::event::{KeyCode, KeyEvent};
use ratatui::layout::Rect;
use ratatui::Frame;

enum Phase {
    Menu(MenuState),
    ConfirmQuit(MenuState),
}

pub struct MainMenuScreen {
    phase: Phase,
}

fn main_items() -> Vec<MenuItem> {
    vec![
        MenuItem::new("Generate Hypothetical", "create tort law scenarios"),
        MenuItem::new("Chat", "CLI-style chatbot and /hypo workflow"),
        MenuItem::new("Browse Corpus", "view and search entries"),
        MenuItem::new("Import & Preprocess", "OCR raw files into corpus"),
        MenuItem::new("Scrape SG Case Law", "fetch from legal databases"),
        MenuItem::new("Label Corpus", "tag entries with topics and quality"),
        MenuItem::new("Index Semantic Search", "embed corpus into vector store"),
        MenuItem::new("Export", "save generation to DOCX/PDF"),
        MenuItem::new("More", "history, stats, providers, settings, batch"),
    ]
}

fn quit_menu() -> MenuState {
    MenuState::new(
        "Exit Jikai?",
        vec![
            MenuItem::new("Clean & Exit", "remove generated files, then quit"),
            MenuItem::new("Exit", "quit without cleaning"),
            MenuItem::new("Cancel", "return to menu"),
        ],
    )
}

impl MainMenuScreen {
    pub fn new() -> Self {
        Self {
            phase: Phase::Menu(MenuState::new("Jikai", main_items())),
        }
    }
}

impl Screen for MainMenuScreen {
    fn name(&self) -> &str {
        "Main"
    }

    fn handle_key(&mut self, key: KeyEvent, _ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::Menu(menu) => {
                match key.code {
                    KeyCode::Char('q') | KeyCode::Esc => {
                        self.phase = Phase::ConfirmQuit(quit_menu());
                        return ScreenAction::None;
                    }
                    KeyCode::Char('g') => {
                        return ScreenAction::Push(Box::new(super::generate::GenerateScreen::new()))
                    }
                    KeyCode::Char('c') => {
                        return ScreenAction::Push(Box::new(super::chat::ChatScreen::new()))
                    }
                    KeyCode::Char('h') => {
                        return ScreenAction::Push(Box::new(super::history::HistoryScreen::new()))
                    }
                    _ => {}
                }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => ScreenAction::Push(Box::new(super::generate::GenerateScreen::new())),
                        1 => ScreenAction::Push(Box::new(super::chat::ChatScreen::new())),
                        2 => ScreenAction::Push(Box::new(super::corpus::BrowseScreen::new())),
                        3 => {
                            ScreenAction::Push(Box::new(super::preprocess::PreprocessScreen::new()))
                        }
                        4 => ScreenAction::Push(Box::new(super::scrape::ScrapeScreen::new())),
                        5 => ScreenAction::Push(Box::new(super::corpus::LabelScreen::new())),
                        6 => ScreenAction::Push(Box::new(super::embed::EmbedScreen::new())),
                        7 => ScreenAction::Push(Box::new(super::export::ExportScreen::new())),
                        8 => ScreenAction::Push(Box::new(super::more::MoreScreen::new())),
                        _ => ScreenAction::None,
                    }
                } else {
                    ScreenAction::None
                }
            }
            Phase::ConfirmQuit(menu) => {
                if key.code == KeyCode::Esc {
                    self.phase = Phase::Menu(MenuState::new("Jikai", main_items()));
                    return ScreenAction::None;
                }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => {
                            // clean & exit
                            self.phase = Phase::Menu(MenuState::new("Jikai", main_items()));
                            return ScreenAction::Push(Box::new(
                                super::cleanup::CleanupScreen::new_for_exit(),
                            ));
                        }
                        1 => return ScreenAction::Quit, // exit
                        _ => self.phase = Phase::Menu(MenuState::new("Jikai", main_items())), // cancel
                    }
                }
                ScreenAction::None
            }
        }
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Menu(menu) => menu.render(f, area),
            Phase::ConfirmQuit(confirm) => confirm.render(f, area),
        }
    }
}
