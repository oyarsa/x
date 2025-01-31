# DSL Specification

### Syntax
- S-expression based
- Top-level forms: base-cmd, load-env, load-config, types, def, task, group
- String interpolation with `{var}` syntax

### Types
- Defined in `types` block
- Values can be literals or shell command output
- Runtime type checking with exact string matching
- Type errors show invalid value and allowed options

### Variables & Scope
- Defined in `def` blocks or within tasks/groups
- Lexical scoping with inheritance
- Child scopes can override parent values
- Variables resolved through scope chain, error if not found

### String Interpolation
- Two phases: declaration and usage
- Max depth: 10
- Circular references forbidden
- At usage: all placeholders must resolve

### Expressions
- `or`: Short-circuits on first non-None
- `and`: Short-circuits on first None
- `if`: Conditional with string result
- `equal?`: String comparison with whitespace stripping

### Built-in Functions
- `env`: Environment lookup
- `conf`: Config lookup
- `git-root`: Git repository root
- `current-timestamp`: ISO-8601 timestamp
- `shell`: Execute command
- `from-shell`: Execute and split output

### Tasks & Groups
- Tasks have: name, description, command, optional metadata
- Groups can define shared command template
- Task inheritance of group commands
- Dependencies via `steps`
- Command-line args appended after `--`

### CLI
- `--list`: Show tasks/groups
- `--verbose`: Include descriptions
- `-` for stdin input
- Task selection: `group.task` or `task`

### Error Handling
- No recovery from errors
- Show all relevant information (valid types, missing vars)
- Stop execution on first error
