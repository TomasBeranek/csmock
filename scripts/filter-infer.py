#!/usr/bin/env python

import json
import sys
import re
import os
import subprocess
from pathlib import Path


def nullDereferenceFilter(bug):
    for bugTrace in bug["bug_trace"]:
        if re.match("Skipping .*\(\):", bugTrace["description"]):
            return True


def inferboFilter(bug):
    if bug["bug_type"] == ["BUFFER_OVERRUN_U5"] or bug["bug_type"] == ["INTEGER_OVERFLOW_U5"]:
        return True

    bufferOverRunTypes = [
        "BUFFER_OVERRUN_L2",
        "BUFFER_OVERRUN_L3",
        "BUFFER_OVERRUN_L4",
        "BUFFER_OVERRUN_L5",
        "BUFFER_OVERRUN_S2",
        "INFERBO_ALLOC_MAY_BE_NEGATIVE",
        "INFERBO_ALLOC_MAY_BE_BIG"]

    integerOverFlowTypes = [
        "INTEGER_OVERFLOW_L1",
        "INTEGER_OVERFLOW_L2",
        "INTEGER_OVERFLOW_L5"]

    if bug["bug_type"] in bufferOverRunTypes or bug["bug_type"] in integerOverFlowTypes:
        if ("+oo" in bug["qualifier"]) or ("-oo" in bug["qualifier"]):
            return True


def lowerSeverityForDEADSTORE(bug):
    if bug["bug_type"] == "DEAD_STORE":
        bug["severity"] = "WARNING"


def memoryLeaksFilter(bug):
    if bug["bug_type"] != "MEMORY_LEAK":
        return

    AST_FILES_DIR = "/builddir/infer-ast"
    AST_LOG_FILE = "/builddir/infer-ast-log"

    # create the directory if it doesn't exist
    Path(AST_FILES_DIR).mkdir(parents=True, exist_ok=True)
    # TODO: do not generate an ast again if it already exists

    with open(AST_LOG_FILE, 'r') as file:
        compileInfo = file.read().split("\n\n")
        for s in compileInfo:
            if not s:
                break

            s = s.split("\n")

            # delete first char from each file name, which is only Infer's info
            # 1st item in list is a compile command
            # 2nd item in list is a PWD
            # other items in list are freshly captured files
            freshlyCapturedFiles = [f[1:] for f in s[2:]]

            # generate ast only for files in which are memory leaks
            if bug["file"] not in freshlyCapturedFiles:
                continue

            # split compile command into list of arguments
            compileCommand = s[0].split()

            # obtain PWD of compile command
            PWD = s[1]
            cdPWD = ["cd", PWD, "&&"]

            # overwrite original compiler
            compileCommand[0] = "clang"

            # insert args for ast generating (-cc1 must be the first arg!)
            compileCommand.insert(1, "-cc1")
            compileCommand.insert(2, "-ast-dump")

            # go to a directory, where compile command was called, necessary since
            # file name is relative
            compileCommand.insert(3, "-working-directory="+PWD)

            # we cannot use args check and shell
            result = subprocess.run(compileCommand, capture_output=True, text=True, encoding="utf-8", cwd=PWD)

            # we cannot use return code to determine success of ast generating, since
            # ast can be generated even if compile command ends with errorneous return code,
            # but we can check if there is an ast node FunctionDecl which must be in every file
            if "FunctionDecl" not in result.stdout:
                # simply adding args to compile command failed, try a different aproach
                if "-c" in compileCommand:
                    # delete all occurences of '-c' (only compile arg) which doesnt work with -cc1 and -ast-dump
                    compileCommand = [arg for arg in compileCommand if arg != "-c"]
                    result = subprocess.run(compileCommand, capture_output=True, text=True, encoding="utf-8", cwd=PWD)
                if "FunctionDecl" not in result.stdout:
                    # deleting '-c' didnt help or wasnt present in the command, try the last aproach
                    # keep only -Dmacro args and ignore everything else
                    compileCommand = [arg for arg in compileCommand if arg[0:2] == "-D" or arg[0:2] == "-I"]
                    compileCommand = ["clang", "-cc1", "-ast-dump"] + compileCommand

                    # TODO: freshlyCapturedFiles are only names of files, but in compile command
                    #       needs to be relative or absolute path -> compare freshlyCapturedFiles with compile args
                    #       and use these arg instead of freshlyCapturedFiles
                    compileCommand = compileCommand + freshlyCapturedFiles
                    result = subprocess.run(compileCommand, capture_output=True, text=True, encoding="utf-8", cwd=PWD)

                    if "FunctionDecl" not in result.stdout:
                        # it wasnt possible to obtain ast from this compile command
                        # create an empty file for every source file in ast directory
                        # TODO: a path may be needed to create
                        for sourceFile in freshlyCapturedFiles:
                            with open("%s/%s" % (AST_FILES_DIR, sourceFile), "w") as astFile:
                                astFile.write("")
                            print("WARNING: INFER: filter-infer.py: failed generate AST for file " + sourceFile, file=sys.stderr)
                        continue

            # copy generated ast for every source file for easier access
            # TODO: a path may be needed to create
            for sourceFile in freshlyCapturedFiles:
                with open("%s/%s" % (AST_FILES_DIR, sourceFile), "w") as astFile:
                    # stdout is captured as bytes and needs to be converted
                    astFile.write(result.stdout)


def applyFilters(bugList, filterList):
    modifiedBugList = []

    while bugList:
        bug = bugList.pop(0)
        bugIsFalseAlarm = False
        for filter in filterList:
            try:
                # if a filter returns true, then this bug is considered a
                # false alarm and will not be included in the final report
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
            inferboFilter,
            memoryLeaksFilter,
            nullDereferenceFilter]
        bugList = applyFilters(bugList, filterList)

    firstBug = True

    for bug in bugList:
        if not firstBug:
            print()
        print("Error: INFER_WARNING:")
        for bugTrace in bug["bug_trace"]:
            print("%s:%s:%s: note: %s" % (bugTrace["filename"], bugTrace["line_number"], bugTrace["column_number"], bugTrace["description"]))
        print("%s:%s:%s: %s[%s]: %s" % (bug["file"], bug["line"], bug["column"], bug["severity"].lower(), bug["bug_type"], bug["qualifier"]))
        firstBug=False

if __name__ == "__main__":
    main()
