"""Move trailing quote inserted at line end to before punctuation."""
import sys, re

path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

lines = src.split('\n')
out = []
for ln_no, line in enumerate(lines, 1):
    # Match line ending in "punctuation+quote", e.g., ,"  ]" )" :" }" 
    # Move the quote BEFORE the punctuation cluster
    m = re.search(r'([,\)\]:\}]+)"\s*$', line)
    if m and ln_no in {39,41,308,359,426,429,485,490,491,516,517,522,553,621,679,680,681,734,735,739,742,748,782}:
        # rewrite
        # punctuation cluster
        punct = m.group(1)
        new_line = line[:m.start()] + '"' + punct
        # preserve trailing whitespace
        ws_match = re.search(r'\s*$', line)
        new_line += ws_match.group(0)
        print(f"line {ln_no}: moved quote ({line.rstrip()[-3:]!r} -> {new_line.rstrip()[-3:]!r})")
        out.append(new_line)
    else:
        out.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print("Done")
