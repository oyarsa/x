//! A single–file evaluator for our DSL.
//!
//! It uses the provided S–expression parser and supports the DSL forms:
//!   base-cmd, load-env, load-config, types, def, task, and group.
//!
//! It also implements built–in functions (or, and, if, equal?, env, conf,
//! git-root, current-timestamp, shell, from-shell) and does string interpolation
//! for values (using {var} syntax with a maximum depth of 10).
//!
//! The CLI supports “--list” (to list available tasks) and running tasks (by name,
//! or by group name). Tasks may have dependencies (steps) and will be executed in order.

use chrono::Utc;
use regex::Regex;
use serde_json::Value as JsonValue;
use std::collections::{HashMap, HashSet};
use std::env;
use std::error::Error;
use std::fmt;
use std::fs;
use std::path::Path;
use std::process::Command;

// ======================================================================
// S–Expression parser (from the provided main.rs)
// ======================================================================

#[derive(Debug, Clone, PartialEq)]
pub enum SExp {
    Symbol(String),
    String(String),
    List(Vec<SExp>),
    Quoted(Box<SExp>),
}

#[derive(Debug)]
pub enum ParseError {
    UnexpectedEOF,
    UnterminatedString,
    UnclosedParen,
    UnexpectedCloseParen,
    EmptyQuoted,
    UnexpectedContent(String),
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Self::UnexpectedEOF => write!(f, "Unexpected end of input"),
            Self::UnterminatedString => write!(f, "Unclosed string literal"),
            Self::UnclosedParen => write!(f, "Unclosed parenthesis"),
            Self::UnexpectedCloseParen => write!(f, "Unexpected closing parenthesis"),
            Self::EmptyQuoted => write!(f, "Empty quoted expression"),
            Self::UnexpectedContent(s) => write!(f, "Unexpected content after expression: {}", s),
        }
    }
}

impl Error for ParseError {}

impl fmt::Display for SExp {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            SExp::Symbol(s) => write!(f, "{}", quote_symbol(s)),
            SExp::String(s) => write!(f, "\"{}\"", quote_string(s)),
            SExp::List(items) => {
                write!(f, "(")?;
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        write!(f, " ")?;
                    }
                    write!(f, "{}", item)?;
                }
                write!(f, ")")
            }
            SExp::Quoted(exp) => write!(f, "'{}", exp),
        }
    }
}

fn quote_string(s: &str) -> String {
    s.replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
        .replace('\u{0008}', "\\b")
        .replace('\u{000C}', "\\f")
}

fn quote_symbol(s: &str) -> String {
    let mut result = s.to_string();
    for (pattern, replacement) in [
        ("\\", "\\\\"),
        ("'", "\\'"),
        ("`", "\\`"),
        ("\"", "\\\""),
        ("(", "\\("),
        (")", "\\)"),
        ("[", "\\["),
        ("]", "\\]"),
        (" ", "\\ "),
        (",", "\\,"),
        ("?", "\\?"),
        (";", "\\;"),
        ("#", "\\#"),
    ] {
        result = result.replace(pattern, replacement);
    }
    result
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

    fn parse_sexp(&mut self) -> Result<SExp, ParseError> {
        let chars: Vec<char> = self.text.chars().collect();
        // Skip whitespace and comments.
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
            return Err(ParseError::UnexpectedEOF);
        }
        match chars[self.pos] {
            '(' => {
                self.pos += 1;
                let mut list = Vec::new();
                while self.pos < chars.len() && chars[self.pos] != ')' {
                    list.push(self.parse_sexp()?);
                }
                if self.pos >= chars.len() {
                    return Err(ParseError::UnclosedParen);
                }
                self.pos += 1; // skip ')'
                Ok(SExp::List(list))
            }
            ')' => Err(ParseError::UnexpectedCloseParen),
            '"' => self.parse_string(&chars),
            '\'' => {
                self.pos += 1;
                let quoted = self.parse_sexp()?;
                Ok(SExp::Quoted(Box::new(quoted)))
            }
            _ => self.parse_atom(&chars),
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
                    return Ok(SExp::String(result));
                }
                '\\' => {
                    self.pos += 1;
                    if self.pos >= chars.len() {
                        return Err(ParseError::UnterminatedString);
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
        Err(ParseError::UnterminatedString)
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
            s if s == self.nil => SExp::List(vec![]),
            s if s == self.true_val => SExp::Symbol("true".to_string()),
            s if Some(s) == self.false_val => SExp::Symbol("false".to_string()),
            _ => {
                if let Ok(n) = token.parse::<i64>() {
                    SExp::Symbol(n.to_string())
                } else if let Ok(f) = token.parse::<f64>() {
                    SExp::Symbol(f.to_string())
                } else {
                    SExp::Symbol(token)
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

/// Repeatedly parse one S–expression at a time from the input string.
/// This function returns a vector of top–level forms.
pub fn loads_all(s: &str) -> Result<Vec<SExp>, ParseError> {
    let mut forms = Vec::new();
    let mut parser = Parser::new(s, "nil", "t", None, ';');
    let chars: Vec<char> = s.chars().collect();
    while parser.pos < chars.len() {
        // Skip whitespace and comments.
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
        // Expect each top-level form to begin with '('.
        if chars[parser.pos] != '(' {
            return Err(ParseError::UnexpectedContent(format!(
                "Expected '(' at position {}",
                parser.pos
            )));
        }
        let form = parser.parse_sexp()?;
        forms.push(form);
    }
    Ok(forms)
}

pub fn dumps(exp: &SExp, pretty: bool) -> String {
    if pretty {
        dumps_pretty(exp, "  ", 0)
    } else {
        exp.to_string()
    }
}

fn dumps_pretty(exp: &SExp, indent: &str, level: usize) -> String {
    match exp {
        SExp::String(_) | SExp::Symbol(_) => exp.to_string(),
        SExp::List(items) if items.is_empty() => "()".to_string(),
        SExp::List(items) => {
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
        SExp::Quoted(inner) => format!("'{}", dumps_pretty(inner, indent, level)),
    }
}

// ======================================================================
// DSL Evaluator implementation
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
            _ => Err(EvalError::Other("Expected string value".into())),
        }
    }
}

#[derive(Debug)]
enum EvalError {
    UndefinedVariable(String),
    UnknownFunction(String),
    InvalidFunctionCall,
    NonLiteralInQuoted,
    InterpolationDepthExceeded,
    TypeError {
        var: String,
        value: String,
        allowed: Vec<String>,
    },
    ExecutionError(String),
    Other(String),
}

impl fmt::Display for EvalError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            EvalError::UndefinedVariable(var) => write!(f, "Undefined variable: {}", var),
            EvalError::UnknownFunction(func) => write!(f, "Unknown function: {}", func),
            EvalError::InvalidFunctionCall => write!(f, "Invalid function call"),
            EvalError::NonLiteralInQuoted => write!(f, "Non–literal value in quoted expression"),
            EvalError::InterpolationDepthExceeded => write!(f, "Interpolation depth exceeded"),
            EvalError::TypeError {
                var,
                value,
                allowed,
            } => write!(
                f,
                "Type error for variable {}: value {} is not one of allowed: {:?}",
                var, value, allowed
            ),
            EvalError::ExecutionError(s) => write!(f, "Execution error: {}", s),
            EvalError::Other(s) => write!(f, "Error: {}", s),
        }
    }
}

impl Error for EvalError {}

struct Context {
    base_cmd: Option<String>,
    config: Option<JsonValue>,
    types: HashMap<String, Vec<String>>,
    defs: HashMap<String, String>,
    tasks: HashMap<String, Task>,
}

impl Context {
    fn new() -> Self {
        Self {
            base_cmd: None,
            config: None,
            types: HashMap::new(),
            defs: HashMap::new(),
            tasks: HashMap::new(),
        }
    }
}

#[derive(Debug, Clone)]
struct Task {
    name: String,  // fully qualified (e.g. "eval.accuracy")
    title: String, // a short description
    desc: Option<String>,
    meta: HashMap<String, String>,
    cmd: Option<String>,
    shell: Option<String>,
    params: Option<String>,
    steps: Vec<String>,
    props: HashMap<String, String>,
}

fn eval_expr(exp: &SExp, env: &HashMap<String, String>, ctx: &Context) -> Result<Value, EvalError> {
    match exp {
        SExp::String(s) => {
            let interped = interpolate(s, env)?;
            Ok(Value::Str(interped))
        }
        SExp::Symbol(s) => {
            if let Some(val) = env.get(s) {
                Ok(Value::Str(val.clone()))
            } else {
                Err(EvalError::UndefinedVariable(s.clone()))
            }
        }
        SExp::List(list) => {
            if list.is_empty() {
                return Ok(Value::None);
            }
            let func = match &list[0] {
                SExp::Symbol(s) => s.as_str(),
                _ => return Err(EvalError::InvalidFunctionCall),
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
                        return Err(EvalError::InvalidFunctionCall);
                    }
                    let cond = eval_expr(&list[1], env, ctx)?;
                    let cond_val = cond.as_str()?;
                    if cond_val.trim() == "true" {
                        eval_expr(&list[2], env, ctx)
                    } else {
                        eval_expr(&list[3], env, ctx)
                    }
                }
                "equal?" => {
                    if list.len() != 3 {
                        return Err(EvalError::InvalidFunctionCall);
                    }
                    let a = eval_expr(&list[1], env, ctx)?;
                    let a = a.as_str()?.trim();
                    let b = eval_expr(&list[2], env, ctx)?;
                    let b = b.as_str()?.trim();
                    Ok(Value::Str(
                        if a == b { "true" } else { "false" }.to_string(),
                    ))
                }
                "env" => {
                    if list.len() != 2 {
                        return Err(EvalError::InvalidFunctionCall);
                    }
                    let var = eval_expr(&list[1], env, ctx)?.as_str()?.to_string();
                    match env::var(&var) {
                        Ok(val) => Ok(Value::Str(val)),
                        Err(_) => Ok(Value::None),
                    }
                }
                "conf" => {
                    if list.len() != 2 {
                        return Err(EvalError::InvalidFunctionCall);
                    }
                    let key = eval_expr(&list[1], env, ctx)?.as_str()?.to_string();
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
                        .map_err(|e| EvalError::ExecutionError(e.to_string()))?;
                    let s = String::from_utf8_lossy(&output.stdout).trim().to_string();
                    Ok(Value::Str(s))
                }
                "current-timestamp" => {
                    let now = Utc::now().to_rfc3339();
                    Ok(Value::Str(now))
                }
                "shell" => {
                    if list.len() != 2 {
                        return Err(EvalError::InvalidFunctionCall);
                    }
                    let cmd_str = eval_expr(&list[1], env, ctx)?.as_str()?.to_string();
                    let output = Command::new("sh")
                        .arg("-c")
                        .arg(&cmd_str)
                        .output()
                        .map_err(|e| EvalError::ExecutionError(e.to_string()))?;
                    let s = String::from_utf8_lossy(&output.stdout).trim().to_string();
                    Ok(Value::Str(s))
                }
                "from-shell" => {
                    if list.len() != 2 {
                        return Err(EvalError::InvalidFunctionCall);
                    }
                    let cmd_str = eval_expr(&list[1], env, ctx)?.as_str()?.to_string();
                    let output = Command::new("sh")
                        .arg("-c")
                        .arg(&cmd_str)
                        .output()
                        .map_err(|e| EvalError::ExecutionError(e.to_string()))?;
                    let s = String::from_utf8_lossy(&output.stdout);
                    let parts: Vec<String> = s.split_whitespace().map(|s| s.to_string()).collect();
                    Ok(Value::List(parts))
                }
                _ => Err(EvalError::UnknownFunction(func.to_string())),
            }
        }
        SExp::Quoted(inner) => match &**inner {
            SExp::List(items) => {
                let mut vec = Vec::new();
                for item in items {
                    match item {
                        SExp::String(s) => vec.push(s.clone()),
                        SExp::Symbol(s) => vec.push(s.clone()),
                        _ => return Err(EvalError::NonLiteralInQuoted),
                    }
                }
                Ok(Value::List(vec))
            }
            other => eval_expr(other, env, ctx),
        },
    }
}

fn interpolate(s: &str, env: &HashMap<String, String>) -> Result<String, EvalError> {
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
                return Err(EvalError::UndefinedVariable(key.to_string()));
            }
        }
        result = replaced;
    }
    if re.is_match(&result) {
        Err(EvalError::InterpolationDepthExceeded)
    } else {
        Ok(result)
    }
}

// ======================================================================
// DSL top–level forms processing
// ======================================================================

fn process_forms(forms: &[SExp], ctx: &mut Context) -> Result<(), EvalError> {
    for form in forms {
        if let SExp::List(items) = form {
            if items.is_empty() {
                continue;
            }
            if let SExp::Symbol(ref form_name) = items[0] {
                match form_name.as_str() {
                    "base-cmd" => {
                        if items.len() != 2 {
                            return Err(EvalError::Other("base-cmd requires one argument".into()));
                        }
                        if let SExp::String(s) = &items[1] {
                            ctx.base_cmd = Some(s.clone());
                        } else {
                            return Err(EvalError::Other(
                                "base-cmd argument must be a string".into(),
                            ));
                        }
                    }
                    "load-env" => {
                        if items.len() != 2 {
                            return Err(EvalError::Other("load-env requires one argument".into()));
                        }
                        if let SExp::String(fname) = &items[1] {
                            load_env(fname)?;
                        } else {
                            return Err(EvalError::Other(
                                "load-env argument must be a string".into(),
                            ));
                        }
                    }
                    "load-config" => {
                        if items.len() != 2 {
                            return Err(EvalError::Other(
                                "load-config requires one argument".into(),
                            ));
                        }
                        if let SExp::String(fname) = &items[1] {
                            let content = fs::read_to_string(fname).map_err(|e| {
                                EvalError::Other(format!(
                                    "Error reading config file '{}': {}. Please ensure the file exists and is accessible.",
                                    fname, e
                                ))
                            })?;
                            let json: JsonValue = serde_json::from_str(&content).map_err(|e| {
                                EvalError::Other(format!(
                                    "Error parsing JSON in config file '{}': {}.",
                                    fname, e
                                ))
                            })?;
                            ctx.config = Some(json);
                        } else {
                            return Err(EvalError::Other(
                                "load-config argument must be a string".into(),
                            ));
                        }
                    }
                    "types" => {
                        for type_def in &items[1..] {
                            if let SExp::List(def_items) = type_def {
                                if def_items.len() != 2 {
                                    return Err(EvalError::Other(format!(
                                        "Malformed type definition: expected exactly 2 parts (type name and allowed values), but found {} parts in: {}. This may indicate that your DSL file is not correctly separated into top-level forms.",
                                        def_items.len(),
                                        dumps(type_def, false)
                                    )));
                                }
                                let type_name = if let SExp::Symbol(s) = &def_items[0] {
                                    s.clone()
                                } else {
                                    return Err(EvalError::Other(format!(
                                        "Invalid type name in type definition: {}",
                                        dumps(&def_items[0], false)
                                    )));
                                };
                                let allowed_val = eval_expr(&def_items[1], &ctx.defs, ctx)?;
                                let allowed = match allowed_val {
                                    Value::List(v) => v,
                                    Value::Str(s) => vec![s],
                                    _ => {
                                        return Err(EvalError::Other(format!(
                                            "Type allowed-values for '{}' must be a list or string, but got: {}",
                                            type_name,
                                            dumps(&def_items[1], false)
                                        )))
                                    }
                                };
                                ctx.types.insert(type_name, allowed);
                            } else {
                                return Err(EvalError::Other(format!(
                                    "Invalid type definition: expected a list, got: {}",
                                    dumps(type_def, false)
                                )));
                            }
                        }
                    }
                    "def" => {
                        for def_item in &items[1..] {
                            if let SExp::List(parts) = def_item {
                                if parts.len() != 2 {
                                    return Err(EvalError::Other(
                                        "Each def entry must have a key and a value".into(),
                                    ));
                                }
                                let (var_name, type_opt) = match &parts[0] {
                                    SExp::Symbol(s) => (s.clone(), None),
                                    SExp::List(inner) if inner.len() == 2 => {
                                        let raw_var = if let SExp::Symbol(s) = &inner[0] {
                                            s.trim_start_matches('[').to_string()
                                        } else {
                                            return Err(EvalError::Other("Invalid def key".into()));
                                        };
                                        let raw_type = if let SExp::Symbol(s) = &inner[1] {
                                            s.trim_end_matches(']').to_string()
                                        } else {
                                            return Err(EvalError::Other(
                                                "Invalid def type".into(),
                                            ));
                                        };
                                        (raw_var, Some(raw_type))
                                    }
                                    _ => {
                                        return Err(EvalError::Other(
                                            "Invalid def key format".into(),
                                        ))
                                    }
                                };
                                let val = eval_expr(&parts[1], &ctx.defs, ctx)?;
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
                                            });
                                        }
                                    }
                                }
                                ctx.defs.insert(var_name, val_str);
                            } else {
                                return Err(EvalError::Other("Invalid def entry".into()));
                            }
                        }
                    }
                    "task" => {
                        let task = process_task(items, None)?;
                        ctx.tasks.insert(task.name.clone(), task);
                    }
                    "group" => {
                        process_group(items, ctx)?;
                    }
                    other => {
                        return Err(EvalError::Other(format!(
                            "Unknown top-level form: {}",
                            other
                        )))
                    }
                }
            } else {
                return Err(EvalError::Other(
                    "Expected a symbol at the beginning of the form".into(),
                ));
            }
        } else {
            return Err(EvalError::Other(
                "Expected a list for a top-level form".into(),
            ));
        }
    }
    Ok(())
}

fn process_task(items: &[SExp], parent: Option<&Task>) -> Result<Task, EvalError> {
    if items.len() < 3 {
        return Err(EvalError::Other("Task definition too short".into()));
    }
    let raw_name = match &items[1] {
        SExp::Symbol(s) => s.clone(),
        _ => return Err(EvalError::Other("Task name must be a symbol".into())),
    };
    let name = if let Some(p) = parent {
        format!("{}.{}", p.name, raw_name)
    } else {
        raw_name
    };
    let title = match &items[2] {
        SExp::String(s) => s.clone(),
        _ => return Err(EvalError::Other("Task title must be a string".into())),
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
        if let SExp::List(prop_items) = prop {
            if prop_items.is_empty() {
                continue;
            }
            let key = if let SExp::Symbol(s) = &prop_items[0] {
                s.as_str()
            } else {
                continue;
            };
            match key {
                "desc" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s) = &prop_items[1] {
                            task.desc = Some(s.clone());
                        }
                    }
                }
                "meta" => {
                    for meta_prop in &prop_items[1..] {
                        if let SExp::List(pair) = meta_prop {
                            if pair.len() == 2 {
                                let mkey = match &pair[0] {
                                    SExp::Symbol(s) | SExp::String(s) => s.clone(),
                                    _ => continue,
                                };
                                let mval = match &pair[1] {
                                    SExp::Symbol(s) | SExp::String(s) => s.clone(),
                                    _ => continue,
                                };
                                task.meta.insert(mkey, mval);
                            }
                        }
                    }
                }
                "cmd" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s) = &prop_items[1] {
                            task.cmd = Some(s.clone());
                        }
                    }
                }
                "shell" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s) = &prop_items[1] {
                            task.shell = Some(s.clone());
                        }
                    }
                }
                "params" => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s) = &prop_items[1] {
                            task.params = Some(s.clone());
                        }
                    }
                }
                "steps" => {
                    for step in &prop_items[1..] {
                        if let SExp::Symbol(s) = step {
                            task.steps.push(s.clone());
                        }
                    }
                }
                _ => {
                    if prop_items.len() >= 2 {
                        if let SExp::String(s) = &prop_items[1] {
                            task.props.insert(key.to_string(), s.clone());
                        } else if let SExp::Symbol(s) = &prop_items[1] {
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
        return Err(EvalError::Other("Group definition too short".into()));
    }
    let group_name = match &items[1] {
        SExp::Symbol(s) => s.clone(),
        _ => return Err(EvalError::Other("Group name must be a symbol".into())),
    };
    let group_title = match &items[2] {
        SExp::String(s) => s.clone(),
        _ => return Err(EvalError::Other("Group title must be a string".into())),
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
        if let SExp::List(prop_items) = prop {
            if prop_items.is_empty() {
                continue;
            }
            if let SExp::Symbol(key) = &prop_items[0] {
                match key.as_str() {
                    "desc" => {
                        if prop_items.len() >= 2 {
                            if let SExp::String(s) = &prop_items[1] {
                                group_task.desc = Some(s.clone());
                            }
                        }
                    }
                    "params" => {
                        if prop_items.len() >= 2 {
                            if let SExp::String(s) = &prop_items[1] {
                                group_task.params = Some(s.clone());
                            }
                        }
                    }
                    "cmd" => {
                        if prop_items.len() >= 2 {
                            if let SExp::String(s) = &prop_items[1] {
                                group_task.cmd = Some(s.clone());
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
    }
    for prop in &items[3..] {
        if let SExp::List(prop_items) = prop {
            if !prop_items.is_empty() {
                if let SExp::Symbol(key) = &prop_items[0] {
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

fn load_env(fname: &str) -> Result<(), EvalError> {
    let content = fs::read_to_string(fname).map_err(|e| {
        EvalError::Other(format!(
            "Error reading .env file '{}': {}. Please ensure the file exists in the expected location.",
            fname, e
        ))
    })?;
    for line in content.lines() {
        let trimmed = line.trim();
        // Skip comments and empty lines.
        if trimmed.starts_with('#') || trimmed.is_empty() {
            continue;
        }
        if let Some(idx) = trimmed.find('=') {
            let key = trimmed[..idx].trim();
            let raw_value = trimmed[idx + 1..].trim();
            // If the value is enclosed in double quotes, remove them.
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

fn execute_task(
    name: &str,
    ctx: &Context,
    extra_args: &[String],
    executed: &mut HashSet<String>,
) -> Result<(), EvalError> {
    if executed.contains(name) {
        return Ok(());
    }
    let task = ctx.tasks.get(name).ok_or_else(|| {
        EvalError::Other(format!("Task '{}' not found (or dependency missing)", name))
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
        return Err(EvalError::Other(format!(
            "Task '{}' has no command to execute",
            name
        )));
    };
    if !extra_args.is_empty() {
        let extra = extra_args.join(" ");
        cmd_line = format!("{} {}", cmd_line, extra);
    }
    // Merge the global definitions with the task's own properties
    let mut interp_env = ctx.defs.clone();
    interp_env.extend(task.props.clone());
    let cmd_line = interpolate(&cmd_line, &interp_env)?;
    println!("Executing task {}: {}", name, cmd_line);
    // let status = Command::new("sh")
    //     .arg("-c")
    //     .arg(&cmd_line)
    //     .status()
    //     .map_err(|e| EvalError::ExecutionError(e.to_string()))?;
    // if !status.success() {
    //     return Err(EvalError::ExecutionError(format!(
    //         "Task '{}' exited with status {}",
    //         name, status
    //     )));
    // }
    executed.insert(name.to_string());
    Ok(())
}

// ======================================================================
// Main – load DSL file, process it, and run CLI commands.
// ======================================================================

fn main() -> Result<(), Box<dyn Error>> {
    let path = Path::new("spec.dsl");
    let dsl_content =
        fs::read_to_string(path).map_err(|e| format!("Error reading DSL file spec.dsl: {}", e))?;
    // Parse all top-level forms.
    let forms = loads_all(&dsl_content).map_err(|e| format!("Parse error: {}", e))?;
    let mut ctx = Context::new();
    process_forms(&forms, &mut ctx)?;
    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() || args[0] == "--list" {
        println!("Available tasks:");
        let verbose = args.iter().any(|s| s == "--verbose");
        let mut names: Vec<_> = ctx.tasks.keys().collect();
        names.sort();
        for name in names {
            if let Some(task) = ctx.tasks.get(name) {
                if verbose {
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
    } else {
        let mut task_names = Vec::new();
        let mut extra_args = Vec::new();
        let mut iter = args.iter();
        while let Some(arg) = iter.next() {
            if arg == "--" {
                extra_args = iter.map(|s| s.to_string()).collect();
                break;
            } else {
                task_names.push(arg.to_string());
            }
        }
        let mut executed = HashSet::new();
        for tname in task_names {
            if ctx.tasks.contains_key(&tname) {
                execute_task(&tname, &ctx, &extra_args, &mut executed)?;
            } else {
                let mut found = false;
                let prefix = format!("{}.", tname);
                let mut keys: Vec<_> = ctx
                    .tasks
                    .keys()
                    .filter(|k| k.starts_with(&prefix))
                    .cloned()
                    .collect();
                keys.sort();
                for key in keys {
                    execute_task(&key, &ctx, &extra_args, &mut executed)?;
                    found = true;
                }
                if !found {
                    eprintln!("Task or group '{}' not found.", tname);
                }
            }
        }
    }
    Ok(())
}
