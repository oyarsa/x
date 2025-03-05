use clap::Parser;
use serde_json::Value;
use std::fs::File;
use std::io::{self, BufReader, Read};

/// Print the first N items of a JSON array.
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
pub struct Args {
    /// Path to the JSON file
    #[arg(default_value = "-")]
    filename: String,

    /// Number of items to process
    #[arg(short = 'n', long = "items", default_value = "5")]
    num_items: usize,
}

pub fn run(args: &Args) -> Result<(), Box<dyn std::error::Error>> {
    let reader: Box<dyn Read> = if args.filename == "-" {
        Box::new(io::stdin())
    } else {
        Box::new(File::open(&args.filename)?)
    };
    let mut reader = BufReader::new(reader);

    // Check for opening bracket
    let mut byte = [0u8; 1];
    reader.read_exact(&mut byte)?;
    if byte[0] != b'[' {
        return Err("File does not start with an array '[' character".into());
    }

    // Skip initial whitespace
    loop {
        if reader.read_exact(&mut byte).is_err() {
            println!("[]"); // Empty array
            return Ok(());
        }

        if !byte[0].is_ascii_whitespace() {
            if byte[0] == b']' {
                println!("[]"); // Empty array
                return Ok(());
            }
            break; // Found start of first element
        }
    }

    // Setup for parsing
    let mut buffer = String::new();
    let mut depth = 1; // We're already inside the array
    let mut in_string = false;
    let mut escape_next = false;
    let mut elements_found = 0;
    let mut items = Vec::with_capacity(args.num_items);

    // Process the first character
    buffer.push(byte[0] as char);

    if byte[0] as char == '"' {
        in_string = true;
    } else if byte[0] as char == '{' || byte[0] as char == '[' {
        depth += 1;
    }

    // Main processing loop
    loop {
        if reader.read_exact(&mut byte).is_err() {
            // Unexpected EOF
            if !buffer.is_empty() {
                if let Ok(value) = serde_json::from_str::<Value>(&buffer) {
                    items.push(value);
                }
            }
            break;
        }

        let current_char = byte[0] as char;

        if current_char == '"' && !escape_next {
            in_string = !in_string;
        }

        if in_string {
            escape_next = current_char == '\\' && !escape_next;
            buffer.push(current_char);
        } else if current_char == '{' || current_char == '[' {
            depth += 1;
            buffer.push(current_char);
        } else if current_char == '}' || current_char == ']' {
            depth -= 1;
            buffer.push(current_char);

            if depth == 0 {
                // End of the entire array
                break;
            }
        } else if current_char == ',' && depth == 1 {
            // End of an element at the array level
            match serde_json::from_str::<Value>(&buffer) {
                Ok(value) => {
                    items.push(value);
                    elements_found += 1;

                    if elements_found >= args.num_items {
                        break;
                    }
                }
                Err(e) => {
                    eprintln!("Error parsing JSON element: {}", e);
                    eprintln!("Problematic JSON: {}", buffer);
                    return Err(e.into());
                }
            }
            buffer.clear();
        } else {
            buffer.push(current_char);
        }
    }

    println!("{}", serde_json::to_string_pretty(&items)?);

    Ok(())
}
