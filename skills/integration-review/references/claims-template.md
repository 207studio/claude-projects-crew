# Claims block — paste into a worker's (subagent's or thread's) prompt

~~~text
When you finish, end your final message with a fenced block tagged `claims`
containing a JSON list. One entry per checkable statement you make about your
output. Do not claim anything you did not measure. If you did not finish, say
so and still list what exists. Paths are relative to the repository root.

Types: file_exists, file_absent, max_chars, min_chars, max_lines, contains,
not_contains, regex, json_valid, changed_within, command.
Add "claimed" with your own measured value.

Example:
```claims
[
  {"type": "file_exists", "path": "drafts/post.txt"},
  {"type": "max_chars", "path": "drafts/post.txt", "max": 280, "mode": "x_weighted", "claimed": 262},
  {"type": "changed_within", "base": "main", "allowed": ["drafts/*"]},
  {"type": "command", "run": "npm test", "expect_exit": 0, "claimed": "42 passed"}
]
```
~~~

The coordinator then runs:

```bash
python3 <skill-dir>/scripts/verify_claims.py report.md --root .
```

A worker that ends without this block yields exit code 2 (UNVERIFIED).
