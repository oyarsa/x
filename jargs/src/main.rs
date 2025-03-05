use std::io::{self, Read, Write};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};

use clap::Parser;
use indicatif::{ProgressBar, ProgressStyle};
use rayon::prelude::*;
use serde_json::Value;

#[derive(Parser, Debug)]
#[clap(
    author,
    version,
    about = "Run a command on each string in a JSON array"
)]
struct Args {
    /// Command to run on each string
    #[clap(required = true)]
    command: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let mut buffer = String::new();
    io::stdin().read_to_string(&mut buffer)?;

    let data: Value = serde_json::from_str(&buffer)?;
    let strings = match data {
        Value::Array(arr) => arr
            .iter()
            .filter_map(|v| v.as_str().map(String::from))
            .collect::<Vec<String>>(),
        _ => return Err("Error: Input must be a JSON array".into()),
    };

    let pb = Arc::new(Mutex::new(
        ProgressBar::new(strings.len() as u64).with_style(ProgressStyle::default_bar().template(
            "[{elapsed_precise}] {bar:40.cyan/blue} {pos}/{len} {percent}% ETA: {eta_precise}",
        )?),
    ));

    // Clone command for parallel processing
    let cmd = args.command[0].clone();
    let cmd_args: Vec<_> = args.command[1..].to_vec();

    // Process strings in parallel but print in order
    let results: Vec<_> = strings
        .into_par_iter()
        .map(|text| {
            // Run the command
            let output = Command::new(&cmd)
                .args(&cmd_args)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .spawn()
                .and_then(|mut child| {
                    if let Some(mut stdin) = child.stdin.take() {
                        stdin.write_all(text.as_bytes())?;
                        // Close stdin to signal EOF to the command
                        drop(stdin);
                    }
                    child.wait_with_output()
                });

            // Process the output
            let result = match output {
                Ok(output) => String::from_utf8_lossy(&output.stdout).trim().to_string(),
                Err(e) => format!("Error: {}", e),
            };

            // Increment the progress bar
            pb.lock().unwrap().inc(1);

            result
        })
        .collect();

    pb.lock().unwrap().finish_with_message("Done");

    for result in results {
        println!("{}", result);
    }

    Ok(())
}
