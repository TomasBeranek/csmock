#!/usr/bin/env python

# Copyright (C) 2014 Red Hat, Inc.
#
# This file is part of csmock.
#
# csmock is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# csmock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with csmock.  If not, see <http://www.gnu.org/licenses/>.

class PluginProps:
    def __init__(self):
        self.pass_priority = 0x10

del_flags_by_level_common = {
        0: {"-Werror", "-fdiagnostics-color", "-fdiagnostics-color=always"}}

add_flags_by_level_common = {
        1: {"-Wall", "-Wextra"},
        2: {"-Wunreachable-code", "-Wundef", "-Wcast-align",
            "-Wpointer-arith", "-Wfloat-equal", "-Wshadow",
            "-Wwrite-strings"}}

add_flags_by_level_c_only = {
        0: {"-Wno-unknown-pragmas"}}

add_flags_by_level_cxx_only = {
        2: {"-Wctor-dtor-privacy", "-Woverloaded-virtual",
            "-Wstrict-prototypes"}}

def serialize_flags(flags):
    str = ""
    for f in flags:
        if 0 < len(str):
            str += ":"
        str += f
    return str

class FlagsMatrix:
    def __init__(self):
        self.add_cflags = set()
        self.del_cflags = set()
        self.add_cxxflags = set()
        self.del_cxxflags = set()

    def __ior__(a, b):
        r = FlagsMatrix()
        r.add_cflags = a.add_cflags | b.add_cflags
        r.del_cflags = a.del_cflags | b.del_cflags
        r.add_cxxflags = a.add_cxxflags | b.add_cxxflags
        r.del_cxxflags = a.del_cxxflags | b.del_cxxflags
        return r

    def write_to_env(self, env):
        env["CSWRAP_ADD_CFLAGS"]   = serialize_flags(self.add_cflags)
        env["CSWRAP_DEL_CFLAGS="]  = serialize_flags(self.del_cflags)
        env["CSWRAP_ADD_CXXFLAGS"] = serialize_flags(self.add_cxxflags)
        env["CSWRAP_DEL_CXXFLAGS"] = serialize_flags(self.del_cxxflags)

def flags_by_warning_level(level):
    flags = FlagsMatrix()
    for l in range(0, level + 1):
        if l in del_flags_by_level_common:
            flags.del_cflags |= del_flags_by_level_common[l]
            flags.del_cxxflags |= del_flags_by_level_common[l]

        if l in add_flags_by_level_common:
            flags.add_cflags |= add_flags_by_level_common[l]
            flags.add_cxxflags |= add_flags_by_level_common[l]

        if l in add_flags_by_level_c_only:
            flags.add_cflags |= add_flags_by_level_c_only[l]

        if l in add_flags_by_level_cxx_only:
            flags.add_cxxflags |= add_flags_by_level_cxx_only[l]
    return flags

def flags_by_default():
    return flags_by_warning_level(0)

class Plugin:
    def __init__(self):
        self.enabled = False
        self.flags = flags_by_default()

    def get_props(self):
        return PluginProps()

    def enable(self):
        self.enabled = True

    def init_parser(self, parser):
        parser.add_argument("-w", "--gcc-warning-level", type=int,
                help="Adjust GCC warning level.  -w0 means default flags, \
-w1 appends -Wall and -Wextra, and -w2 enables some other useful warnings. \
(automatically enables the GCC plug-in)")

    def handle_args(self, parser, args, props):
        if args.gcc_warning_level is not None:
            self.enable()
            self.flags |= flags_by_warning_level(args.gcc_warning_level)

        if not self.enabled:
            return

        props.enable_cswrap()
        props.cswrap_filters += \
            ["csgrep --invert-match --checker COMPILER_WARNING --event error"]

        self.flags.write_to_env(props.env)