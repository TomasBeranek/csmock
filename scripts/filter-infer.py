#!/usr/bin/env python

import json
import sys
import re
import os
import subprocess
from pathlib import Path


def uninitFilter(bug):
    if bug["bug_type"] == "UNINITIALIZED_VALUE":
        if re.match("The value read from .*\[_\] was never initialized.", bug["qualifier"]):
            return True


def biabductionFilter(bug):
    if bug["bug_type"] == "NULL_DEREFERENCE" or bug["bug_type"] == "RESOURCE_LEAK":
        for bugTrace in bug["bug_trace"]:
            if re.match("Skipping .*\(\):", bugTrace["description"]):
                return True
            if re.match("Switch condition is false. Skipping switch case", bugTrace["description"]):
                return True


def inferboFilter(bug):
    if bug["bug_type"] == "BUFFER_OVERRUN_U5" or bug["bug_type"] == "INTEGER_OVERFLOW_U5":
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
        "INTEGER_OVERFLOW_L2",
        "INTEGER_OVERFLOW_L5",
        "INTEGER_OVERFLOW_U5"]

    if bug["bug_type"] in bufferOverRunTypes or bug["bug_type"] in integerOverFlowTypes:
        if ("+oo" in bug["qualifier"]) or ("-oo" in bug["qualifier"]):
            return True


def lowerSeverityForDEADSTORE(bug):
    if bug["bug_type"] == "DEAD_STORE":
        bug["severity"] = "WARNING"


def getFunctionAST(file, functionName):
    with open(file) as f:
        lines = f.read().splitlines()

    startfunctionIndex = -1
    endfunctionIndex = len(lines) - 1 # implicit end
    for lineIndex in range(len(lines)):
        if startfunctionIndex == -1 and re.match(r'\|\-FunctionDecl .* ' + functionName + r' ', lines[lineIndex]):
            startfunctionIndex = lineIndex
            continue # skip this to line, so it wont match with end
        if startfunctionIndex != -1 and lines[lineIndex][0:2] == "|-":
            endfunctionIndex = lineIndex - 1 # current line is FunctionDecl of next function
            break
    return lines[startfunctionIndex:endfunctionIndex+1]


def getLineDepth(line):
    depth = 0
    for c in line:
        if c in "| `-":
            depth += 1
        else:
            break
    # -2 is because there is always a leading '|' and before
    # node a '-' and we want a function declaration to have 0 depth
    return depth - 2


def getCommandAST(functionAST, lineNumber):
    lineRe = "<line:" + str(lineNumber)
    commandAST = []
    currDepth = -1

    for line in functionAST:
        # detection of the allocation command (it might be encapsulated e.g. in IfStmt)
        if (not commandAST) and (lineRe in line):
            currDepth = getLineDepth(line)
            commandAST.append(line)
            continue
        if currDepth == -1:
            continue
        elif getLineDepth(line) > currDepth:
            commandAST.append(line)
        else:
            break

    return commandAST


def getBinaryOperatorAST(commandAST, col):
        binaryOperatorAST = []
        currDepth = -1

        for line in commandAST:
            if (not binaryOperatorAST) and ("BinaryOperator" in line):
                currDepth = getLineDepth(line)
                binaryOperatorAST.append(line)
                continue
            if currDepth == -1:
                continue
            elif getLineDepth(line) > currDepth:
                binaryOperatorAST.append(line)
            else:
                # we have a loaded BinaryOperator node and we have to check if there is a rvalue
                # that starts on a col (if we have the right BinaryOperator node)
                for line in binaryOperatorAST:
                    if ("<col:"+str(col)) in line:
                        # we have found the right one
                        return binaryOperatorAST
                # this binary operation was not the right one
                binaryOperatorAST = []

        # if BinaryOperator ended with commandAST, its still possible, that we found
        # the right one
        for line in binaryOperatorAST:
            if ("<col:"+str(col)) in line:
                # we have found the right one
                return binaryOperatorAST

        # if the right node wasnt found return None -> this will throw an exception
        # in a caller and this bug will be considered as a false positive


def getVariableName(functionAST, callLine, callCol):
    commandAST = getCommandAST(functionAST, callLine)
    binaryOperatorAST = getBinaryOperatorAST(commandAST, callCol)

    if binaryOperatorAST:
        for line in binaryOperatorAST:
            if "lvalue" in line:
                # extract variable name from AST line
                # example:
                # |       | |-DeclRefExpr 0x1c75b68 <col:4> 'char *' lvalue Var 0x1c6ce08 'p' 'char *'
                return line.split("lvalue")[1].split("'")[1]

    # if an allocated memory was assigned while declaring the variable, in AST it isnt
    # called a BinaryOperator, so we have to check a VarDecl node instead
    for line in commandAST:
        if "-VarDecl" in line:
            # extract variable name from AST line
            # example:
            # |   | `-VarDecl 0x149b410 <col:3, col:21> col:8 used c 'char *' cinit
            return line.split("used")[1].split(" ")[1]


def checkMemoryLeakAgainstAST(bug, fileAST):
    functionName = bug["procedure"]
    functionAST = getFunctionAST(fileAST, functionName)
    # get the name of the variable in which allocated memory is stored, the function
    # needs AST and (line, column) in which starts a trace (where an allocation is done by
    # calling malloc, calloc, ... or any other function which returns an allocated memory)
    variableName = getVariableName(functionAST, bug["bug_trace"][1]["line_number"], bug["bug_trace"][1]["column_number"])

    # check if the varibale is used as a lvalue after its last use
    lastUseLine = bug["bug_trace"][-1]["line_number"]
    afterLastUse = False
    lineIndex = 0
    lvalueFound = False

    while lineIndex < len(functionAST):
        if ("<line:"+str(lastUseLine)) in functionAST[lineIndex]:
            afterLastUse = True
            # skip the rest of the command AST on the lastUseLine
            lastUseCommandStartDepth = getLineDepth(functionAST[lineIndex])
            lineIndex += 1

            while getLineDepth(functionAST[lineIndex]) > lastUseCommandStartDepth:
                lineIndex += 1
            continue

        if afterLastUse and re.search('lvalue .* \'' + variableName + '\' ', functionAST[lineIndex]):
            lvalueFound = True
        lineIndex += 1

    if lvalueFound:
        return False
    else:
        return True


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
                    # keep only -Dmacro and -Ilib args and ignore everything else
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

    # checks the bug against the generated AST
    return checkMemoryLeakAgainstAST(bug, "%s/%s" % (AST_FILES_DIR, sourceFile))


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

    if "--only-transform" not in sys.argv:
        filterList = []

        if "--no-biadbuction" not in sys.argv:
            filterList += [biabductionFilter]

        if "--no-inferbo" not in sys.argv:
            filterList += [inferboFilter]

        if "--no-uninit" not in sys.argv:
            filterList += [uninitFilter]

        if "--no-memory-leak" not in sys.argv:
            filterList += [memoryLeaksFilter]

        if "--no-dead-store" not in sys.argv:
            filterList += [lowerSeverityForDEADSTORE]

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
