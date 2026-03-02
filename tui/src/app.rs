use crossterm::event::KeyEvent;
use ratatui::Frame;
use crate::screens::{Screen, ScreenAction};
use crate::screens::main_menu::MainMenuScreen;
use crate::state::navigation::NavStack;
use crate::ui::layout::main_layout;
use crate::ui::widgets::breadcrumb::render_breadcrumb;
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
}

impl App {
    pub fn new(api_url: String) -> Self {
        let main = MainMenuScreen::new();
        Self {
            screen_stack: vec![Box::new(main)],
            nav: NavStack::new(),
            status_bar: StatusBar::default(),
            ctx: AppContext { api_url },
            running: true,
            tick_counter: 0,
        }
    }

    pub fn handle_key(&mut self, key: KeyEvent) {
        if crate::event::is_quit(&key) {
            self.running = false;
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
        // refresh status bar every ~50 ticks (~5s at 100ms tick)
        if self.tick_counter % 50 == 0 {
            self.refresh_status();
        }
    }

    pub fn draw(&mut self, f: &mut Frame) {
        let (breadcrumb_area, body_area, status_area) = main_layout(f.area());
        render_breadcrumb(f, breadcrumb_area, &self.nav.breadcrumb());
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
                    self.running = false;
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
        // async health check would be ideal; for now just mark api_ok based on last known
        // real implementation would spawn a task
        self.status_bar.api_ok = true; // optimistic
    }
}
