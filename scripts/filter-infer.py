#!/usr/bin/env python

import json
import sys
import re


def inferboFilter(bug):
    if bug["bug_type"] == ["BUFFER_OVERRUN_U5"]:
        return True

    bufferOverRunTypes = [
        "BUFFER_OVERRUN_L2",
        "BUFFER_OVERRUN_L3",
        "BUFFER_OVERRUN_L4",
        "BUFFER_OVERRUN_L5",
        "BUFFER_OVERRUN_S2"]

    if bug["bug_type"] in bufferOverRunTypes:
        size = re.findall(r"Size: \[[^\[\]\n]*\]", bug["qualifier"])[0]
        if size and (("+oo" in size) or ("-oo" in size)):
            return True


def lowerSeverityForDEADSTORE(bug):
    if bug["bug_type"] == "DEAD_STORE":
        bug["severity"] = "WARNING"


def applyFilters(bugList, filterList):
    modifiedBugList = []

    while bugList:
        bug = bugList.pop(0)
        bugIsFalseAlarm = False
        for filter in filterList:
            try:
                # if a filter returns true, then this bug is considered a
                # false alarm will not be included in the final report
                # NOTE: a bug marked as a false alarm may not actually be
                #       a false alarm
                if filter(bug):
                    bugIsFalseAlarm = True
                    break
            except:
                # if a filter fails on a bug, then the filter behaves as if
                # the bug was real
                bugIsFalseAlarm = False
        if not bugIsFalseAlarm:
            modifiedBugList.append(bug)

    return modifiedBugList


def main():
    bugList = json.load(sys.stdin)

    if len(sys.argv) == 1 or sys.argv[1] != "--only-transform":
        filterList = [
            lowerSeverityForDEADSTORE,
            inferboFilter]
        bugList = applyFilters(bugList, filterList)

    for bug in bugList:
        print("%s:%s:%s: %s: %s[Infer]: %s" % (bug["file"], bug["line"], bug["column"], bug["severity"].lower(), bug["bug_type"], bug["qualifier"]))

if __name__ == "__main__":
    main()
