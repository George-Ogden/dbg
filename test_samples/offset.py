from debug import dbg

def foo():
    ...

def bar(arg):
    return dbg(arg)

print(bar(5))
