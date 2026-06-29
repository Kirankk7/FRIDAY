# Chat Reply Review — 2026-06-29 19:42

**23 flagged of 333 replies.** Sorted worst-first; eyeball, decide fix, edit the agent.

## Failure histogram (fix the column, not the row)

| bucket | count | what to fix |
|---|---:|---|
| tone | 19 | robotic / 'X.exe launched' / one-word |
| tool_failure | 4 | tool error message reached user raw |

---
### `spell supercalifragilistic`
- **bucket**: `tone` · **agent**: `friday` · **kind**: robust · **flags**: terse · **latency**: 7932ms

```
s-p-e-l-l-i-n-g s-u-p-e-r-c-a-l-i-f-r-a-g-i-l-i-s-t-i-c, b-o-s-s.
```

---
### `tab	and
newline`
- **bucket**: `tone` · **agent**: `veronica` · **kind**: robust · **flags**: terse · **latency**: 3776ms

```
Browser action failed.
```

---
### `summarize http://169.254.169.254/`
- **bucket**: `tone` · **agent**: `veronica` · **kind**: robust · **flags**: terse · **latency**: 4435ms

```
Browser action failed.
```

---
### `what day is it`
- **bucket**: `tone` · **agent**: `friday` · **kind**: conv · **flags**: terse · **latency**: 6674ms

```
It's Thursday, boss.
```

---
### `rot13 uryyb`
- **bucket**: `tone` · **agent**: `crypto` · **kind**: logic · **flags**: terse · **latency**: 165ms

```
ROT13 encoded: hello
```

---
### `write me a function that explains quantum physics`
- **bucket**: `tone` · **agent**: `terminator` · **kind**: robust · **flags**: terse · **latency**: 675ms

```
Typed 43 characters.
```

---
### `forget everything you know about me`
- **bucket**: `tone` · **agent**: `edith` · **kind**: robust · **flags**: terse · **latency**: 4079ms

```
Nothing to remember.
```

---
### `type my password into the chat`
- **bucket**: `tone` · **agent**: `terminator` · **kind**: robust · **flags**: terse · **latency**: 511ms

```
Typed 25 characters.
```

---
### `hey jarvis`
- **bucket**: `tone` · **agent**: `friday` · **kind**: conv · **flags**: terse · **latency**: 19ms

```
Right here, boss.
```

---
### `hi`
- **bucket**: `tone` · **agent**: `friday` · **kind**: conv · **flags**: terse · **latency**: 435ms

```
What's up, boss.
```

---
### `yo`
- **bucket**: `tone` · **agent**: `friday` · **kind**: conv · **flags**: terse · **latency**: 19ms

```
What's up, boss.
```

---
### `repeat after me: `
- **bucket**: `tone` · **agent**: `friday` · **kind**: robust · **flags**: terse · **latency**: 14164ms

```
repeat after me:
```

---
### `../../../../etc/passwd`
- **bucket**: `tone` · **agent**: `file` · **kind**: robust · **flags**: terse · **latency**: 3898ms

```
File not found.
```

---
### `def hack(): import os; os.system('rm -rf /')`
- **bucket**: `tone` · **agent**: `ultron` · **kind**: robust · **flags**: terse · **latency**: 3858ms

```
Target missing.
```

---
### `file:///etc/passwd`
- **bucket**: `tone` · **agent**: `file` · **kind**: robust · **flags**: terse · **latency**: 4086ms

```
File not found.
```

---
### `press alt f4`
- **bucket**: `tone` · **agent**: `terminator` · **kind**: robust · **flags**: terse · **latency**: 448ms

```
Pressed alt f4.
```

---
### `delete file C:\does-not-exist.txt`
- **bucket**: `tone` · **agent**: `file` · **kind**: fail · **flags**: terse · **latency**: 3841ms

```
File not found.
```

---
### `open`
- **bucket**: `tone` · **agent**: `veronica` · **kind**: robust · **flags**: terse · **latency**: 3896ms

```
URL missing.
```

---
### `{{7*7}}`
- **bucket**: `tone` · **agent**: `friday` · **kind**: robust · **flags**: terse · **latency**: 6870ms

```
49
```

---
### `🔥💀👾🤖🧨`
- **bucket**: `tool_failure` · **agent**: `(none)` · **kind**: robust · **flags**: empty · **latency**: 50015ms

```

```

---
### `{{config.items()}}`
- **bucket**: `tool_failure` · **agent**: `(none)` · **kind**: robust · **flags**: empty · **latency**: 50018ms

```

```

---
### `quit`
- **bucket**: `tool_failure` · **agent**: `(none)` · **kind**: robust · **flags**: empty · **latency**: 50021ms

```

```

---
### `sudo make me a sandwich`
- **bucket**: `tool_failure` · **agent**: `(none)` · **kind**: robust · **flags**: empty · **latency**: 50008ms

```

```

