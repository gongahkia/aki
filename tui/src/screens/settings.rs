use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::state::generation::TuiState;
use crate::ui::theme;
use crate::ui::widgets::menu::{MenuItem, MenuState};

enum Phase {
    List(MenuState),
    View(String),
}

pub struct SettingsScreen {
    phase: Phase,
}

impl SettingsScreen {
    pub fn new() -> Self {
        let items = vec![
            MenuItem::new("View Current Settings", "show all configuration"),
            MenuItem::new("Reset Defaults", "restore default generation config"),
        ];
        Self { phase: Phase::List(MenuState::new("Settings", items)) }
    }
}

impl Screen for SettingsScreen {
    fn name(&self) -> &str { "Settings" }

    fn handle_key(&mut self, key: KeyEvent, _ctx: &mut AppContext) -> ScreenAction {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => return ScreenAction::Pop,
            _ => {}
        }
        match &mut self.phase {
            Phase::List(menu) => {
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => {
                            let state = TuiState::load();
                            let text = format!(
                                "Provider: {}\nModel: {}\nTemperature: {:.1}\nComplexity: {}\nParties: {}\nMethod: {}\nInclude Analysis: {}",
                                state.last_config.provider,
                                state.last_config.model.as_deref().unwrap_or("default"),
                                state.last_config.temperature,
                                state.last_config.complexity,
                                state.last_config.parties,
                                state.last_config.method,
                                if state.last_config.include_analysis { "yes" } else { "no" },
                            );
                            self.phase = Phase::View(text);
                        }
                        1 => {
                            let state = TuiState::default();
                            state.save();
                            self.phase = Phase::View("Defaults restored.".into());
                        }
                        _ => {}
                    }
                }
            }
            Phase::View(_) => {
                if key.code == KeyCode::Esc || key.code == KeyCode::Enter || key.code == KeyCode::Backspace {
                    self.phase = Phase::List(MenuState::new("Settings", vec![
                        MenuItem::new("View Current Settings", "show all configuration"),
                        MenuItem::new("Reset Defaults", "restore default generation config"),
                    ]));
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::List(menu) => menu.render(f, area),
            Phase::View(text) => {
                let block = Block::default().title(Span::styled(" Settings ", theme::title()))
                    .borders(Borders::ALL).border_style(theme::border());
                f.render_widget(Paragraph::new(text.as_str()).wrap(Wrap { trim: false }).block(block), area);
            }
        }
    }
}
