#!/usr/bin/python3

import argparse
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        "Check semantic equality of several commits using DiffKemp.")
    parser.add_argument("repo",
                        help="path to the repository to analyze")
    parser.add_argument("--diffkemp", default="diffkemp",
                        help="path to the DiffKemp executable")
    return parser.parse_args()


def run_analysis(args):
    for commit in sys.stdin:
        commit = commit.strip()


def main():
    args = parse_args()
    run_analysis(args)


if __name__ == "__main__":
    main()
