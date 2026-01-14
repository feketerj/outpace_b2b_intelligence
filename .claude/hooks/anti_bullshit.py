#!/usr/bin/env python3
"""Anti-Bullshit Protocol - Project Hook"""

import sys

def main():
    print("""
PROOF REQUIRED: Before saying "done", "fixed", "verified", or "works", output this:

```proof
ACTION: [what user task was tested]
EXECUTED: [exact command/click/request]
OUTPUT: [actual response or screenshot path]
RESULT: [pass/fail + evidence]
```

No proof block = not done.
""")
    sys.exit(0)

if __name__ == "__main__":
    main()
