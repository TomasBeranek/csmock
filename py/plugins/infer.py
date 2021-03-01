import csmock.common.util

INFER_RESULTS_FILTER_SCRIPT = "/usr/share/csmock/scripts/filter-infer.py"
INFER_INSTALL_SCRIPT = "/usr/share/csmock/scripts/install-infer.sh"
INFER_INSTALL_LOG = "/builddir/infer-install-log"
INFER_RESULTS = "/builddir/infer-results.txt"
INFER_ANALYZE_LOG = "/builddir/infer-analyze-log"
INFER_CAPTURE_LOG = "/builddir/infer-capture-log"
INFER_OUT_DIR = "/builddir/infer-out"
CSGREP_CMD = "csgrep --quiet %s > %s"

class PluginProps:
    def __init__(self):
        self.pass_priority = 0x60
        self.description = "Static analysis tool for Java/C/C++ code."


class Plugin:
    def __init__(self):
        self.enabled = False

    def get_props(self):
        return PluginProps()

    def enable(self):
        self.enabled = True

    def init_parser(self, parser):
        # TODO:
        #   -- add a possibility to specify an infer archive path
        parser.add_argument(
            "--infer-analyze-add-flag", action="append", default=["--bufferoverrun", "--pulse"],
            help="append the given flag (except '-o') when invoking infer analyze \
(can be used multiple times)(default '--bufferoverrun', '--pulse')")

    def handle_args(self, parser, args, props):
        if not self.enabled:
            return

        # python2.7 -- for the infer reporting module
        # ncurses-compat-libs -- libtinfo.so.5
        props.install_pkgs += ["python2.7", "ncurses-compat-libs"]

        props.copy_in_files += ["/opt/infer-linux64-v1.0.0.tar.xz"]
        props.copy_in_files += [INFER_INSTALL_SCRIPT]
        props.copy_in_files += [INFER_RESULTS_FILTER_SCRIPT]

        # install infer and wrappers for a capture phase of infer
        install_cmd = "%s > %s 2>&1" % (INFER_INSTALL_SCRIPT, INFER_INSTALL_LOG)
        def install_infer_hook(results, mock):
            return mock.exec_chroot_cmd(install_cmd)
        props.post_depinst_hooks += [install_infer_hook]

        # run an analysis phase of infer
        infer_analyze_flags = csmock.common.cflags.serialize_flags(args.infer_analyze_add_flag, separator=" ")
        run_cmd = "infer analyze %s -o %s > %s 2>&1" % (infer_analyze_flags, INFER_OUT_DIR, INFER_ANALYZE_LOG)
        props.post_build_chroot_cmds += [run_cmd]

        # the filter script tries to filter out false positives and transforms results into GCC compatible format
        filter_cmd = "python2.7 %s < %s/report.json > %s" % (INFER_RESULTS_FILTER_SCRIPT, INFER_OUT_DIR, INFER_RESULTS)
        props.post_build_chroot_cmds += [filter_cmd]

        props.copy_out_files += [INFER_INSTALL_LOG]
        props.copy_out_files += [INFER_CAPTURE_LOG]
        props.copy_out_files += [INFER_ANALYZE_LOG]
        props.copy_out_files += [INFER_RESULTS]

        def filter_hook(results):
            src = results.dbgdir_raw + INFER_RESULTS
            dst = "%s/infer-results.err" % results.dbgdir_uni
            cmd = CSGREP_CMD % (src, dst)
            return results.exec_cmd(cmd, shell=True, echo=True)

        props.post_process_hooks += [filter_hook]
