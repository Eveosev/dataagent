"""Inspect and reconcile small UTF-8 CSV extracts, using exact text and business keys."""

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass


@dataclass
class Sample:
    columns: list
    rows: dict
    total: int
    blanks: Counter
    blank_keys: int
    duplicate_keys: int

    def profile(self):
        return {
            "rows": self.total,
            "columns": self.columns,
            "blank_by_column": {column: self.blanks[column] for column in self.columns},
            "blank_key_rows": self.blank_keys,
            "duplicate_key_rows": self.duplicate_keys,
        }


def read_sample(path, keys):
    with open(path, encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        columns = next(reader, [])
        if not columns or any(not name.strip() for name in columns) or len(set(columns)) != len(columns):
            raise ValueError("expected a header with unique, nonempty column names")
        if len(set(keys)) != len(keys) or any(key not in columns for key in keys):
            raise ValueError("each --key must name a distinct column in the input header")

        sample = Sample(columns, {}, 0, Counter(), 0, 0)
        for values in reader:
            if len(values) != len(columns):
                raise ValueError(f"record ending on line {reader.line_num} has the wrong column count")
            row = dict(zip(columns, values))
            key = tuple(row[name] for name in keys)
            sample.total += 1
            sample.blanks.update(name for name, value in row.items() if not value.strip())
            if any(not value.strip() for value in key):
                sample.blank_keys += 1
            elif key in sample.rows:
                sample.duplicate_keys += 1
            else:
                sample.rows[key] = row
        return sample


def compare(expected, actual):
    result = {"match": False, "expected": expected.profile(), "actual": actual.profile()}
    if set(expected.columns) != set(actual.columns):
        return {**result, "reason": "different_columns"}
    if any(sample.blank_keys or sample.duplicate_keys for sample in (expected, actual)):
        return {**result, "reason": "ambiguous_keys"}
    if not expected.total and not actual.total:
        return {**result, "reason": "no_evidence"}

    missing = expected.rows.keys() - actual.rows.keys()
    extra = actual.rows.keys() - expected.rows.keys()
    changed = 0
    by_column = Counter()
    for key in expected.rows.keys() & actual.rows.keys():
        left, right = expected.rows[key], actual.rows[key]
        if left != right:
            changed += 1
            by_column.update(name for name in expected.columns if left[name] != right[name])
    result.update(
        match=not (missing or extra or changed),
        missing_rows=len(missing),
        extra_rows=len(extra),
        changed_rows=changed,
        changed_by_column=dict(sorted(by_column.items())),
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile", help="inspect a small sample and a candidate key")
    profile.add_argument("sample")
    check = commands.add_parser("compare", help="compare independent snapshots by business key")
    check.add_argument("expected")
    check.add_argument("actual")
    for command in (profile, check):
        command.add_argument("--key", action="append", required=True, help="key column; repeat for a composite key")
    args = parser.parse_args()
    try:
        if args.command == "profile":
            result = read_sample(args.sample, args.key).profile()
            status = 0
        else:
            result = compare(read_sample(args.expected, args.key), read_sample(args.actual, args.key))
            status = 0 if result["match"] else 1
    except (OSError, ValueError, csv.Error) as error:
        result = {"error": str(error)}
        status = 2
    print(json.dumps(result, ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
