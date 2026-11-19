#Created by D/Cst. Taylor Meyer, Halton Regional Police Service
from __future__ import print_function

#!/usr/bin/env python
import io
import json
import os
import re


def load_options(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compile_filters(options):
    line_rules = options.get("line_rules", {})

    path_re = None
    if line_rules.get("exclude_path_like", {}).get("enabled"):
        path_re = re.compile(line_rules["exclude_path_like"]["regex"])

    filename_re = None
    if line_rules.get("exclude_filename_like", {}).get("enabled"):
        filename_re = re.compile(line_rules["exclude_filename_like"]["regex"])

    repeated_re = None
    if line_rules.get("exclude_repeated_char_sequences", {}).get("enabled"):
        repeated_re = re.compile(line_rules["exclude_repeated_char_sequences"]["regex"])

    timestamp_re = None
    if line_rules.get("exclude_timestamp_or_datestamp", {}).get("enabled"):
        regexes = line_rules["exclude_timestamp_or_datestamp"].get("regexes", [])
        if regexes:
            combined = "|".join("(?:{})".format(r) for r in regexes)
            timestamp_re = re.compile(combined, re.IGNORECASE)

    contains_list = []
    if line_rules.get("exclude_contains", {}).get("enabled"):
        contains_list = line_rules["exclude_contains"].get("substrings", [])

    min_len = line_rules.get("length", {}).get("min")
    max_len = line_rules.get("length", {}).get("max")

    ascii_only = bool(line_rules.get("ascii_only", False))
    trim = bool(line_rules.get("trim_whitespace", True))
    drop_empty = bool(line_rules.get("drop_empty_lines", True))
    dedupe_cfg = line_rules.get("dedupe", {})
    dedupe_enabled = bool(dedupe_cfg.get("enabled", False))
    dedupe_case_sensitive = bool(dedupe_cfg.get("case_sensitive", True))

    return {
        "path_re": path_re,
        "filename_re": filename_re,
        "repeated_re": repeated_re,
        "timestamp_re": timestamp_re,
        "contains_list": contains_list,
        "min_len": min_len,
        "max_len": max_len,
        "ascii_only": ascii_only,
        "trim": trim,
        "drop_empty": drop_empty,
        "dedupe_enabled": dedupe_enabled,
        "dedupe_case_sensitive": dedupe_case_sensitive,
    }


def keep_line(line, f):
    s = line.strip() if f["trim"] else line

    if f["drop_empty"] and not s:
        return False

    if f["min_len"] is not None and len(s) < int(f["min_len"]):
        return False
    if f["max_len"] is not None and len(s) > int(f["max_len"]):
        return False

    if f["ascii_only"] and any(ord(ch) > 127 for ch in s):
        return False

    if f["path_re"] and f["path_re"].search(s):
        return False
    if f["filename_re"] and f["filename_re"].search(s):
        return False
    if f["repeated_re"] and f["repeated_re"].search(s):
        return False
    if f["timestamp_re"] and f["timestamp_re"].search(s):
        return False

    s_lower = s.lower()
    for token in f["contains_list"]:
        if token.lower() in s_lower:
            return False

    return True


def clean_one_file(input_path, output_path, filters):
    with io.open(input_path, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.read().splitlines()
    kept = [line.strip() if filters["trim"] else line for line in lines if keep_line(line, filters)]
    duplicates_removed = 0
    if filters["dedupe_enabled"]:
        deduped = []
        seen = set()
        for line in kept:
            key = line if filters["dedupe_case_sensitive"] else line.lower()
            if key in seen:
                duplicates_removed += 1
                continue
            seen.add(key)
            deduped.append(line)
        kept = deduped

    with io.open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(kept) + ("\n" if kept else ""))
    removed = len(lines) - len(kept)
    print("Input: {}".format(os.path.basename(input_path)))
    print("Output: {}".format(os.path.basename(output_path)))
    print("Input lines: {}".format(len(lines)))
    print("Output lines: {}".format(len(kept)))
    print("Removed lines: {}".format(removed))
    if filters["dedupe_enabled"]:
        print("Duplicates removed: {}".format(duplicates_removed))
    print("-" * 40)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "password_cleanup_options.json")
    if not os.path.exists(config_path):
        raise SystemExit("Config file not found: {}".format(config_path))

    options = load_options(config_path)
    filters = compile_filters(options)

    txt_files = sorted(
        os.path.join(script_dir, name)
        for name in os.listdir(script_dir)
        if (
            name.lower().endswith(".txt")
            and not name.lower().endswith(".cleaned.txt")
            and not os.path.splitext(name)[0].lower().startswith("readme")
        )
    )
    if not txt_files:
        raise SystemExit("No .txt files found in: {}".format(script_dir))

    print("Config: {}".format(config_path))
    print("Working folder: {}".format(script_dir))
    print("Files found: {}".format(len(txt_files)))
    print("=" * 40)

    for input_path in txt_files:
        stem, _ = os.path.splitext(input_path)
        output_path = stem + ".cleaned.txt"
        clean_one_file(input_path, output_path, filters)


if __name__ == "__main__":
    main()
