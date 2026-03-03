use crossterm::event::{KeyCode, KeyEvent};
use ratatui::Frame;
use ratatui::layout::Rect;
use crate::app::AppContext;
use crate::screens::{Screen, ScreenAction};
use crate::ui::widgets::menu::{MenuItem, MenuState};
use crate::ui::widgets::progress::ProgressBar;

enum Phase {
    SourceSelect(MenuState),
    Running(ProgressBar, String), // bar + job_id
    Done(MenuState),
    Error(String, MenuState),
}

pub struct ScrapeScreen {
    phase: Phase,
    poll_pending: Option<tokio::task::JoinHandle<Result<crate::api::types::JobStatus, anyhow::Error>>>,
    start_pending: Option<tokio::task::JoinHandle<Result<String, anyhow::Error>>>,
}

fn source_menu() -> MenuState {
    MenuState::new("Select Source", vec![
        MenuItem::new("CommonLII", "commonlii.org Singapore cases"),
        MenuItem::new("Judiciary.gov.sg", "official judiciary portal"),
        MenuItem::new("SICC", "Singapore International Commercial Court"),
        MenuItem::new("SG Law Gazette", "law gazette articles"),
    ])
}

fn done_menu(source: &str) -> MenuState {
    MenuState::new(&format!("Scrape complete: {}", source), vec![
        MenuItem::new("Done", "return to previous screen"),
        MenuItem::new("Scrape Another", "pick a different source"),
    ])
}

fn error_menu(msg: &str) -> MenuState {
    let short = if msg.len() > 60 { format!("{}...", &msg[..60]) } else { msg.to_string() };
    MenuState::new(&format!("Error: {}", short), vec![
        MenuItem::new("Retry", "try again"),
        MenuItem::new("Go Back", "return to previous screen"),
    ])
}

impl ScrapeScreen {
    pub fn new() -> Self {
        Self { phase: Phase::SourceSelect(source_menu()), poll_pending: None, start_pending: None }
    }

    fn start_scrape(&mut self, source: &str, ctx: &mut AppContext) {
        self.phase = Phase::Running(ProgressBar::new(&format!("Scraping {}", source)), String::new());
        let api = ctx.api_url.clone();
        let src = source.to_string();
        self.start_pending = Some(tokio::spawn(async move {
            let client = crate::api::client::ApiClient::new(&api);
            let req = crate::api::types::ScrapeRequest {
                source: src, courts: None, years: None, max_cases: 50, tort_only: true,
            };
            client.start_scrape(&req).await
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

impl Screen for ScrapeScreen {
    fn name(&self) -> &str { "Scrape SG Case Law" }

    fn handle_key(&mut self, key: KeyEvent, ctx: &mut AppContext) -> ScreenAction {
        match &mut self.phase {
            Phase::SourceSelect(menu) => {
                if key.code == KeyCode::Esc || key.code == KeyCode::Char('q') { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    let source = match idx { 0 => "commonlii", 1 => "judiciary", 2 => "sicc", _ => "gazette" };
                    self.start_scrape(source, ctx);
                }
            }
            Phase::Running(_, _) => {
                if key.code == KeyCode::Esc { self.phase = Phase::Done(done_menu("cancelled")); }
            }
            Phase::Done(menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => return ScreenAction::Pop,
                        1 => self.phase = Phase::SourceSelect(source_menu()),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
            Phase::Error(_, menu) => {
                if key.code == KeyCode::Esc { return ScreenAction::Pop; }
                if let Some(idx) = menu.handle_key(key) {
                    match idx {
                        0 => self.phase = Phase::SourceSelect(source_menu()),
                        _ => return ScreenAction::Pop,
                    }
                }
            }
        }
        ScreenAction::None
    }

    fn render(&mut self, f: &mut Frame, area: Rect, _ctx: &AppContext) {
        match &mut self.phase {
            Phase::SourceSelect(menu) => menu.render(f, area),
            Phase::Running(bar, _) => bar.render(f, area),
            Phase::Done(menu) => menu.render(f, area),
            Phase::Error(_, menu) => menu.render(f, area),
        }
    }

    fn tick(&mut self, ctx: &mut AppContext) {
        if let Some(handle) = &self.start_pending {
            if handle.is_finished() {
                let handle = self.start_pending.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(job_id)) => {
                        if let Phase::Running(_, ref mut jid) = self.phase { *jid = job_id; }
                    }
                    Ok(Err(e)) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                    Err(e) => { let msg = format!("{}", e); self.phase = Phase::Error(msg.clone(), error_menu(&msg)); }
                }
            }
        }
        if let Phase::Running(_, job_id) = &self.phase {
            if !job_id.is_empty() { self.poll_job(ctx, &job_id.clone()); }
        }
        if let Some(handle) = &self.poll_pending {
            if handle.is_finished() {
                let handle = self.poll_pending.take().unwrap();
                match tokio::runtime::Handle::current().block_on(handle) {
                    Ok(Ok(status)) => {
                        match status.status.as_str() {
                            "completed" => { self.phase = Phase::Done(done_menu("source")); }
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
}
