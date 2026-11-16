# Roadmap

## Shipped in 0.1

- One-skill directory and snapshot comparison.
- Whole-directory byte hashes, binary change detection, and strict input errors.
- Literal signal deltas with source evidence.
- Static reference graph, cycle handling, and before/after routes.
- Text, JSON, Markdown, and standalone responsive HTML.
- CI exit policies, demo fixtures, bilingual README, regression tests.

## Next: validate usefulness

1. Collect redistributable real-world updates and measure missed references and noisy signals.
2. Improve Markdown reference coverage based on those fixtures (reference-style links, angle-bracket paths with spaces).
3. Add Git-ref comparison with explicit revision verification and no automatic checkout modification.
4. Add collection discovery with separate, stable identities for each skill.
5. Publish package artifacts after release checks and package-name ownership are confirmed.

## Only after demand is demonstrated

- MCP wrapper returning structured review artifacts.
- SARIF integration, with precisely documented locations and baseline semantics.
- Optional syntax-aware extractors that preserve the zero-dependency baseline CLI.

No release dates are promised. Issues with sanitized input fixtures are the best way to prioritize work.
