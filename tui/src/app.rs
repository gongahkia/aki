use crate::screens::chat::ChatScreen;
use crate::screens::main_menu::MainMenuScreen;
use crate::screens::{Screen, ScreenAction};
use crate::state::generation::{TuiState, UiMode};
use crate::state::navigation::NavStack;
use crate::ui::layout::main_layout;
use crate::ui::widgets::breadcrumb::render_breadcrumb;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::status_bar::StatusBar;
use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use ratatui::Frame;
use std::fs::OpenOptions;
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::Duration;

struct ManagedProcess {
    child: Child,
    log_path: PathBuf,
}

pub struct AppContext {
    pub api_url: String,
    ollama_process: Option<ManagedProcess>,
    ollama_last_exit: Option<String>,
}

impl AppContext {
    pub fn new(api_url: String) -> Self {
        Self {
            api_url,
            ollama_process: None,
            ollama_last_exit: None,
        }
    }

    fn ollama_api_addr() -> SocketAddr {
        SocketAddr::from(([127, 0, 0, 1], 11434))
    }

    fn ollama_api_reachable() -> bool {
        TcpStream::connect_timeout(&Self::ollama_api_addr(), Duration::from_millis(200)).is_ok()
    }

    fn refresh_ollama_process_state(&mut self) {
        let mut exited: Option<String> = None;
        if let Some(proc) = self.ollama_process.as_mut() {
            match proc.child.try_wait() {
                Ok(Some(status)) => exited = Some(status.to_string()),
                Ok(None) => {}
                Err(err) => exited = Some(format!("error checking status: {}", err)),
            }
        }
        if let Some(status) = exited {
            self.ollama_process = None;
            self.ollama_last_exit = Some(status);
        }
    }

    pub fn poll_background_processes(&mut self) {
        self.refresh_ollama_process_state();
    }

    pub fn start_ollama_serve(&mut self) -> Result<String, String> {
        self.refresh_ollama_process_state();
        if let Some(proc) = self.ollama_process.as_ref() {
            return Ok(format!(
                "Ollama server already running (pid {}).",
                proc.child.id()
            ));
        }
        if Self::ollama_api_reachable() {
            return Ok(
                "Ollama API already reachable at 127.0.0.1:11434 (managed externally).".into(),
            );
        }

        let log_path = std::env::temp_dir().join("jikai-ollama-serve.log");
        let stdout_file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .map_err(|e| format!("Failed to open log file '{}': {}", log_path.display(), e))?;
        let stderr_file = stdout_file
            .try_clone()
            .map_err(|e| format!("Failed to clone log file handle: {}", e))?;

        let child = Command::new("ollama")
            .arg("serve")
            .stdin(Stdio::null())
            .stdout(Stdio::from(stdout_file))
            .stderr(Stdio::from(stderr_file))
            .spawn()
            .map_err(|e| format!("Failed to start `ollama serve`: {}", e))?;
        let pid = child.id();
        self.ollama_process = Some(ManagedProcess {
            child,
            log_path: log_path.clone(),
        });
        self.ollama_last_exit = None;

        // Give fast failures (missing binary/port conflict) a chance to surface.
        thread::sleep(Duration::from_millis(250));
        self.refresh_ollama_process_state();
        if self.ollama_process.is_none() && !Self::ollama_api_reachable() {
            let status = self
                .ollama_last_exit
                .as_deref()
                .unwrap_or("unknown failure");
            return Err(format!(
                "`ollama serve` exited immediately ({}). Check logs at {}",
                status,
                log_path.display()
            ));
        }

        Ok(format!(
            "Started Ollama server (pid {}). Logs: {}",
            pid,
            log_path.display()
        ))
    }

    pub fn stop_ollama_serve(&mut self) -> Result<String, String> {
        self.refresh_ollama_process_state();
        let Some(mut proc) = self.ollama_process.take() else {
            if Self::ollama_api_reachable() {
                return Err(
                    "Ollama API is reachable, but this TUI session did not start it. Stop it from your shell if needed."
                        .into(),
                );
            }
            return Err("No Ollama server process tracked by this TUI session.".into());
        };

        if let Ok(Some(status)) = proc.child.try_wait() {
            self.ollama_last_exit = Some(status.to_string());
            return Ok(format!("Ollama server already stopped ({})", status));
        }

        proc.child
            .kill()
            .map_err(|e| format!("Failed to stop Ollama server: {}", e))?;
        let status = proc
            .child
            .wait()
            .map_err(|e| format!("Failed to wait for Ollama server shutdown: {}", e))?;
        self.ollama_last_exit = Some(status.to_string());
        Ok(format!("Stopped Ollama server ({})", status))
    }

    pub fn ollama_status(&mut self) -> String {
        self.refresh_ollama_process_state();
        if let Some(proc) = self.ollama_process.as_ref() {
            let reachable = if Self::ollama_api_reachable() {
                "reachable"
            } else {
                "starting"
            };
            return format!(
                "Ollama server running (pid {}, {}). Logs: {}",
                proc.child.id(),
                reachable,
                proc.log_path.display()
            );
        }
        if Self::ollama_api_reachable() {
            return "Ollama API reachable at 127.0.0.1:11434 (managed externally).".into();
        }
        if let Some(last) = self.ollama_last_exit.as_deref() {
            return format!(
                "Ollama API not reachable. Last managed process status: {}. Run /ollama serve.",
                last
            );
        }
        "Ollama API not reachable. Run /ollama serve.".into()
    }
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
        let state = TuiState::load();
        let (main, root_label): (Box<dyn Screen + Send>, &'static str) = match state.ui_mode {
            UiMode::Traditional => (Box::new(MainMenuScreen::new()), "Main"),
            UiMode::Chat => (Box::new(ChatScreen::new()), "Chat"),
        };
        Self {
            screen_stack: vec![main],
            nav: NavStack::with_root(root_label),
            status_bar: StatusBar::default(),
            ctx: AppContext::new(api_url),
            running: true,
            tick_counter: 0,
            quit_menu: None,
        }
    }

    fn quit_menu_items() -> MenuState {
        MenuState::new(
            "Exit Jikai?",
            vec![
                MenuItem::new("Clean & Exit", "remove generated files, then quit"),
                MenuItem::new("Exit", "quit without cleaning"),
                MenuItem::new("Cancel", "return"),
            ],
        )
    }

    pub fn handle_key(&mut self, key: KeyEvent) {
        // intercept quit menu
        if let Some(menu) = &mut self.quit_menu {
            if key.code == KeyCode::Esc {
                self.quit_menu = None;
                return;
            }
            if let Some(idx) = menu.handle_key(key) {
                match idx {
                    0 => {
                        // clean & exit: push cleanup screen
                        self.quit_menu = None;
                        let action = ScreenAction::Push(Box::new(
                            crate::screens::cleanup::CleanupScreen::new_for_exit(),
                        ));
                        self.process_action(action);
                    }
                    1 => self.running = false,  // exit
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
        self.ctx.poll_background_processes();
        if let Some(screen) = self.screen_stack.last_mut() {
            screen.tick(&mut self.ctx);
        }
        let pending_action = if let Some(screen) = self.screen_stack.last_mut() {
            screen.take_pending_action()
        } else {
            ScreenAction::None
        };
        self.process_action(pending_action);
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
