//! Run a shell command for each string in a JSON array
use std::io::{self, Read, Write};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};

use clap::Parser;
use indicatif::{ProgressBar, ProgressStyle};
use rayon::prelude::*;
use serde_json::Value;

#[derive(Parser, Debug)]
#[command(arg_required_else_help = true)]
pub struct Args {
    /// Command to run on each string
    #[clap(required = true)]
    pub command: Vec<String>,
}

pub fn run(args: &Args) -> Result<(), Box<dyn std::error::Error>> {
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
                    }
                    child.wait_with_output()
                });

            let result = match output {
                Ok(output) => String::from_utf8_lossy(&output.stdout).trim().to_string(),
                Err(e) => format!("Error: {}", e),
            };

            pb.lock().unwrap().inc(1);

            result
        })
        .collect();

    for result in results {
        println!("{}", result);
    }

    Ok(())
}
