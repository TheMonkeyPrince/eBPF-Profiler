saved_results: dict[tuple[str, int], int] = {}
cached_files: dict[str, list[str]] = {}

def find_block_end(filename, start_line):
    """
    Given a C source file and a 1-based line number, find the matching closing '}' for the block
    whose opening '{' appears on that same line.

    Nested braces, string literals, character literals, and comments are handled.
    """

    if (filename, start_line) in saved_results:
        return saved_results[(filename, start_line)]


    if filename not in cached_files:
        with open(filename, 'r') as f:
            cached_files[filename] = f.readlines()

    lines = cached_files[filename]

    # Adjust for 0-based index
    start_idx = start_line - 1
    if start_idx < 0 or start_idx >= len(lines):
        raise ValueError("Invalid start line number")

    # Opening `{` must be on start_line itself; do not scan forward — later lines
    # may contain unrelated braces (e.g. `case X:` with no block vs `switch (...) {` below).
    line = lines[start_idx]
    brace_pos = line.find('{')
    if brace_pos == -1:
        raise ValueError(f"No opening brace on line {filename}:{start_line}")

    # Initialize counters
    brace_count = 0
    in_string = False
    in_char = False
    in_single_comment = False
    in_multi_comment = False

    for i in range(start_idx, len(lines)):
        line = lines[i]
        j = 0
        while j < len(line):
            c = line[j]
            
            # Handle string literals
            if in_string:
                if c == '"' and line[j-1] != '\\':
                    in_string = False
            elif in_char:
                if c == "'" and line[j-1] != '\\':
                    in_char = False
            elif in_single_comment:
                if c == '\n':
                    in_single_comment = False
            elif in_multi_comment:
                if c == '*' and j + 1 < len(line) and line[j+1] == '/':
                    in_multi_comment = False
                    j += 1
            else:
                # Check for comment starts
                if c == '/' and j + 1 < len(line):
                    if line[j+1] == '/':
                        in_single_comment = True
                        j += 1
                    elif line[j+1] == '*':
                        in_multi_comment = True
                        j += 1
                # Check for strings/chars
                elif c == '"':
                    in_string = True
                elif c == "'":
                    in_char = True
                # Count braces
                elif c == '{':
                    brace_count += 1
                elif c == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Return 1-based line number
                        saved_results[(filename, start_line)] = i + 1
                        return i + 1
            j += 1

    raise ValueError("Matching closing brace not found")

saved_block_starts: dict[tuple[str, int], int] = {}
def find_block_start(filename, end_line):
    """
    Given a C source file and the 1-based line number of a block's closing `}`,
    return the 1-based line number where that block's opening `{` begins (the
    same line `find_block_end` would use as start_line for this end_line).

    Relies on `find_block_end` for brace/string/comment handling.
    """
    if (filename, end_line) in saved_block_starts:
        return saved_block_starts[(filename, end_line)]

    # Nearest matching `{` is usually just above `end_line`; scan backward.
    for L in range(end_line, 0, -1):
        try:
            if find_block_end(filename, L) == end_line:
                saved_block_starts[(filename, end_line)] = L
                return L
        except ValueError:
            continue

    raise ValueError(f"No opening brace matches the given end line {filename}:{end_line}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python utils.py <filename> <line> <direction>")
        sys.exit(1)
    
    filename = sys.argv[1]
    line = int(sys.argv[2])
    direction = sys.argv[3]
    if direction == "down":
        print(find_block_end(filename, line))
    elif direction == "up":
        print(find_block_start(filename, line))
    else:
        print("Invalid direction. Use 'up' or 'down'.")
        sys.exit(1)
    