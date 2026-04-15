saved_results: dict[tuple[str, int], int] = {}
cached_files: dict[str, list[str]] = {}

def find_block_end(filename, start_line):
    """
    Given a C source file and a starting line number, find the line number of the matching closing brace '}'.
    This function accounts for nested braces, string literals, character literals, and comments.
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

    # Search for the opening brace in the given line
    line = lines[start_idx]
    brace_pos = line.find('{')
    while brace_pos == -1 and start_idx + 1 < len(lines): # look for the opening brace in subsequent lines if not found in the current line
        start_idx += 1
        line = lines[start_idx]
        brace_pos = line.find('{')
    if brace_pos == -1:
        raise ValueError("No opening brace found starting from the given line")

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
