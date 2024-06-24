#!/usr/bin/python3

import csv
import argparse
import os
import re
import sys

import git


def parse_args():
    parser = argparse.ArgumentParser(
        "Check semantic equality of several commits using DiffKemp.")
    parser.add_argument("repo",
                        help="path to the repository to analyze")
    parser.add_argument("--diffkemp", default="diffkemp",
                        help="path to the DiffKemp executable")
    return parser.parse_args()


def locate_functions(old_commit, new_commit):
    all_matched = True
    functions = set()
    for diff in old_commit.diff(new_commit, create_patch=True):
        diff_str = diff.diff.decode()
        matched = False
        # Make use of git's detection of which function was changed. The diff
        # hunk is of the format:
        #   @@ <information about location> @@ <function> name
        for match in re.finditer(r"^@@.*@@ (?P<function>.*)$", diff_str, re.M):
            if f_match := re.search(r"(^|\s)(?P<name>\S*)\(", match.group("function")):
                matched = True
                functions.add(f_match.group("name"))
        if not matched:
            # Skip commits where we can't identify the changed function in
            # all the diff hunks
            all_matched = False

    return all_matched, list(functions)


def analyze_commit(args, writer, commit):
    repo = git.Repo(args.repo)
    new_commit = repo.commit(commit)
    old_commit = repo.commit(f"{commit}^")
    snapshot_path = os.path.join(os.getcwd(), "snapshot", commit)
    old_snapshot = os.path.join(snapshot_path, "old")
    new_snapshot = os.path.join(snapshot_path, "new")

    all_matched, functions = locate_functions(old_commit, new_commit)
    if not all_matched:
        writer.writerow([commit, ", ".join(functions), len(functions), "-", "UNK"])
        return


def run_analysis(args):
    writer = csv.writer(sys.stdout)
    writer.writerow(["commit", "functions", "no_functions", "no_eq_functions", "verdict"])
    for commit in sys.stdin:
        commit = commit.strip()
        analyze_commit(args, writer, commit)


def main():
    args = parse_args()
    run_analysis(args)


if __name__ == "__main__":
    main()
