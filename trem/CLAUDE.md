# trem - Utility Tools

## Build Commands
- Build: `just build` or `cargo build`
- Run: `just run` or `cargo run`
- Install: `just install` or `cargo install --path .`
- Release build: `just release` or `cargo build --release`

## Test Commands
- Run tests: `just test` or `cargo test`
- Run single test: `cargo test test_name`

## Lint Commands
- Run all lints: `just lint`
- Run clippy: `just clippy` or `cargo clippy -- -D warnings`
- Check formatting: `just fmt-check` or `cargo fmt -- --check`
- Format code: `just fmt` or `cargo fmt`
- Check all (lint + test): `just check-all`

## Code Style Guidelines
- Edition: Rust 2021
- Error handling: Use `macro_rules! die` for fatal errors
- Naming: Snake case for functions/variables, CamelCase for types
- Documentation: Use doc comments `///` for public items
- Architecture: Each subcommand has its own module
- Imports: Group std imports first, then external crates
- Prefer Result types over unwrap/expect in public APIs