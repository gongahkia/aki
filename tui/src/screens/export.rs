use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::ProgressBar;

enum Phase {
    FormatSelect(MenuState),
    Running(ProgressBar, String),
    Done(MenuState),
    Error(String, MenuState),
}

pub struct ExportScreen {
    phase: Phase,
    poll_pending: Option<tokio::task::JoinHandle<Result<crate::api::types::JobStatus, anyhow::Error>>>,
    start_pending: Option<tokio::task::JoinHandle<Result<String, anyhow::Error>>>,
}

fn format_menu() -> MenuState {
    MenuState::new("Export Format", vec![
        MenuItem::new("DOCX", "Microsoft Word document"),
        MenuItem::new("PDF", "portable document format"),
    ])
}

fn done_menu(fmt: &str) -> MenuState {
    MenuState::new(&format!("Exported as {}", fmt.to_uppercase()), vec![
        MenuItem::new("Done", "return to previous screen"),
        MenuItem::new("Export Another", "pick a different format"),
    ])
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try again"),
        MenuItem::new("Go Back", "return to previous screen"),
    ])
}

impl ExportScreen {
    pub fn new() -> Self {
        Self { phase: Phase::FormatSelect(format_menu()), poll_pending: None, start_pending: None }
    }

    fn start_export(&mut self, format: &str, ctx: &mut AppContext) {
        self.phase = Phase::Running(ProgressBar::new(&format!("Exporting {}", format.to_uppercase())), String::new());
        let api = ctx.api_url.clone();
        let fmt = format.to_string();
        self.start_pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            let req = crate::api::types::ExportRequest {
                generation_id: None,
                hypothetical: Some("(last generated)".into()),
                analysis: None, model_answer: None,
                format: fmt, output_path: None,
            };
            client.start_export(&req).await
        }));
    }

    fn poll_job(&mut self, ctx: &AppContext, job_id: &str) {
        if self.poll_pending.is_some() { return; }
        let api = ctx.api_url.clone();
        let jid = job_id.to_string();
        self.poll_pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            client.job_status(&jid).await
        }));
    }
}

impl Screen for ExportScreen {
    fn name(&self) -> &str { "Export" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::FormatSelect(menu) => {
                if key.code == KeyCode::Esc || key.code == KeyCode::Char('q') { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    let format = if idx == 0 { "docx" } else { "pdf" };
                    self.start_export(format, ctx);
                }
            }
            Phase::Running(_, _) => {}
            Phase::Done(menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => return ScreenAction::Pop,
                        1 => self.phase = Phase::FormatSelect(format_menu()),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
            Phase::Error(_, menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => self.phase = Phase::FormatSelect(format_menu()),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::FormatSelect(menu) => menu.render(f, area),
            Phase::Running(bar, _) => bar.render(f, area),
            Phase::Done(menu) => menu.render(f, area),
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, ctx: &mut AppContext) {
        if let Some(result) = crate::async_join::take_join_result_if_finished(&mut self.start_pending) {
            match result {
                Ok(Ok(job_id)) => {
                    if let Phase::Running(_, ref mut jid) = self.phase { *jid = job_id; }
                }
                Ok(Err(e)) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                Err(e) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
            }
        }
        if let Phase::Running(_, job_id) = &self.phase {
            if !job_id.is_empty() { self.poll_job(ctx, &job_id.clone()); }
        }
        if let Some(result) = crate::async_join::take_join_result_if_finished(&mut self.poll_pending) {
            match result {
                Ok(Ok(status)) => {
                    match status.status.as_str() {
                        "completed" => { self.phase = Phase::Done(done_menu("file")); }
                        "failed" => {
                            let msg = status.error.unwrap_or_else(|| "Unknown error".into());
                            self.phase = Phase::Error(msg.clone(), error_menu(&msg));
                        }
                        "cancelled" => { self.phase = Phase::Done(done_menu("cancelled")); }
                        _ => {
                            if let Phase::Running(bar, _) = &mut self.phase {
                                bar.set(status.progress as f64 / 100.0, &format!("{}%", status.progress));
                            }
                        }
                    }
                }
                _ => {}
            }
        }
    }
}
