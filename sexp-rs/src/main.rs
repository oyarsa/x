use std::error::Error;
use std::fmt;

fn main() -> Result<(), Box<dyn Error>> {
    let input = r#"(types
                     (model '("4o" "4o-mini"))
                     (dataset '("full" "subset")))"#;

    let expr = loads(input)?;
    println!("Parsed expression:\n{}", dumps(&expr, true));
    Ok(())
}

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

    pub fn parse(&mut self) -> Result<Vec<SExp>, ParseError> {
        let result = self.parse_sexp()?;
        if self.pos < self.text.len() {
            return Err(ParseError::UnexpectedContent(
                self.text[self.pos..].to_string(),
            ));
        }

        let open_count = self.text.chars().filter(|&c| c == '(').count();
        let close_count = self.text.chars().filter(|&c| c == ')').count();

        match (open_count, close_count) {
            (o, c) if o > c => Err(ParseError::UnclosedParen),
            (o, c) if c > o => Err(ParseError::UnexpectedCloseParen),
            _ => Ok(result),
        }
    }

    fn parse_sexp(&mut self) -> Result<Vec<SExp>, ParseError> {
        let mut results = Vec::new();
        let chars: Vec<char> = self.text.chars().collect();

        while self.pos < chars.len() {
            match chars[self.pos] {
                ' ' | '\t' | '\n' | '\r' => self.pos += 1,
                '"' => results.push(self.parse_string(&chars)?),
                '(' => {
                    self.pos += 1;
                    results.push(SExp::List(self.parse_sexp()?));
                }
                ')' => {
                    self.pos += 1;
                    break;
                }
                '\'' => {
                    self.pos += 1;
                    let quoted = self.parse_sexp()?;
                    if quoted.is_empty() {
                        return Err(ParseError::EmptyQuoted);
                    }
                    results.push(SExp::Quoted(Box::new(quoted[0].clone())));
                }
                c if c == self.line_comment => self.skip_comment(&chars),
                _ => results.push(self.parse_atom(&chars)?),
            }
        }

        Ok(results)
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

pub fn loads(s: &str) -> Result<SExp, ParseError> {
    let mut parser = Parser::new(s, "nil", "t", None, ';');
    let result = parser.parse()?;
    if result.is_empty() {
        return Ok(SExp::List(vec![]));
    }
    Ok(result[0].clone())
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_parsing() {
        assert_eq!(
            loads(r#""hello""#).unwrap(),
            SExp::String("hello".to_string())
        );
        assert_eq!(loads("symbol").unwrap(), SExp::Symbol("symbol".to_string()));
        assert_eq!(
            loads("(a b)").unwrap(),
            SExp::List(vec![
                SExp::Symbol("a".to_string()),
                SExp::Symbol("b".to_string())
            ])
        );
    }

    #[test]
    fn test_nested_expressions() {
        let exp = loads("(define (square x) (* x x))").unwrap();
        if let SExp::List(items) = exp {
            assert_eq!(items.len(), 3);
            assert_eq!(items[0], SExp::Symbol("define".to_string()));
        } else {
            panic!("Expected List");
        }
    }

    #[test]
    fn test_quoted_expressions() {
        let exp = loads("'(a b c)").unwrap();
        if let SExp::Quoted(inner) = exp {
            if let SExp::List(items) = *inner {
                assert_eq!(items.len(), 3);
            } else {
                panic!("Expected List inside Quote");
            }
        } else {
            panic!("Expected Quoted");
        }
    }

    #[test]
    fn test_strings() {
        let cases = [
            r#""""#,
            r#""hello""#,
            r#""hello \"world\"""#,
            r#""hello\nworld""#,
        ];
        for case in cases {
            let parsed = loads(case).unwrap();
            assert!(matches!(parsed, SExp::String(_)));
        }
    }

    #[test]
    fn test_comments() {
        assert_eq!(
            loads("(a b) ; comment").unwrap(),
            SExp::List(vec![
                SExp::Symbol("a".to_string()),
                SExp::Symbol("b".to_string())
            ])
        );
    }

    #[test]
    fn test_special_values() {
        assert_eq!(loads("nil").unwrap(), SExp::List(vec![]));
        assert_eq!(loads("t").unwrap(), SExp::Symbol("true".to_string()));
    }

    #[test]
    fn test_roundtrip() {
        let cases = [
            "(a b c)",
            r#""hello""#,
            "(a (b c) d)",
            "'(quote me)",
            "(define x 42)",
        ];
        for case in cases {
            let parsed = loads(case).unwrap();
            let dumped = dumps(&parsed, false);
            assert_eq!(loads(&dumped).unwrap(), parsed);
        }
    }

    #[test]
    fn test_error_handling() {
        assert!(loads("(unclosed").is_err());
        assert!(loads(r#""unclosed"#).is_err());
        assert!(loads(")").is_err());
    }

    #[test]
    fn test_pretty_printing() {
        let exp = loads("(define (factorial n) (if (= n 0) 1 (* n (factorial (- n 1)))))").unwrap();
        let pretty = dumps(&exp, true);
        assert!(pretty.contains('\n'));
        assert_eq!(loads(&pretty).unwrap(), exp);
    }
}
