# `dbg!` in Python

The `dbg!` macro in Rust is amazing.
However, Python doesn't support macros and doesn't have a built-in equivalent.

This library provides a solution:

```python
from debug import dbg

x = 4
y = 10
z = dbg(x) + dbg(y)
print(z)
```

The standard output displays:

```
14
```

And the standard error displays:

```
[main.py:5] x = 4
[main.py:5] y = 10
```

## Installation

This library is compatible with Python>=3.11.
Install via `pip` from GitHub:

```bash
pip install git+https://github.com/George-Ogden/dbg.git
```

## Examples

```python
from debug import dbg

# Literals
dbg(8.0) # [main.py:4] 8.0 = 8.0

# Variables
x = 4
dbg(x) # [main.py:8] x = 4

# Expressions
y = 5
dbg(y + 8) # [main.py:11] y + 8 = 13

# Return the input
z = True
z = dbg(not z) # [main.py:16] not z = False
assert not z

# Debug current line number
dbg() # [main.py:20]

# Multiple arguments
minus_two = -2
result = dbg('Foo', minus_two) # [main.py:24] 'Foo' = 'Foo' // [main.py:24] minus_two = -2
assert result == ('Foo', -2)
```

For more examples, see `test_samples/` and `test_suite.py`.

## Limitations

Getting the debug information involves introspecting the code very heavily.
You need a Python interpreter that allows this (which you probably have by default).
If some information is unavailable, a placeholder will be shown, such as `<unknown>`.
