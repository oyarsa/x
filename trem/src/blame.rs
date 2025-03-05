//! Pretty print git blame output

use std::env;
use std::io::{self, BufWriter, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};

use clap::Parser;
use regex::Regex;

/// Show pretty-printed git blame for file
#[derive(Parser, Debug)]
#[command(arg_required_else_help = true)]
pub struct Args {
    /// File to get blame
    pub file: PathBuf,

    /// Disable pager and print directly to stdout
    #[arg(long)]
    pub no_pager: bool,
}

#[derive(Clone, Copy)]
enum Color {
    Red,
    Green,
    Yellow,
    Magenta,
    Reset,
}

impl Color {
    fn code(&self) -> &str {
        match self {
            Color::Red => "\x1b[31m",
            Color::Green => "\x1b[32m",
            Color::Yellow => "\x1b[33m",
            Color::Magenta => "\x1b[35m",
            Color::Reset => "\x1b[0m",
        }
    }
}

struct Entry {
    short_hash: String,
    author: String,
    summary: String,
    lineno: String,
    code_line: String,
}

fn prettify(text: &str, width: usize, color: Color) -> String {
    format!(
        "{}{:width$}{}",
        color.code(),
        text,
        Color::Reset.code(),
        width = width
    )
}

macro_rules! die {
    ($($arg:tt)*) => {{
        eprintln!($($arg)*);
        std::process::exit(1)
    }};
}

pub fn run(args: &Args) {
    if !args.file.exists() {
        die!("File does not exist");
    }

    let output = match Command::new("git")
        .args(["blame", "--line-porcelain"])
        .arg(&args.file)
        .output()
    {
        Ok(output) if !output.status.success() => die!(
            "Error running git blame:\n{}",
            String::from_utf8_lossy(&output.stderr)
        ),
        Ok(output) => String::from_utf8_lossy(&output.stdout).to_string(),
        Err(e) => die!("Failed to execute git: {e}"),
    };

    let hash_regex = Regex::new(r"^[0-9a-f]{40}").expect("Regex must be valid.");
    let lines: Vec<&str> = output.lines().collect();

    let mut entries = Vec::new();
    let mut i = 0;

    while i < lines.len() {
        let line = lines[i];
        if !hash_regex.is_match(line) {
            i += 1;
            continue;
        }

        let parts: Vec<&str> = line.split_whitespace().collect();
        let short_hash = parts[0][0..8].to_string();
        let lineno = parts[2].to_string();
        let mut author = String::new();
        let mut summary = String::new();

        i += 1;
        while i < lines.len() && !lines[i].starts_with('\t') && !hash_regex.is_match(lines[i]) {
            let line = lines[i];
            if let Some(author_str) = line.strip_prefix("author ") {
                author = author_str.to_string();
            } else if let Some(summary_str) = line.strip_prefix("summary ") {
                summary = summary_str.to_string();
            }
            i += 1;
        }

        let mut code_line = String::new();
        if i < lines.len() && lines[i].starts_with('\t') {
            code_line = lines[i][1..].to_string();
        }

        entries.push(Entry {
            short_hash,
            author,
            summary,
            lineno,
            code_line,
        });
        i += 1;
    }

    let max_widths = [
        ("short_hash", 10),
        ("author", 20),
        ("summary", 50),
        ("lineno", 6),
    ];

    let field_lengths: Vec<(_, usize)> = max_widths
        .iter()
        .map(|&(field, max_width)| {
            let max_len = entries
                .iter()
                .map(|e| match field {
                    "short_hash" => e.short_hash.len(),
                    "author" => e.author.len(),
                    "summary" => e.summary.len(),
                    "lineno" => e.lineno.len(),
                    _ => die!("Invalid field in git blame: {field}."),
                })
                .max()
                .unwrap_or(0);
            (field, max_len.min(max_width))
        })
        .collect();

    // Truncate fields if necessary
    for entry in &mut entries {
        for (field, max_width) in max_widths {
            let value = match field {
                "author" => &mut entry.author,
                "summary" => &mut entry.summary,
                _ => continue,
            };
            if value.len() > max_width {
                value.truncate(max_width - 1);
                value.push('…');
            }
        }
    }

    if args.no_pager {
        print_to_stdout(&entries, &field_lengths);
    } else {
        print_to_pager(&entries, &field_lengths);
    }
}

/// Write formatted lines to a writer
fn write_entries<W: Write>(
    mut writer: W,
    entries: &[Entry],
    field_lengths: &[(&str, usize)],
) -> io::Result<()> {
    let colors = [
        ("short_hash", Color::Red),
        ("author", Color::Green),
        ("summary", Color::Yellow),
        ("lineno", Color::Magenta),
    ];

    for entry in entries {
        let formatted = colors
            .iter()
            .map(|&(field, color)| {
                let width = field_lengths
                    .iter()
                    .find(|&&(f, _)| f == field)
                    .map(|&(_, w)| w)
                    .unwrap();
                let value = match field {
                    "short_hash" => &entry.short_hash,
                    "author" => &entry.author,
                    "summary" => &entry.summary,
                    "lineno" => &entry.lineno,
                    _ => unreachable!(),
                };
                prettify(value, width, color)
            })
            .collect::<Vec<String>>()
            .join(" ");

        let formatted_line = format!("{} {}", formatted, entry.code_line);
        writeln!(writer, "{formatted_line}")?;
    }

    Ok(())
}

fn print_to_stdout(entries: &[Entry], field_lengths: &[(&str, usize)]) {
    let stdout = io::stdout();
    let writer = BufWriter::new(stdout.lock());

    if let Err(e) = write_entries(writer, entries, field_lengths) {
        die!("Failed to write to stdout: {e}");
    }
}

fn print_to_pager(entries: &[Entry], field_lengths: &[(&str, usize)]) {
    // Get pager command from PAGER env var, defaulting to "less"
    let pager_cmd = env::var("PAGER").unwrap_or_else(|_| "less".to_string());

    let mut cmd = if pager_cmd.contains("less") {
        let mut cmd = Command::new(&pager_cmd);
        // -R preserves ANSI color codes
        cmd.arg("-R");
        cmd
    } else {
        // For other pagers, use as-is
        Command::new(&pager_cmd)
    };

    let mut pager = match cmd.stdin(Stdio::piped()).spawn() {
        Ok(child) => child,
        Err(e) => die!("Failed to spawn pager: {e}"),
    };

    let pager_stdin = pager.stdin.take().expect("Failed to open pager stdin");
    let writer = BufWriter::new(pager_stdin);

    if let Err(e) = write_entries(writer, entries, field_lengths) {
        die!("Failed to write to pager: {e}");
    }

    match pager.wait() {
        Ok(status) => {
            if !status.success() {
                eprintln!("Warning: Pager exited with status: {status}");
            }
        }
        Err(e) => eprintln!("Warning: Failed to wait for pager: {e}"),
    }
}
