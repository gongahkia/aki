use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use ratatui::Frame;
use crate::screens::{Screen, ScreenAction};
use crate::screens::chat::ChatScreen;
use crate::state::navigation::NavStack;
use crate::ui::layout::main_layout;
use crate::ui::widgets::breadcrumb::render_breadcrumb;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::status_bar::StatusBar;

pub struct AppContext {
    pub api_url: String,
}

pub struct App {
    screen_stack: Vec<Box<dyn Screen + Send>>,
    nav: NavStack,
    status_bar: StatusBar,
    pub ctx: AppContext,
    pub running: bool,
    tick_counter: u64,
    quit_menu: Option<MenuState>,
}

impl App {
    pub fn new(api_url: String) -> Self {
        let main = ChatScreen::new();
        Self {
            screen_stack: vec![Box::new(main)],
            nav: NavStack::with_root("Chat"),
            status_bar: StatusBar::default(),
            ctx: AppContext { api_url },
            running: true,
            tick_counter: 0,
            quit_menu: None,
        }
    }

    fn quit_menu_items() -> MenuState {
        MenuState::new("Exit Jikai?", vec![
            MenuItem::new("Clean & Exit", "remove generated files, then quit"),
            MenuItem::new("Exit", "quit without cleaning"),
            MenuItem::new("Cancel", "return"),
        ])
    }

    pub fn handle_key(&mut self, key: KeyEvent) {
        // intercept quit menu
        if let Some(menu) = &mut self.quit_menu {
            if key.code == KeyCode::Esc { self.quit_menu = None; return; }
            if let Some(idx) = menu.handle_key(key) {
                match idx {
                    0 => { // clean & exit: push cleanup screen
                        self.quit_menu = None;
                        let action = ScreenAction::Push(Box::new(crate::screens::cleanup::CleanupScreen::new()));
                        self.process_action(action);
                    }
                    1 => self.running = false, // exit
                    _ => self.quit_menu = None, // cancel
                }
            }
            return;
        }
        // ctrl+c triggers quit menu
        if key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL) {
            self.quit_menu = Some(Self::quit_menu_items());
            return;
        }
        let action = if let Some(screen) = self.screen_stack.last_mut() {
            screen.handle_key(key, &mut self.ctx)
        } else {
            ScreenAction::Quit
        };
        self.process_action(action);
    }

    pub fn tick(&mut self) {
        self.tick_counter += 1;
        if let Some(screen) = self.screen_stack.last_mut() {
            screen.tick(&mut self.ctx);
        }
        if self.tick_counter % 50 == 0 {
            self.refresh_status();
        }
    }

    pub fn draw(&mut self, f: &mut Frame) {
        let (breadcrumb_area, body_area, status_area) = main_layout(f.area());
        render_breadcrumb(f, breadcrumb_area, &self.nav.breadcrumb());
        // overlay quit menu if active
        if let Some(menu) = &mut self.quit_menu {
            menu.render(f, body_area);
            self.status_bar.render(f, status_area);
            return;
        }
        if let Some(screen) = self.screen_stack.last_mut() {
            screen.render(f, body_area, &self.ctx);
        }
        self.status_bar.render(f, status_area);
    }

    fn process_action(&mut self, action: ScreenAction) {
        match action {
            ScreenAction::None => {}
            ScreenAction::Push(mut screen) => {
                screen.on_enter(&mut self.ctx);
                self.nav.push(screen.name());
                self.screen_stack.push(screen);
            }
            ScreenAction::Pop => {
                if self.screen_stack.len() > 1 {
                    self.screen_stack.pop();
                    self.nav.pop();
                } else {
                    // at root -- show quit menu with cleanup option
                    self.quit_menu = Some(Self::quit_menu_items());
                }
            }
            ScreenAction::Replace(mut screen) => {
                screen.on_enter(&mut self.ctx);
                self.nav.pop();
                self.nav.push(screen.name());
                if let Some(last) = self.screen_stack.last_mut() {
                    *last = screen;
                }
            }
            ScreenAction::Quit => {
                self.running = false;
            }
        }
    }

    fn refresh_status(&mut self) {
        self.status_bar.api_ok = true; // optimistic; real impl would ping /health
    }
}
