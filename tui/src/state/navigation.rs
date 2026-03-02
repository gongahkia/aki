/// breadcrumb navigation stack
pub struct NavStack {
    stack: Vec<String>,
}

impl NavStack {
    pub fn new() -> Self { Self { stack: vec!["Main".into()] } }

    pub fn push(&mut self, label: &str) {
        self.stack.push(label.to_string());
    }

    pub fn pop(&mut self) -> Option<String> {
        if self.stack.len() > 1 { self.stack.pop() } else { None }
    }

    pub fn breadcrumb(&self) -> String {
        self.stack.join(" > ")
    }

    pub fn depth(&self) -> usize { self.stack.len() }

    pub fn reset(&mut self) {
        self.stack.truncate(1);
    }
}
