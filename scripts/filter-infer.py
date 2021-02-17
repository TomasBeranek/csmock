#!/usr/bin/python2.7

import json
import sys

resultsFile = open(sys.argv[2])
results = json.load(resultsFile)
resultsFile.close()

# if sys.argv[1] == "only-tranform":

for r in results:
    print("%s:%s:%s: %s: %s[Infer]: %s" % (r["file"], r["line"], r["column"], r["severity"].lower(), r["bug_type"], r["qualifier"]))
