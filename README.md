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

And the standard error displays (in color if you run it yourself):

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
dbg(8.0) # [main.py:4:1] 8.0 = 8.0

# Variables
x = 4
dbg(x) # [main.py:8:1] x = 4

# Expressions
y = 5
dbg(y + 8) # [main.py:11:1] y + 8 = 13

# Return the input
z = True
z = dbg(not z) # [main.py:16:5] not z = False
assert not z

# Pretty print items and code (on larger examples)
dbg([1] * 2) # [main.py:20:1] [1] * 2 = [1, 1]

# Debug current line/col number
dbg() # [main.py:20:1]

# Multiple arguments
minus_two = -2
result = dbg('Foo', minus_two) # [main.py:24:10] 'Foo' = 'Foo' // [main.py:24:10] minus_two = -2
assert result == ('Foo', -2)
```

For more examples, see `test_samples/` and `test_suite.py`.

## Limitations

Getting the debug information involves introspecting the code very heavily.
You need a Python interpreter that allows this (which you probably have by default).
If some information is unavailable, a placeholder will be shown, such as `<unknown>`.

## Advanced Features

`dbg` automatically detects whether ANSI codes are supported by your terminal and uses color if available.
This detection may occasionally fail and you can override it like this:

```python
from debug import CONFIG

CONFIG.color = True # enable
CONFIG.color = False # disable
```

Additionally, if you want to change the color scheme:

```python
from debug import CONFIG

CONFIG.style = "github-dark"
CONFIG.style = "monokai"
```

See a full list of styles at https://pygments.org/styles/.

And if you want the pretty-printing to use a different indent width (default = 2):

```python
from debug import CONFIG

CONFIG.indent = 4
CONFIG.indent = 8
```

### Persistent Config

You can also change the settings by placing a `debug/dbg.conf` in your user config folder or a `dbg.conf` file in your local directory (higher precedence).

```ini
[dbg]
color = yes # always show color
style = github-dark # change the style
indent = 4 # increase the indent size
```

That means that your favorite theme is always loaded or you can disable color if it is misdetected.
