use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::confirm::Confirm;
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::ProgressBar;
use crossterm::event::{KeyCode, KeyEvent};
use ratatui::layout::Rect;
use ratatui::Frame;

enum Phase {
    Confirm(Confirm),
    Running(ProgressBar, String), // bar + job_id
    Done(MenuState),
    Error(String, MenuState),
}

pub struct PreprocessScreen {
    phase: Phase,
    poll_pending:
        Option<tokio::task::JoinHandle<Result<crate::api::types::JobStatus, anyhow::Error>>>,
    start_pending: Option<tokio::task::JoinHandle<Result<String, anyhow::Error>>>,
}

fn done_menu(msg: &str) -> MenuState {
    MenuState::new(
        msg,
        vec![
            MenuItem::new("Done", "return to previous screen"),
            MenuItem::new("Run Again", "preprocess again"),
        ],
    )
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 {
        format!("{}...", &msg[..60])
    } else {
        msg.to_string()
    };
    MenuState::new(
        &format!("Error: {}", short),
        vec![
            MenuItem::new("Retry", "try again"),
            MenuItem::new("Go Back", "return to previous screen"),
        ],
    )
}

impl PreprocessScreen {
    pub fn new() -> Self {
        Self {
            phase: Phase::Confirm(Confirm::new("Preprocess raw corpus files?", true)),
            poll_pending: None,
            start_pending: None,
        }
    }

    fn start_job(&mut self, ctx: &mut AppContext) {
        self.phase = Phase::Running(ProgressBar::new("Preprocessing"), String::new());
        let api = ctx.api_url.clone();
        self.start_pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.start_preprocess(None, None).await
        }));
    }

    fn poll_job(&mut self, ctx: &AppContext, job_id: &str) {
        if self.poll_pending.is_some() {
            return;
        }
        let api = ctx.api_url.clone();
        let jid = job_id.to_string();
        self.poll_pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.job_status(&jid).await
        }));
    }
}

impl Screen for PreprocessScreen {
    fn name(&self) -> &str {
        "Import & Preprocess"
    }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::Confirm(confirm) => {
                if key.code == KeyCode::Esc {
                    return ScreenAction::Pop;
                }
                if let Some(yes) = confirm.handle_key(key) {
                    if yes {
                        self.start_job(ctx);
                    } else {
                        return ScreenAction::Pop;
                    }
                }
            }
            Phase::Running(_, _) => {
                if key.code == KeyCode::Esc {
                    self.phase = Phase::Done(done_menu("Cancelled"));
                }
            }
            Phase::Done(menu) => {
                if key.code == KeyCode::Esc {
                    return ScreenAction::Pop;
                }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => return ScreenAction::Pop,
                        1 => self.start_job(ctx),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
            Phase::Error(_, menu) => {
                if key.code == KeyCode::Esc {
                    return ScreenAction::Pop;
                }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => self.start_job(ctx),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::Confirm(c) => c.render(f, area),
            Phase::Running(bar, _) => bar.render(f, area),
            Phase::Done(menu) => menu.render(f, area),
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, ctx: &mut AppContext) {
        // resolve start_pending -> get job_id
        if let Some(result) =
            crate::async_join::take_join_result_if_finished(&mut self.start_pending)
        {
            match result {
                Ok(Ok(job_id)) => {
                    if let Phase::Running(_, ref mut jid) = self.phase {
                        *jid = job_id;
                    }
                }
                Ok(Err(e)) => {
                    let msg = format!("{}", e);
                    self.phase = Phase::Error(msg.clone(), error_menu(&msg));
                }
                Err(e) => {
                    let msg = format!("{}", e);
                    self.phase = Phase::Error(msg.clone(), error_menu(&msg));
                }
            }
        }
        // poll job status
        if let Phase::Running(_, job_id) = &self.phase {
            if !job_id.is_empty() {
                self.poll_job(ctx, &job_id.clone());
            }
        }
        if let Some(result) =
            crate::async_join::take_join_result_if_finished(&mut self.poll_pending)
        {
            match result {
                Ok(Ok(status)) => match status.status.as_str() {
                    "completed" => {
                        self.phase = Phase::Done(done_menu("Preprocessing complete"));
                    }
                    "failed" => {
                        let msg = status.error.unwrap_or_else(|| "Unknown error".into());
                        self.phase = Phase::Error(msg.clone(), error_menu(&msg));
                    }
                    "cancelled" => {
                        self.phase = Phase::Done(done_menu("Cancelled"));
                    }
                    _ => {
                        if let Phase::Running(bar, _) = &mut self.phase {
                            bar.set(
                                status.progress as f64 / 100.0,
                                &format!("{}%", status.progress),
                            );
                        }
                    }
                },
                _ => {} // poll failed, will retry next tick
            }
        }
    }
}
