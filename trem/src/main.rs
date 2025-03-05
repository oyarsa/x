mod blame;
mod jargs;
mod jhead;

use clap::{Parser, Subcommand};

const HELP_TEMPLATE: &str = "\
{about}

{usage-heading} {usage}

{all-args}

{name} {version}
{author}
";

/// Multi-purpose utility for git blame formatting and JSON array processing
#[derive(Parser)]
#[command(version, about, author)]
#[command(arg_required_else_help = true)]
#[command(help_template = HELP_TEMPLATE)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Show pretty-printed git blame for file
    Blame(blame::Args),

    /// Run a command on each string in a JSON array
    Jargs(jargs::Args),

    /// Print the first N items of a JSON array
    Jhead(jhead::Args),
}

fn main() {
    let cli = Cli::parse();

    match &cli.command {
        Commands::Blame(args) => blame::run(args),
        Commands::Jargs(args) => {
            if let Err(e) = jargs::run(args) {
                eprintln!("Error: {}", e);
                std::process::exit(1);
            }
        }
        Commands::Jhead(args) => {
            if let Err(e) = jhead::run(args) {
                eprintln!("Error: {}", e);
                std::process::exit(1);
            }
        }
    }
}
