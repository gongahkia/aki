use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::theme;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crossterm::event::{KeyCode, KeyEvent};
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;

enum Phase {
    StepSelect(MenuState, usize),
    Done,
}

pub struct GuidedScreen {
    phase: Phase,
}

impl GuidedScreen {
    pub fn new() -> Self {
        let items = vec![
            MenuItem::new("Step 1: Check Corpus", "verify corpus is ready"),
            MenuItem::new("Step 2: Preprocess (if needed)", "import raw files"),
            MenuItem::new("Step 3: Generate Hypothetical", "create a scenario"),
            MenuItem::new("Step 4: Export", "save to DOCX/PDF"),
        ];
        Self {
            phase: Phase::StepSelect(MenuState::new("Guided Walkthrough", items), 0),
        }
    }
}

impl Screen for GuidedScreen {
    fn name(&self) -> &str {
        "Guided Mode"
    }

    fn handle_key(&mut self, key: KeyEvent, _ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        match &mut self.phase {
            Phase::StepSelect(menu, _step) => {
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => {
                            return ScreenAction::Push(Box::new(super::corpus::BrowseScreen::new()))
                        }
                        1 => {
                            return ScreenAction::Push(Box::new(
                                super::preprocess::PreprocessScreen::new(),
                            ))
                        }
                        2 => {
                            return ScreenAction::Push(Box::new(
                                super::generate::GenerateScreen::new(),
                            ))
                        }
                        3 => {
                            return ScreenAction::Push(Box::new(super::export::ExportScreen::new()))
                        }
                        _ => {}
                    }
                }
            }
            Phase::Done => {
                if key.code == KeyCode::Enter {
                    return ScreenAction::Pop;
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::StepSelect(menu, _) => menu.render(f, area),
            Phase::Done => {
                let block = Block::default()
                    .title(Span::styled(" Complete ", theme::success()))
                    .borders(Borders::ALL);
                f.render_widget(
                    Paragraph::new("Guided walkthrough complete.").block(block),
                    area,
                );
            }
        }
    }
}
