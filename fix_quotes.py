"""Fix missing closing double-quotes on lines (mojibake corruption)."""
import sys, re, io

path = sys.argv[1]
with open(path, 'r', encoding='utf-8-sig') as f:
    src = f.read()

lines = src.split('\n')
in_triple = False
triple_marker = None
out = []
for ln_no, line in enumerate(lines, 1):
    # naive triple-quote tracking
    stripped = line
    # Count triple quote occurrences
    tcount_d = stripped.count('"""')
    tcount_s = stripped.count("'''")
    if in_triple:
        # find closing
        if triple_marker == '"""' and '"""' in stripped:
            in_triple = False
            triple_marker = None
        elif triple_marker == "'''" and "'''" in stripped:
            in_triple = False
            triple_marker = None
        out.append(line)
        continue
    # not in triple
    # Strip triple-quoted parts on this line (handle once-opened-and-closed on same line)
    # If odd number of triple quotes, set in_triple
    if tcount_d % 2 == 1:
        in_triple = True
        triple_marker = '"""'
        out.append(line)
        continue
    if tcount_s % 2 == 1:
        in_triple = True
        triple_marker = "'''"
        out.append(line)
        continue
    # Remove triple-quoted contents within the line
    work = re.sub(r'"""[^"]*"""', '', stripped)
    work = re.sub(r"'''[^']*'''", '', work)
    # Remove comments (# only outside strings — naive)
    # Find # outside quotes
    # Count remaining single double quotes, skipping escaped \"
    i = 0
    in_s = False
    quote = None
    code = []
    while i < len(work):
        ch = work[i]
        if in_s:
            if ch == '\\' and i + 1 < len(work):
                i += 2; continue
            if ch == quote:
                in_s = False; quote = None
            i += 1; continue
        if ch == '#':
            break
        if ch == '"' or ch == "'":
            in_s = True
            quote = ch
        i += 1
    if in_s and quote == '"':
        # Unclosed double quote on this line. Insert closing quote BEFORE trailing punctuation
        # such as , ) ] : } so dict/list values keep their structure.
        m = re.search(r'([,\)\]:\}\s]+)$', line)
        if m:
            insert_at = m.start()
            new_line = line[:insert_at] + '"' + line[insert_at:]
        else:
            new_line = line.rstrip() + '"'
        print(f"line {ln_no}: added closing quote")
        out.append(new_line)
    elif in_s and quote == "'":
        m = re.search(r'([,\)\]:\}\s]+)$', line)
        if m:
            insert_at = m.start()
            new_line = line[:insert_at] + "'" + line[insert_at:]
        else:
            new_line = line.rstrip() + "'"
        print(f"line {ln_no}: added closing single quote")
        out.append(new_line)
    else:
        out.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))

print("Done")
