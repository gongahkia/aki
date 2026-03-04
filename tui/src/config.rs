use clap::Parser;

#[derive(Parser, Debug)]
#[command(
    name = "jikai",
    version = "2.0.0",
    about = "Jikai TUI -- Singapore Tort Law Hypothetical Generator"
)]
pub struct Config {
    /// API server base URL
    #[arg(long, default_value = "http://127.0.0.1:8000", env = "JIKAI_API_URL")]
    pub api_url: String,
}
