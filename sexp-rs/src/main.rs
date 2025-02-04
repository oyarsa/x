//! A single–file evaluator for our DSL.
//!
//! This program parses S–expressions that track line numbers and supports DSL forms:
//!   base-cmd, load-env, load-config, types, def, task, and group.
//!
//! It implements built–in functions (or, and, if, equal?, env, conf, git-root,
//! current-timestamp, shell, from-shell) and performs string interpolation
//! (using {var} syntax with a maximum recursion depth of 10).
//!
//! The CLI supports:
//!   - Listing tasks: `dsl --list` (with optional `--verbose` for descriptions)
//!   - Running tasks (or groups), e.g. `dsl eval.accuracy` or `dsl train eval.accuracy`
//!   - Passing extra arguments: e.g. `dsl eval.accuracy -- --verbose`
//!   - Specifying the DSL file with `--file`/`-f` (default: "tasks.dsl")
//!   - When no tasks are provided, it defaults to the "default" task.
//!   - Every evaluation error is annotated with the line number where it occurred.

use chrono::Utc;
use clap::Parser as ClapParser;
use regex::Regex;
use serde_json::Value as JsonValue;
use std::collections::{HashMap, HashSet};
use std::env;
use std::error::Error;
use std::fmt;
use std::fs;
use std::path::Path;
use std::process::Command;
use thiserror::Error;

// ======================================================================
// CLI definition
// ======================================================================

const HELP_TEMPLATE: &str = "\
{about}

{usage-heading} {usage}

{all-args}

{name} {version}
{author}
";

#[derive(ClapParser, Debug)]
#[command(version, about, author)]
#[command(help_template = HELP_TEMPLATE)]
struct Cli {
    /// Path to the DSL file
    #[arg(short, long, default_value = "tasks.dsl")]
    file: String,

    /// List all available tasks
    #[arg(long)]
    list: bool,

    /// Print descriptions with the task list
    #[arg(long)]
    verbose: bool,

    /// Names of tasks or groups to run
    #[arg()]
    tasks: Vec<String>,

    /// Extra arguments to pass to the task command (after `--`)
    #[arg(last = true, num_args = 0..)]
    extra_args: Vec<String>,
}

// ======================================================================
// S–Expression parser with location tracking
// ======================================================================

#[derive(Debug, Clone, PartialEq)]
pub enum SExp {
    Symbol(String, usize),
    String(String, usize),
    List(Vec<SExp>, usize),
    Quoted(Box<SExp>, usize),
}

impl SExp {
    /// Return the line number where this SExp was parsed.
    fn line(&self) -> usize {
        match self {
            SExp::Symbol(_, line) => *line,
            SExp::String(_, line) => *line,
            SExp::List(_, line) => *line,
            SExp::Quoted(_, line) => *line,
        }
    }
}

#[derive(Debug, Clone, Error)]
pub enum ParseError {
    #[error("Unexpected end of input at line {0}")]
    UnexpectedEOF(usize),

    #[error("Unclosed string literal at line {0}")]
    UnterminatedString(usize),

    #[error("Unclosed parenthesis at line {0}")]
    UnclosedParen(usize),

    #[error("Unexpected closing parenthesis at line {0}")]
    UnexpectedCloseParen(usize),

    #[error("Empty quoted expression at line {0}")]
    EmptyQuoted(usize),

    #[error("Unexpected content at line {1}: {0}")]
    UnexpectedContent(String, usize),
}

impl fmt::Display for SExp {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            SExp::Symbol(s, _) => write!(f, "{}", s),
            SExp::String(s, _) => write!(f, "\"{}\"", s),
            SExp::List(items, _) => {
                write!(f, "(")?;
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        write!(f, " ")?;
                    }
                    write!(f, "{}", item)?;
                }
                write!(f, ")")
            }
            SExp::Quoted(exp, _) => write!(f, "'{}", exp),
        }
    }
}

pub struct Parser<'a> {
    text: &'a str,
    pos: usize,
    nil: &'a str,
    true_val: &'a str,
    false_val: Option<&'a str>,
    line_comment: char,
}

impl<'a> Parser<'a> {
    pub fn new(
        text: &'a str,
        nil: &'a str,
        true_val: &'a str,
        false_val: Option<&'a str>,
        line_comment: char,
    ) -> Self {
        Self {
            text,
            pos: 0,
            nil,
            true_val,
            false_val,
            line_comment,
        }
    }

    /// Compute the current line number (starting at 1).
    fn current_line(&self) -> usize {
        self.text[..self.pos].matches('\n').count() + 1
    }

    fn parse_sexp(&mut self) -> Result<SExp, ParseError> {
        let chars: Vec<char> = self.text.chars().collect();
        while self.pos < chars.len() {
            let c = chars[self.pos];
            if c.is_whitespace() {
                self.pos += 1;
            } else if c == self.line_comment {
                self.skip_comment(&chars);
            } else {
                break;
            }
        }
        if self.pos >= chars.len() {
            return Err(ParseError::UnexpectedEOF(self.current_line()));
        }
        match chars[self.pos] {
            '(' => {
                let start_line = self.current_line();
                self.pos += 1;
                let mut list = Vec::new();
                while self.pos < chars.len() && chars[self.pos] != ')' {
                    list.push(self.parse_sexp()?);
                }
                if self.pos >= chars.len() {
                    return Err(ParseError::UnclosedParen(self.current_line()));
                }
                self.pos += 1; // consume ')'
                Ok(SExp::List(list, start_line))
            }
            ')' => Err(ParseError::UnexpectedCloseParen(self.current_line())),
            '"' => {
                let start_line = self.current_line();
                self.parse_string(&chars).map(|s| match s {
                    SExp::String(val, _) => SExp::String(val, start_line),
                    other => other,
                })
            }
            '\'' => {
                let start_line = self.current_line();
                self.pos += 1;
                let quoted = self.parse_sexp()?;
                Ok(SExp::Quoted(Box::new(quoted), start_line))
            }
            _ => {
                let start_line = self.current_line();
                self.parse_atom(&chars).map(|s| match s {
                    SExp::Symbol(val, _) => SExp::Symbol(val, start_line),
                    other => other,
                })
            }
        }
    }

    fn parse_string(&mut self, chars: &[char]) -> Result<SExp, ParseError> {
        assert_eq!(chars[self.pos], '"');
        self.pos += 1;
        let mut result = String::new();
        while self.pos < chars.len() {
            match chars[self.pos] {
                '"' => {
                    self.pos += 1;
                    return Ok(SExp::String(result, self.current_line()));
                }
                '\\' => {
                    self.pos += 1;
                    if self.pos >= chars.len() {
                        return Err(ParseError::UnterminatedString(self.current_line()));
                    }
                    result.push(match chars[self.pos] {
                        'n' => '\n',
                        'r' => '\r',
                        't' => '\t',
                        'b' => '\u{0008}',
                        'f' => '\u{000C}',
                        c => c,
                    });
                }
                c => result.push(c),
            }
            self.pos += 1;
        }
        Err(ParseError::UnterminatedString(self.current_line()))
    }

    fn parse_atom(&mut self, chars: &[char]) -> Result<SExp, ParseError> {
        let start = self.pos;
        while self.pos < chars.len() {
            let c = chars[self.pos];
            if c.is_whitespace() || c == '(' || c == ')' || c == self.line_comment {
                break;
            }
            self.pos += 1;
        }
        let token: String = chars[start..self.pos].iter().collect();
        Ok(match token.as_str() {
            s if s == self.nil => SExp::List(vec![], self.current_line()),
            s if s == self.true_val => SExp::Symbol("true".to_string(), self.current_line()),
            s if Some(s) == self.false_val => {
                SExp::Symbol("false".to_string(), self.current_line())
            }
            _ => {
                if let Ok(n) = token.parse::<i64>() {
                    SExp::Symbol(n.to_string(), self.current_line())
                } else if let Ok(f) = token.parse::<f64>() {
                    SExp::Symbol(f.to_string(), self.current_line())
                } else {
                    SExp::Symbol(token, self.current_line())
                }
            }
        })
    }

    fn skip_comment(&mut self, chars: &[char]) {
        while self.pos < chars.len() && chars[self.pos] != '\n' {
            self.pos += 1;
        }
    }
}

/// Parse all top-level forms from the input string.
pub fn loads_all(s: &str) -> Result<Vec<SExp>, ParseError> {
    let mut forms = Vec::new();
    let mut parser = Parser::new(s, "nil", "t", None, ';');
    let chars: Vec<char> = s.chars().collect();
    while parser.pos < chars.len() {
        while parser.pos < chars.len() {
            let c = chars[parser.pos];
            if c.is_whitespace() {
                parser.pos += 1;
            } else if c == parser.line_comment {
                parser.skip_comment(&chars);
            } else {
                break;
            }
        }
        if parser.pos >= chars.len() {
            break;
        }
        if chars[parser.pos] != '(' {
            return Err(ParseError::UnexpectedContent(
                format!("Expected '(' at position {}", parser.pos),
                parser.current_line(),
            ));
        }
        let form = parser.parse_sexp()?;
        forms.push(form);
    }
    Ok(forms)
}

// ======================================================================
// DSL Evaluator definitions and context
// ======================================================================

#[derive(Debug, Clone)]
enum Value {
    Str(String),
    List(Vec<String>),
    None,
}

impl Value {
    fn as_str(&self) -> Result<&str, EvalError> {
        match self {
            Value::Str(s) => Ok(s),
            _ => Err(EvalError::Other {
                message: "Expected string value".to_string(),
                line: 0,
            }),
        }
    }
}

#[derive(Debug, Error)]
pub enum EvalError {
    #[error("Undefined variable: {message} (at line {line})")]
    UndefinedVariable { message: String, line: usize },

    #[error("Unknown function: {message} (at line {line})")]
    UnknownFunction { message: String, line: usize },

    #[error("Invalid function call: {message} (at line {line})")]
    InvalidFunctionCall { message: String, line: usize },

    #[error("Non-literal value in quoted expression: {message} (at line {line})")]
    NonLiteralInQuoted { message: String, line: usize },

    #[error("Interpolation depth exceeded: {message} (at line {line})")]
    InterpolationDepthExceeded { message: String, line: usize },

    #[error("Type error for variable {var}: value {value} is not allowed (allowed: {allowed:?}) (at line {line})")]
    TypeError {
        var: String,
        value: String,
        allowed: Vec<String>,
        line: usize,
    },

    #[error("Execution error: {message} (at line {line})")]
    ExecutionError { message: String, line: usize },

    #[error("Error: {message} (at line {line})")]
    Other { message: String, line: usize },
}

struct Context {
    base_cmd: Option<String>,
    config: Option<JsonValue>,
    types: HashMap<String, Vec<String>>,
    defs: HashMap<String, String>,
    tasks: HashMap<String, Task>,
    groups: HashMap<String, Task>, // Group-level info.
}

impl Context {
    fn new() -> Self {
        Self {
            base_cmd: None,
            config: None,
            types: HashMap::new(),
            defs: HashMap::new(),
            tasks: HashMap::new(),
            groups: HashMap::new(),
        }
    }
}

#[derive(Debug, Clone)]
struct Task {
    name: String, // Fully qualified (e.g. "eval.accuracy")
    title: String,
    desc: Option<String>,
    meta: HashMap<String, String>,
    cmd: Option<String>,
    shell: Option<String>,
    params: Option<String>,
    steps: Vec<String>,
    props: HashMap<String, String>,
}

// ======================================================================
// Modified interpolate: now accepts a line number parameter.
// ======================================================================

fn interpolate(s: &str, env: &HashMap<String, String>, line: usize) -> Result<String, EvalError> {
    let mut result = s.to_string();
    let re = Regex::new(r"\{([^}]+)\}").unwrap();
    for _ in 0..10 {
        if !re.is_match(&result) {
            return Ok(result);
        }
        let mut replaced = result.clone();
        for cap in re.captures_iter(&result) {
            let key = &cap[1];
            if let Some(val) = env.get(key) {
                replaced = replaced.replace(&format!("{{{}}}", key), val);
            } else {
                return Err(EvalError::UndefinedVariable {
                    message: format!("{} (in interpolation)", key),
                    line,
                });
            }
        }
        result = replaced;
    }
    if re.is_match(&result) {
        Err(EvalError::InterpolationDepthExceeded {
            message: "(in interpolation)".to_string(),
            line,
        })
    } else {
        Ok(result)
    }
}

// ======================================================================
// DSL top–level forms processing functions
// ======================================================================

fn dumps(exp: &SExp, pretty: bool) -> String {
    if pretty {
        dumps_pretty(exp, "  ", 0)
    } else {
        exp.to_string()
    }
}

fn dumps_pretty(exp: &SExp, indent: &str, level: usize) -> String {
    match exp {
        SExp::String(s, _) | SExp::Symbol(s, _) => s.to_string(),
        SExp::List(items, _) if items.is_empty() => "()".to_string(),
        SExp::List(items, _) => {
            let indent_str = indent.repeat(level + 1);
            let items_str: Vec<String> = items
                .iter()
                .map(|x| dumps_pretty(x, indent, level + 1))
                .collect();
            format!(
                "(\n{}{}\n{})",
                indent_str,
                items_str.join(&format!("\n{}", indent_str)),
                indent.repeat(level)
            )
        }
        SExp::Quoted(inner, _) => format!("'{}", dumps_pretty(inner, indent, level)),
    }
}

// ======================================================================
// DSL Evaluator Context and Task definitions
// ======================================================================

fn process_forms(forms: &[SExp], ctx: &mut Context) -> Result<(), EvalError> {
    for form in forms {
        if let SExp::List(items, form_line) = form {
            if items.is_empty() {
                continue;
            }
            if let SExp::Symbol(ref form_name, _) = items[0] {
                match form_name.as_str() {
                    "base-cmd" => {
                        if items.len() != 2 {
                            return Err(EvalError::Other {
                                message: "base-cmd requires one argument".to_string(),
                                line: *form_line,
                            });
                        }
                        if let SExp::String(s, _) = &items[1] {
                            ctx.base_cmd = Some(s.clone());
                        } else {
                            return Err(EvalError::Other {
                                message: "base-cmd argument must be a string".to_string(),
                                line: *form_line,
                            });
                        }
                    }
                    "load-env" => {
                        if items.len() != 2 {
                            return Err(EvalError::Other {
                                message: "load-env requires one argument".to_string(),
                                line: *form_line,
                            });
                        }
                        if let SExp::String(fname, line) = &items[1] {
                            load_env(fname).map_err(|e| EvalError::Other {
                                message: format!("{} (in load-env)", e),
                                line: *line,
                            })?;
                        } else {
                            return Err(EvalError::Other {
                                message: "load-env argument must be a string".to_string(),
                                line: *form_line,
                            });
                        }
                    }
                    "load-config" => {
                        if items.len() != 2 {
                            return Err(EvalError::Other {
                                message: "load-config requires one argument".to_string(),
                                line: *form_line,
                            });
                        }
                        if let SExp::String(fname, line) = &items[1] {
                            let content = fs::read_to_string(fname).map_err(|e| {
                                EvalError::Other { message: format!("Error reading config file '{}': {}. Please ensure the file exists and is accessible.", fname, e), line: *line }
                            })?;
                            let json: JsonValue =
                                serde_json::from_str(&content).map_err(|e| EvalError::Other {
                                    message: format!(
                                        "Error parsing JSON in config file '{}': {}.",
                                        fname, e
                                    ),
                                    line: *line,
                                })?;
                            ctx.config = Some(json);
                        } else {
                            return Err(EvalError::Other {
                                message: "load-config argument must be a string".to_string(),
                                line: *form_line,
                            });
                        }
                    }
                    "types" => {
                        for type_def in &items[1..] {
                            if let SExp::List(def_items, def_line) = type_def {
                                if def_items.len() != 2 {
                                    return Err(EvalError::Other { message: format!("Malformed type definition: expected exactly 2 parts, but found {} in: {}", def_items.len(), dumps(type_def, false)), line: *def_line });
                                }
                                let type_name = if let SExp::Symbol(s, _) = &def_items[0] {
                                    s.clone()
                                } else {
                                    return Err(EvalError::Other {
                                        message: format!(
                                            "Invalid type name in type definition: {}",
                                            dumps(&def_items[0], false)
                                        ),
                                        line: *def_line,
                                    });
                                };
                                let allowed_val = eval_expr(&def_items[1], &ctx.defs, ctx)
                                    .map_err(|e| EvalError::Other {
                                        message: format!(
                                            "Error evaluating allowed-values for type '{}': {}",
                                            type_name, e
                                        ),
                                        line: *def_line,
                                    })?;
                                let allowed = match allowed_val {
                                    Value::List(v) => v,
                                    Value::Str(s) => vec![s],
                                    _ => {
                                        return Err(EvalError::Other { message: format!("Type allowed-values for '{}' must be a list or string, but got: {}", type_name, dumps(&def_items[1], false)), line: *def_line });
                                    }
                                };
                                ctx.types.insert(type_name, allowed);
                            } else {
                                return Err(EvalError::Other {
                                    message: format!(
                                        "Invalid type definition: expected a list, got: {}",
                                        dumps(type_def, false)
                                    ),
                                    line: 0,
                                });
                            }
                        }
                    }
                    "def" => {
                        for def_item in &items[1..] {
                            if let SExp::List(parts, def_line) = def_item {
                                if parts.len() != 2 {
                                    return Err(EvalError::Other {
                                        message: "Each def entry must have a key and a value"
                                            .to_string(),
                                        line: *def_line,
                                    });
                                }
                                let (var_name, type_opt) = match &parts[0] {
                                    SExp::Symbol(s, _) => (s.clone(), None),
                                    SExp::List(inner, _) if inner.len() == 2 => {
                                        let raw_var = if let SExp::Symbol(s, _) = &inner[0] {
                                            s.trim_start_matches('[').to_string()
                                        } else {
                                            return Err(EvalError::Other {
                                                message: "Invalid def key".to_string(),
                                                line: *def_line,
                                            });
                                        };
                                        let raw_type = if let SExp::Symbol(s, _) = &inner[1] {
                                            s.trim_end_matches(']').to_string()
                                        } else {
                                            return Err(EvalError::Other {
                                                message: "Invalid def type".to_string(),
                                                line: *def_line,
                                            });
                                        };
                                        (raw_var, Some(raw_type))
                                    }
                                    _ => {
                                        return Err(EvalError::Other {
                                            message: "Invalid def key format".to_string(),
                                            line: *def_line,
                                        })
                                    }
                                };
                                let val = eval_expr(&parts[1], &ctx.defs, ctx).map_err(|e| {
                                    EvalError::Other {
                                        message: format!(
                                            "Error evaluating def entry for variable '{}': {}",
                                            var_name, e
                                        ),
                                        line: *def_line,
                                    }
                                })?;
                                let val_str = match val {
                                    Value::Str(s) => s,
                                    _ => String::new(),
                                };
                                if let Some(tname) = type_opt {
                                    if let Some(allowed) = ctx.types.get(&tname) {
                                        if !allowed.contains(&val_str) {
                                            return Err(EvalError::TypeError {
                                                var: var_name.clone(),
                                                value: val_str.clone(),
                                                allowed: allowed.clone(),
                                                line: *def_line,
                                            });
                                        }
                                    }
                                }
                                ctx.defs.insert(var_name, val_str);
                            } else {
                                return Err(EvalError::Other {
                                    message: "Invalid def entry (expected a list)".to_string(),
                                    line: 0,
                                });
                            }
                        }
                    }
                    "task" => {
                        let task = process_task(items, None).map_err(|e| EvalError::Other {
                            message: format!("Error processing task: {}", e),
                            line: items[0].line(),
                        })?;
                        ctx.tasks.insert(task.name.clone(), task);
                    }
                    "group" => {
                        if let SExp::List(items, group_line) = form {
                            if items.len() < 3 {
                                return Err(EvalError::Other {
                                    message: "Group definition too short".to_string(),
                                    line: *group_line,
                                });
                            }
                            let group_name = if let SExp::Symbol(s, _) = &items[1] {
                                s.clone()
                            } else {
                                return Err(EvalError::Other {
                                    message: "Group name must be a symbol".to_string(),
                                    line: *group_line,
                                });
                            };
                            process_group(items, ctx).map_err(|e| EvalError::Other {
                                message: format!("Error processing group '{}': {}", group_name, e),
                                line: *group_line,
                            })?;
                        }
                    }
                    other => {
                        return Err(EvalError::Other {
                            message: format!("Unknown top-level form: {}", other),
                            line: items[0].line(),
                        });
                    }
                }
            } else {
                return Err(EvalError::Other {
                    message: "Expected a symbol at the beginning of the form".to_string(),
                    line: *form_line,
                });
            }
        } else {
            return Err(EvalError::Other {
                message: "Expected a list for a top-level form".to_string(),
                line: 0,
            });
        }
    }
    Ok(())
}

fn eval_expr(exp: &SExp, env: &HashMap<String, String>, ctx: &Context) -> Result<Value, EvalError> {
    match exp {
        SExp::String(s, _) => {
            // Interpolate the string and propagate errors with the line number from exp.
            let interped = interpolate(s, env, exp.line()).map_err(|e| EvalError::Other {
                message: format!("{} (in string)", e),
                line: exp.line(),
            })?;
            Ok(Value::Str(interped))
        }
        SExp::Symbol(s, line) => {
            if let Some(val) = env.get(s) {
                Ok(Value::Str(val.clone()))
            } else {
                Err(EvalError::UndefinedVariable {
                    message: s.clone(),
                    line: *line,
                })
            }
        }
        SExp::List(list, _) => {
            if list.is_empty() {
                return Ok(Value::None);
            }
            // The function name is expected to be the first element.
            let func_line = list[0].line();
            let func = match &list[0] {
                SExp::Symbol(s, _) => s.as_str(),
                _ => {
                    return Err(EvalError::InvalidFunctionCall {
                        message: "Function call must start with a symbol".to_string(),
                        line: func_line,
                    })
                }
            };
            match func {
                "or" => {
                    for arg in &list[1..] {
                        let val = eval_expr(arg, env, ctx)?;
                        if let Value::None = val {
                            continue;
                        } else {
                            return Ok(val);
                        }
                    }
                    Ok(Value::None)
                }
                "and" => {
                    let mut last = Value::None;
                    for arg in &list[1..] {
                        last = eval_expr(arg, env, ctx)?;
                        if let Value::None = last {
                            return Ok(Value::None);
                        }
                    }
                    Ok(last)
                }
                "if" => {
                    if list.len() != 4 {
                        return Err(EvalError::InvalidFunctionCall {
                            message: "if requires exactly 3 arguments".to_string(),
                            line: func_line,
                        });
                    }
                    let cond = eval_expr(&list[1], env, ctx)?;
                    let cond_val = cond.as_str().map_err(|_| EvalError::Other {
                        message: "Condition must be a string".to_string(),
                        line: list[1].line(),
                    })?;
                    if cond_val.trim() == "true" {
                        eval_expr(&list[2], env, ctx)
                    } else {
                        eval_expr(&list[3], env, ctx)
                    }
                }
                "equal?" => {
                    if list.len() != 3 {
                        return Err(EvalError::InvalidFunctionCall {
                            message: "equal? requires exactly 2 arguments".to_string(),
                            line: func_line,
                        });
                    }
                    let a = eval_expr(&list[1], env, ctx)?;
                    let a_str = a
                        .as_str()
                        .map_err(|_| EvalError::Other {
                            message: "Expected string".to_string(),
                            line: list[1].line(),
                        })?
                        .trim();
                    let b = eval_expr(&list[2], env, ctx)?;
                    let b_str = b
                        .as_str()
                        .map_err(|_| EvalError::Other {
                            message: "Expected string".to_string(),
                            line: list[2].line(),
                        })?
                        .trim();
                    Ok(Value::Str(
                        if a_str == b_str { "true" } else { "false" }.to_string(),
                    ))
                }
                "env" => {
                    if list.len() != 2 {
                        return Err(EvalError::InvalidFunctionCall {
                            message: "env requires one argument".to_string(),
                            line: func_line,
                        });
                    }
                    let var = eval_expr(&list[1], env, ctx)?
                        .as_str()
                        .map_err(|_| EvalError::Other {
                            message: "Expected string".to_string(),
                            line: list[1].line(),
                        })?
                        .to_string();
                    match env::var(&var) {
                        Ok(val) => Ok(Value::Str(val)),
                        Err(_) => Ok(Value::None),
                    }
                }
                "conf" => {
                    if list.len() != 2 {
                        return Err(EvalError::InvalidFunctionCall {
                            message: "conf requires one argument".to_string(),
                            line: func_line,
                        });
                    }
                    let key = eval_expr(&list[1], env, ctx)?
                        .as_str()
                        .map_err(|_| EvalError::Other {
                            message: "Expected string".to_string(),
                            line: list[1].line(),
                        })?
                        .to_string();
                    if let Some(cfg) = &ctx.config {
                        if let Some(val) = cfg.get(&key) {
                            if let Some(s) = val.as_str() {
                                return Ok(Value::Str(s.to_string()));
                            }
                        }
                    }
                    Ok(Value::None)
                }
                "git-root" => {
                    let output = Command::new("git")
                        .args(["rev-parse", "--show-toplevel"])
                        .output()
                        .map_err(|e| EvalError::ExecutionError {
                            message: format!("Git error: {}", e),
                            line: func_line,
                        })?;
                    let s = String::from_utf8_lossy(&output.stdout).trim().to_string();
                    Ok(Value::Str(s))
                }
                "current-timestamp" => {
                    let now = Utc::now().to_rfc3339();
                    Ok(Value::Str(now))
                }
                "shell" => {
                    if list.len() != 2 {
                        return Err(EvalError::InvalidFunctionCall {
                            message: "shell requires one argument".to_string(),
                            line: func_line,
                        });
                    }
                    let cmd_str = eval_expr(&list[1], env, ctx)?
                        .as_str()
                        .map_err(|_| EvalError::Other {
                            message: "Expected string".to_string(),
                            line: list[1].line(),
                        })?
                        .to_string();
                    let output = Command::new("sh")
                        .arg("-c")
                        .arg(&cmd_str)
                        .output()
                        .map_err(|e| EvalError::ExecutionError {
                            message: format!("Shell execution error: {}", e),
                            line: func_line,
                        })?;
                    let s = String::from_utf8_lossy(&output.stdout).trim().to_string();
                    Ok(Value::Str(s))
                }
                "from-shell" => {
                    if list.len() != 2 {
                        return Err(EvalError::InvalidFunctionCall {
                            message: "from-shell requires one argument".to_string(),
                            line: func_line,
                        });
                    }
                    let cmd_str = eval_expr(&list[1], env, ctx)?
                        .as_str()
                        .map_err(|_| EvalError::Other {
                            message: "Expected string".to_string(),
                            line: list[1].line(),
                        })?
                        .to_string();
                    let output = Command::new("sh")
                        .arg("-c")
                        .arg(&cmd_str)
                        .output()
                        .map_err(|e| EvalError::ExecutionError {
                            message: format!("from-shell error: {}", e),
                            line: func_line,
                        })?;
                    let s = String::from_utf8_lossy(&output.stdout);
                    let parts: Vec<String> = s.split_whitespace().map(|s| s.to_string()).collect();
                    Ok(Value::List(parts))
                }
                _ => Err(EvalError::UnknownFunction {
                    message: func.to_string(),
                    line: func_line,
                }),
            }
        }
        SExp::Quoted(inner, line) => match &**inner {
            SExp::List(items, _) => {
                let mut vec = Vec::new();
                for item in items {
                    match item {
                        SExp::String(s, _) => vec.push(s.clone()),
                        SExp::Symbol(s, _) => vec.push(s.clone()),
                        _ => {
                            return Err(EvalError::NonLiteralInQuoted {
                                message: "(in quoted expression)".to_string(),
                                line: *line,
                            })
                        }
                    }
                }
                Ok(Value::List(vec))
            }
            other => eval_expr(other, env, ctx),
        },
    }
}
fn process_task(items: &[SExp], parent: Option<&Task>) -> Result<Task, EvalError> {
    if items.len() < 3 {
        return Err(EvalError::Other {
            message: "Task definition too short".to_string(),
            line: items[0].line(),
        });
    }
    let raw_name = match &items[1] {
        SExp::Symbol(s, _) => s.clone(),
        _ => {
            return Err(EvalError::Other {
                message: "Task name must be a symbol".to_string(),
                line: items[0].line(),
            })
        }
    };
    let name = if let Some(p) = parent {
        format!("{}.{}", p.name, raw_name)
    } else {
        raw_name
    };
    let title = match &items[2] {
        SExp::String(s, _) => s.clone(),
        _ => {
            return Err(EvalError::Other {
                message: "Task title must be a string".to_string(),
                line: items[0].line(),
            })
        }
    };
    let mut task = Task {
        name: name.clone(),
        title,
        desc: None,
        meta: HashMap::new(),
        cmd: None,
        shell: None,
        params: None,
        steps: vec![],
        props: HashMap::new(),
    };
    for prop in &items[3..] {
        if let SExp::List(prop_items, _) = prop {
            if prop_items.is_empty() {
                continue;
            }
            let key = if let SExp::Symbol(s, _) = &prop_items[0] {
                s.as_str()
            } else {
                continue;
            };
            match key {
                "desc" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s, _) = &prop_items[1] {
                            task.desc = Some(s.clone());
                        }
                    }
                }
                "meta" => {
                    for meta_prop in &prop_items[1..] {
                        if let SExp::List(pair, _) = meta_prop {
                            if pair.len() == 2 {
                                let mkey = match &pair[0] {
                                    SExp::Symbol(s, _) | SExp::String(s, _) => s.clone(),
                                    _ => continue,
                                };
                                let mval = match &pair[1] {
                                    SExp::Symbol(s, _) | SExp::String(s, _) => s.clone(),
                                    _ => continue,
                                };
                                task.meta.insert(mkey, mval);
                            }
                        }
                    }
                }
                "cmd" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s, _) = &prop_items[1] {
                            task.cmd = Some(s.clone());
                        }
                    }
                }
                "shell" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s, _) = &prop_items[1] {
                            task.shell = Some(s.clone());
                        }
                    }
                }
                "params" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s, _) = &prop_items[1] {
                            task.params = Some(s.clone());
                        }
                    }
                }
                "steps" => {
                    for step in &prop_items[1..] {
                        if let SExp::Symbol(s, _) = step {
                            task.steps.push(s.clone());
                        }
                    }
                }
                _ => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s, _) = &prop_items[1] {
                            task.props.insert(key.to_string(), s.clone());
                        } else if let SExp::Symbol(s, _) = &prop_items[1] {
                            task.props.insert(key.to_string(), s.clone());
                        }
                    }
                }
            }
        }
    }
    if let Some(p) = parent {
        if task.cmd.is_none() {
            task.cmd = p.cmd.clone();
        }
        if task.params.is_none() {
            task.params = p.params.clone();
        }
    }
    Ok(task)
}

fn process_group(items: &[SExp], ctx: &mut Context) -> Result<(), EvalError> {
    if items.len() < 3 {
        return Err(EvalError::Other {
            message: "Group definition too short".to_string(),
            line: items[0].line(),
        });
    }
    let group_name = match &items[1] {
        SExp::Symbol(s, _) => s.clone(),
        _ => {
            return Err(EvalError::Other {
                message: "Group name must be a symbol".to_string(),
                line: items[0].line(),
            })
        }
    };
    let group_title = match &items[2] {
        SExp::String(s, _) => s.clone(),
        _ => {
            return Err(EvalError::Other {
                message: "Group title must be a string".to_string(),
                line: items[0].line(),
            })
        }
    };
    let mut group_task = Task {
        name: group_name.clone(),
        title: group_title,
        desc: None,
        meta: HashMap::new(),
        cmd: None,
        shell: None,
        params: None,
        steps: vec![],
        props: HashMap::new(),
    };
    for prop in &items[3..] {
        if let SExp::List(prop_items, _) = prop {
            if prop_items.is_empty() {
                continue;
            }
            let SExp::Symbol(key, _) = &prop_items[0] else {
                continue;
            };
            match key.as_str() {
                "desc" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s, _) = &prop_items[1] {
                            group_task.desc = Some(s.clone());
                        }
                    }
                }
                "meta" => {
                    for meta_prop in &prop_items[1..] {
                        if let SExp::List(pair, _) = meta_prop {
                            if pair.len() == 2 {
                                let mkey = match &pair[0] {
                                    SExp::Symbol(s, _) | SExp::String(s, _) => s.clone(),
                                    _ => continue,
                                };
                                let mval = match &pair[1] {
                                    SExp::Symbol(s, _) | SExp::String(s, _) => s.clone(),
                                    _ => continue,
                                };
                                group_task.meta.insert(mkey, mval);
                            }
                        }
                    }
                }
                "params" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s, _) = &prop_items[1] {
                            group_task.params = Some(s.clone());
                        }
                    }
                }
                "cmd" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s, _) = &prop_items[1] {
                            group_task.cmd = Some(s.clone());
                        }
                    }
                }
                _ => {}
            }
        }
    }
    ctx.groups.insert(group_name.clone(), group_task.clone());
    for prop in &items[3..] {
        if let SExp::List(prop_items, _) = prop {
            if !prop_items.is_empty() {
                if let SExp::Symbol(key, _) = &prop_items[0] {
                    if key.as_str() == "task" {
                        let task = process_task(prop_items, Some(&group_task))?;
                        ctx.tasks.insert(task.name.clone(), task);
                    }
                }
            }
        }
    }
    Ok(())
}

// ======================================================================
// Environment loader (strips quotes from values)
// ======================================================================

fn load_env(fname: &str) -> Result<(), EvalError> {
    let content = fs::read_to_string(fname).map_err(|e| {
        EvalError::Other { message: format!("Error reading .env file '{}': {}. Please ensure the file exists in the expected location.", fname, e), line: 0 }
    })?;
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('#') || trimmed.is_empty() {
            continue;
        }
        if let Some(idx) = trimmed.find('=') {
            let key = &trimmed[..idx].trim();
            let raw_value = trimmed[idx + 1..].trim();
            let value =
                if raw_value.starts_with('"') && raw_value.ends_with('"') && raw_value.len() >= 2 {
                    &raw_value[1..raw_value.len() - 1]
                } else {
                    raw_value
                };
            env::set_var(key, value);
        }
    }
    Ok(())
}

// ======================================================================
// Task execution (printing group and task info; errors include line numbers)
// ======================================================================

fn execute_task(
    name: &str,
    ctx: &Context,
    extra_args: &[String],
    executed: &mut HashSet<String>,
) -> Result<(), EvalError> {
    if executed.contains(name) {
        return Ok(());
    }
    let task = ctx.tasks.get(name).ok_or_else(|| EvalError::Other {
        message: format!("Task '{}' not found (or dependency missing)", name),
        line: 0,
    })?;
    for step in &task.steps {
        execute_task(step, ctx, extra_args, executed)?;
    }
    let mut cmd_line = if let Some(shell_cmd) = &task.shell {
        shell_cmd.clone()
    } else if let Some(cmd_tpl) = &task.cmd {
        if let Some(base) = &ctx.base_cmd {
            format!("{} {}", base, cmd_tpl)
        } else {
            cmd_tpl.clone()
        }
    } else {
        return Err(EvalError::Other {
            message: format!("Task '{}' has no command to execute", name),
            line: 0,
        });
    };
    if !extra_args.is_empty() {
        let extra = extra_args.join(" ");
        cmd_line = format!("{} {}", cmd_line, extra);
    }
    let mut interp_env = ctx.defs.clone();
    interp_env.extend(task.props.clone());
    let cmd_line = interpolate(
        &cmd_line,
        &interp_env,
        task.props
            .get("line")
            .and_then(|l| l.parse().ok())
            .unwrap_or(0),
    )?;

    println!("Executing task {}:", name);
    if let Some(desc) = &task.desc {
        println!("  Description: {}", desc);
    }
    if !task.meta.is_empty() {
        println!("  Metadata: {:?}", task.meta);
    }
    println!("  Command: {}", cmd_line);

    let status = Command::new("sh")
        .arg("-c")
        .arg(&cmd_line)
        .status()
        .map_err(|e| EvalError::ExecutionError {
            message: e.to_string(),
            line: 0,
        })?;
    if !status.success() {
        return Err(EvalError::ExecutionError {
            message: format!("Task '{}' exited with status {}", name, status),
            line: 0,
        });
    }
    executed.insert(name.to_string());
    Ok(())
}

// ======================================================================
// Main function
// ======================================================================

fn main() -> Result<(), Box<dyn Error>> {
    let cli = Cli::parse();

    let path = Path::new(&cli.file);
    let dsl_content = fs::read_to_string(path)
        .map_err(|e| format!("Error reading DSL file {}: {}", cli.file, e))?;
    let forms = loads_all(&dsl_content).map_err(|e| format!("Parse error: {}", e))?;
    let mut ctx = Context::new();
    process_forms(&forms, &mut ctx)?;

    if cli.list {
        println!("Available tasks:");
        let mut names: Vec<_> = ctx.tasks.keys().collect();
        names.sort();
        for name in names {
            if let Some(task) = ctx.tasks.get(name) {
                if cli.verbose {
                    println!(
                        "  {}: {}",
                        task.name,
                        task.desc.as_deref().unwrap_or(&task.title)
                    );
                } else {
                    println!("  {}", task.name);
                }
            }
        }
        return Ok(());
    }

    // If no tasks are specified, default to "default"
    let tasks_to_run = if cli.tasks.is_empty() {
        vec!["default".to_string()]
    } else {
        cli.tasks
    };

    let mut executed = HashSet::new();
    for tname in tasks_to_run {
        if let Some(group) = ctx.groups.get(&tname) {
            println!("Group {}:", tname);
            if let Some(desc) = &group.desc {
                println!("  Description: {}", desc);
            }
            if !group.meta.is_empty() {
                println!("  Metadata: {:?}", group.meta);
            }
            let prefix = format!("{}.", tname);
            let mut keys: Vec<_> = ctx
                .tasks
                .keys()
                .filter(|k| k.starts_with(&prefix))
                .cloned()
                .collect();
            keys.sort();
            for key in keys {
                execute_task(&key, &ctx, &cli.extra_args, &mut executed)?;
            }
        } else if ctx.tasks.contains_key(&tname) {
            execute_task(&tname, &ctx, &cli.extra_args, &mut executed)?;
        } else {
            let prefix = format!("{}.", tname);
            let mut keys: Vec<_> = ctx
                .tasks
                .keys()
                .filter(|k| k.starts_with(&prefix))
                .cloned()
                .collect();
            if keys.is_empty() {
                eprintln!("Task or group '{}' not found.", tname);
            } else {
                keys.sort();
                for key in keys {
                    execute_task(&key, &ctx, &cli.extra_args, &mut executed)?;
                }
            }
        }
    }
    Ok(())
}
