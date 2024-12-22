use anyhow::{Context, Result};
use chrono::{Datelike, NaiveDate, Utc};
use clap::Parser;
use std::{fs, path::PathBuf};

const UNDERLINE: &str = "\x1B[4m";
const BOLD: &str = "\x1B[1m";
const RESET: &str = "\x1B[0m";

#[derive(Parser, Debug)]
#[command(author, version, about)]
struct Args {
    /// Start date in YYYY-MM-DD format
    start_date: String,

    /// End date in YYYY-MM-DD format
    end_date: String,

    /// Path to the todo list file
    #[arg(long)]
    todo: Option<PathBuf>,

    /// Start date of vacation in YYYY-MM-DD format
    #[arg(long)]
    vacation_start: Option<String>,

    /// End date of vacation in YYYY-MM-DD format
    #[arg(long)]
    vacation_end: Option<String>,

    /// Maximum number of lines to print from TODO
    #[arg(long, default_value = "10")]
    max_lines: usize,
}

#[derive(Debug)]
struct CalendarDates {
    start: NaiveDate,
    end: NaiveDate,
    today: NaiveDate,
    vacation_start: Option<NaiveDate>,
    vacation_end: Option<NaiveDate>,
}

fn validate_dates(
    start: NaiveDate,
    end: NaiveDate,
    vacation_start: Option<NaiveDate>,
    vacation_end: Option<NaiveDate>,
) -> Result<CalendarDates> {
    if start > end {
        anyhow::bail!("End date must be after start date");
    }

    if let (Some(vstart), Some(vend)) = (vacation_start, vacation_end) {
        if vstart > vend {
            anyhow::bail!("Vacation start date must be before or equal to vacation end date");
        }
        if vstart < start || vend > end {
            anyhow::bail!("Vacation period must be within the start and end dates");
        }
    }

    Ok(CalendarDates {
        start,
        end,
        today: Utc::now().date_naive(),
        vacation_start,
        vacation_end,
    })
}

fn is_vacation_day(day: NaiveDate, vacation: (Option<NaiveDate>, Option<NaiveDate>)) -> bool {
    match vacation {
        (Some(start), Some(end)) => day >= start && day <= end,
        _ => false,
    }
}

fn generate_week_calendar(week_start: NaiveDate, dates: &CalendarDates) -> String {
    let days = (0..7).map(|i| {
        let day = week_start + chrono::Duration::days(i);
        if is_vacation_day(day, (dates.vacation_start, dates.vacation_end)) {
            "V"
        } else if day < dates.start || day > dates.end {
            "·"
        } else if day == dates.today {
            "◈"
        } else if day < dates.today {
            "◼"
        } else {
            "◻"
        }
    });

    let week_str = format!(
        "{} {}",
        week_start.format("%b %d"),
        days.collect::<Vec<_>>().join(" ")
    );

    let should_underline = !is_vacation_day(week_start, (dates.vacation_start, dates.vacation_end))
        && week_start <= dates.today
        && week_start + chrono::Duration::days(7) > dates.today;

    if should_underline {
        format!("{}{}{}", UNDERLINE, week_str, RESET)
    } else {
        week_str
    }
}

fn generate_calendar(dates: &CalendarDates) -> Vec<String> {
    (dates.start.num_days_from_ce()..=dates.end.num_days_from_ce())
        .step_by(7)
        .filter_map(NaiveDate::from_num_days_from_ce_opt)
        .map(|current| {
            // Adjust to start of week (Monday)
            let week_start =
                current - chrono::Duration::days(current.weekday().num_days_from_monday() as i64);
            generate_week_calendar(week_start, dates)
        })
        .collect()
}

fn count_days(start: NaiveDate, end: NaiveDate, predicate: impl Fn(NaiveDate) -> bool) -> usize {
    (start.num_days_from_ce()..=end.num_days_from_ce())
        .map(|days| NaiveDate::from_num_days_from_ce_opt(days).unwrap())
        .filter(|&date| predicate(date))
        .count()
}

fn get_statistics(dates: &CalendarDates) -> String {
    let is_not_vacation = |date| !is_vacation_day(date, (dates.vacation_start, dates.vacation_end));
    let is_passed = |date| date <= dates.today && is_not_vacation(date);

    let total_days = count_days(dates.start, dates.end, is_not_vacation);
    let days_passed = count_days(dates.start, dates.end, is_passed);
    let days_remaining = total_days - days_passed;

    let percentage = if total_days > 0 {
        days_passed as f64 / total_days as f64
    } else {
        0.0
    };

    format!(
        "Days passed:    {:3} ({:.2}%)\n\
         Days remaining: {:3} ({:.2}%)\n\
         Total days:     {:3}",
        days_passed,
        percentage * 100.0,
        days_remaining,
        (1.0 - percentage) * 100.0,
        total_days
    )
}

fn parse_date(date_str: &str) -> Result<NaiveDate> {
    NaiveDate::parse_from_str(date_str, "%Y-%m-%d")
        .with_context(|| format!("Failed to parse date: {}", date_str))
}

fn read_todo_list(path: &PathBuf, max_lines: usize) -> Result<Vec<String>> {
    fs::read_to_string(path)
        .with_context(|| format!("Failed to read todo file: {}", path.display()))
        .map(|content| {
            content
                .lines()
                .take(max_lines)
                .map(|line| line.trim_end().to_string())
                .collect()
        })
}

fn main() -> Result<()> {
    let args = Args::parse();

    let start = parse_date(&args.start_date)?;
    let end = parse_date(&args.end_date)?;

    let vacation_start = args.vacation_start.as_deref().map(parse_date).transpose()?;
    let vacation_end = args.vacation_end.as_deref().map(parse_date).transpose()?;

    if vacation_start.is_some() != vacation_end.is_some() {
        anyhow::bail!("Both --vacation-start and --vacation-end must be provided together");
    }

    let dates = validate_dates(start, end, vacation_start, vacation_end)?;

    println!("{}{}Weekly Calendar:{}", BOLD, UNDERLINE, RESET);
    println!("From : {}", dates.start.format("%Y-%m-%d"));
    println!("To   : {}", dates.end.format("%Y-%m-%d"));
    println!("Today: {}\n", dates.today.format("%Y-%m-%d"));

    if let (Some(vstart), Some(vend)) = (vacation_start, vacation_end) {
        println!("{}Vacations:{}", UNDERLINE, RESET);
        println!(
            "- {} to {}\n",
            vstart.format("%Y-%m-%d"),
            vend.format("%Y-%m-%d")
        );
    }

    for line in generate_calendar(&dates) {
        println!("{}", line);
    }
    println!("\n{}", get_statistics(&dates));

    if let Some(todo_path) = args.todo {
        let todos = read_todo_list(&todo_path, args.max_lines)?;
        println!("\n{}{}Todo List:{}", BOLD, UNDERLINE, RESET);
        for todo in todos {
            println!("{}", todo);
        }
    }

    Ok(())
}
