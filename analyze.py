#!/usr/bin/python3

import csv
import argparse
import contextlib
import os
import re
import shutil
import sys
import subprocess
import tempfile

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


def create_snapshot(repo, commit, diffkemp, functions, output_dir):
    repo.git.clean("-fdx")
    repo.git.restore(".")
    repo.git.checkout(commit.hexsha)

    kargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.check_call(["make", "allmodconfig"], **kargs)
    subprocess.check_call(["scripts/config", "--disable", "CONFIG_RETPOLINE"], **kargs)
    subprocess.check_call(
        ["make", "prepare", "EXTRA_CFLAGS=-w -fno-pie -no-pie", "CFLAGS=-w", "HOSTLDFLAGS=-no-pie"],
        **kargs
    )
    subprocess.check_call(
        ["make", "modules_prepare", "EXTRA_CFLAGS=-w -fno-pie -no-pie", "CFLAGS=-w", "HOSTLDFLAGS=-no-pie"],
        **kargs
    )

    with tempfile.NamedTemporaryFile("w+t", delete_on_close=False) as fp:
        fp.write("\n".join(functions) + "\n")
        fp.close()
        subprocess.check_call(
            [diffkemp, "build-kernel", repo.working_tree_dir, output_dir, fp.name],
            **kargs
        )


def analyze_commit(args, writer, commit):
    repo = git.Repo(args.repo)
    new_commit = repo.commit(commit)
    old_commit = repo.commit(f"{commit}^")

    snapshot_path = os.path.join(os.getcwd(), "snapshot", commit)
    os.makedirs(snapshot_path, exist_ok=True)

    all_results_path = os.path.join(os.getcwd(), "result")
    os.makedirs(all_results_path, exist_ok=True)
    result_path = os.path.join(all_results_path, commit)
    if os.path.exists(result_path):
        shutil.rmtree(result_path)

    old_snapshot = os.path.join(snapshot_path, "old")
    new_snapshot = os.path.join(snapshot_path, "new")

    all_matched, functions = locate_functions(old_commit, new_commit)
    if not functions:
        writer.writerow([commit, "-", "-", "-", "NO-FUNCTIONS", "-"])
        return

    with contextlib.chdir(args.repo):
        create_snapshot(repo, old_commit, args.diffkemp, functions, old_snapshot)
        create_snapshot(repo, new_commit, args.diffkemp, functions, new_snapshot)

    compare_command = [
        args.diffkemp,
        "compare",
        old_snapshot,
        new_snapshot,
        "--report-stat",
        "-o",
        result_path
    ]
    res = subprocess.run(compare_command, capture_output=True)
    output = res.stdout.decode()
    if match := re.search(r"^Equal:\s*(?P<number>\d+)", output, re.M):
        eq = int(match.group("number"))
        verdict = "equal" if eq == len(functions) else "not equal"
        writer.writerow([
            commit,
            ", ".join(functions),
            len(functions),
            eq,
            verdict,
            all_matched
        ])
    else:
        raise RuntimeError("Unable to detect the number of equal functions")


def run_analysis(args):
    writer = csv.writer(sys.stdout)
    writer.writerow(["commit", "functions", "no_functions", "no_eq_functions", "verdict", "confident"])
    for commit in sys.stdin:
        commit = commit.strip()
        try:
            analyze_commit(args, writer, commit)
        except subprocess.CalledProcessError:
            writer.writerow([commit, "-", "-", "-", "FAIL", "-"])


def main():
    args = parse_args()
    run_analysis(args)


if __name__ == "__main__":
    main()
