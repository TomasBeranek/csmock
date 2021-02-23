#!/usr/bin/python2.7

import json
import sys


def lowerSeverityForDEADSTORE(bug):
    if bug["bug_type"] == "DEAD_STORE":
        bug["severity"] = "WARNING"


def applyFilters(bugList, filterList):
    for bug in bugList:
        for filter in filterList:
            filter(bug)


def main():
    bugList = json.load(sys.stdin)

    if len(sys.argv) == 1 or sys.argv[1] != "--only-transform":
        filterList = [lowerSeverityForDEADSTORE]
        applyFilters(bugList, filterList)

    for bug in bugList:
        print("%s:%s:%s: %s: %s[Infer]: %s" % (bug["file"], bug["line"], bug["column"], bug["severity"].lower(), bug["bug_type"], bug["qualifier"]))

if __name__ == "__main__":
    main()
