from debug import dbg

print(dbg('foo'))
print(dbg("bar"))
print(dbg(",:"))
print(dbg(f"{f'{None}'}"))
print(
    dbg(
        "a" # comment
        "b"
    )
)
