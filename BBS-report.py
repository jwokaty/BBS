#!/usr/bin/env python3
##############################################################################
###
### This file is part of the BBS software (Bioconductor Build System).
###
### Author: Hervé Pagès <hpages.on.github@gmail.com>
### Last modification: June 16, 2021
###

import sys
import os
import time
import shutil
import re
import fnmatch
import string
import html
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Tuple

import bbs.fileutils
import bbs.parse
import bbs.jobs
import bbs.rdir
import BBSutils
import BBSvars
import BBSreportutils


BBS_HOME = BBSvars.BBS_home
ENV = Environment(loader=FileSystemLoader(os.path.join(BBS_HOME, "templates")))
MEAT_INDEX = bbs.parse.get_meat_packages(BBSutils.meat_index_file,
                                         as_dict=True)

def get_pkg_overall_status(pkg, statuses, skipped_pkgs):
    if pkg in skipped_pkgs or "ERROR" in statuses:
        status = "ERROR"
    elif "TIMEOUT" in statuses:
        status = "TIMEOUT"
    elif "WARNINGS" in statuses:
        status = "WARNINGS"
    elif "NA" in statuses:
        status = "NA"
    elif "OK" in statuses:
        status = "OK"
    else:
        status = "unknown"
    return status

ENV.globals["get_pkg_overall_status"] = get_pkg_overall_status

class BBSReportConfiguration:

    def __init__(self, simple_layout: bool, no_raw_results: bool) -> None:

        self.compact = simple_layout
        self.no_raw_results = no_raw_results
        self.css_file = BBSutils.getenv('BBS_REPORT_CSS', is_required=False)
        self.base_css_file = os.path.join(BBSutils.getenv('BBS_HOME'),
                                          "templates", "bbs.css")
        self.bgimg_file = BBSutils.getenv('BBS_REPORT_BGIMG', is_required=False)
        self.js_file = BBSutils.getenv('BBS_REPORT_JS', is_required=False)
        self.path = BBSutils.getenv('BBS_REPORT_PATH')
        self.r_environ_user = BBSutils.getenv('R_ENVIRON_USER',
                                              is_required=False)

class BBSPackageReference:

    def __init__(self, name: str, maintainer: str, version: str,
                 package_status: str, git_url: str, git_branch: str,
                 git_last_commit: str, git_last_commit_date: str,
                 stages: list) -> None:

        self.name = name
        self.maintainer = maintainer
        self.version = version
        self.package_status = package_status
        self.git_url = git_url
        self.git_branch = git_branch
        self.git_last_commit = git_last_commit
        self.git_last_commit_date = git_last_commit_date

        print(f"BBS> Getting info for {self.name} ...")
        sys.stdout.flush()

        self.results = {}
        buildtype = BBSvars.buildtype
        for node in BBSreportutils.NODES:
            if self.name not in BBSreportutils.supported_pkgs(node):
                continue

            self.results[node.node_id] = {}
            for stage in stages:
                stage = stage.lower()
                if (buildtype != "bioc-longtests" and stage == "install") or \
                    (buildtype not in ["workflows", "books"] and stage == "checksrc") or \
                    (BBSreportutils.is_doing_buildbin(node) and stage == "build bin") or \
                    stage == "buildsrc":
                    self.results[node.node_id][stage.removesuffix('src')] = \
                        BBSreportutils.get_pkg_status(name, node.node_id, stage)

        print(f"{self.name} = name\n"
              f"{self.maintainer} = maintainer\n"
              f"{self.version} = version\n"
              f"{self.package_status} = package_status\n"
              f"{self.git_url} = git_url\n"
              f"{self.git_branch} = git_branch\n"
              f"{self.git_last_commit} = git_last_commit\n"
              f"{self.git_last_commit_date} = git_last_commit_date\n")
        print("OK")

class BBSReportContent:

    @staticmethod
    def _get_stage_labels():
        stage_labels = []
        buildtype = BBSvars.buildtype
        for stage in BBSreportutils.stages_to_display(buildtype):
            stage_labels.append(BBSreportutils.stage_label(stage))
        return stage_labels

    @staticmethod
    def _get_TIMEOUT_message(stages: list) -> str:
        """Generate TIMEOUT explanation message"""

        labels = []
        times = []

        if "INSTALL" in stages:
            labels.append("INSTALL")
            times.append(int(BBSvars.INSTALL_timeout / 60.0))
        if "BUILD" in stages:
            labels.append("BUILD")
            times.append(int(BBSvars.BUILD_timeout / 60.0))
        if "CHECK" in stages:
            labels.append("CHECK")
            times.append(int(BBSvars.CHECK_timeout / 60.0))
        if "BUILD BIN" in stages:
            labels.append("BUILD BIN")
            times.append(int(BBSvars.BUILDBIN_timeout / 60.0))
        if len(labels) == 1:
            msg = labels[0]
        else:
            msg = f"{', '.join(labels[:-1])} or {labels[-1]}"
        msg += " of package took more than "
        same_times = times[:-1] == times[1:]
        if same_times:
            msg += str(times[0])
        else:
            times = [str(t) for t in times]
            msg += f"{', '.join(times[:-1])} or {times[-1]}"
        msg += " minutes"
        if not same_times:
            msg += ", respectively"
        return msg

    @staticmethod
    def _get_ERROR_message(stages) -> str:
        """Generate ERROR explanation message"""

        labels = stages.copy()
        if len(labels) == 1 and labels[0] == "CHECK":
            msg = "CHECK of package produced errors"
        else:
            CHECK_in_labels = "CHECK" in labels
            if CHECK_in_labels:
                labels.remove("CHECK")
            if len(labels) == 1:
                msg = labels[0]
            else:
                msg = f"{', '.join(labels[:-1])} or {labels[-1]}"
            msg += " of package failed"
            if CHECK_in_labels:
                msg += ", or CHECK produced errors"
        return "Bad DESCRIPTION file, or " + msg

    @staticmethod
    def _get_WARNINGS_message() -> str:
        return "CHECK of package produced warnings"

    @staticmethod
    def _get_OK_message(stages: list) -> str:
        """Generate OK explanation message"""

        if len(stages) == 1:
            msg = stages[0]
        else:
            msg = f"{', '.join(stages[:-1])} or {stages[-1]}"
        return msg + " of package went OK"

    @staticmethod
    def _get_NA_message(stages: list) -> str:
        """Generate NA explanation message"""

        if len(stages) == 1:
            msg = stages[0]
        else:
            msg = f"{', '.join(stages[:-1])} or {stages[-1]}"
        msg += " result is not available because" + \
                " of an anomaly in the Build System"
        return msg

    @staticmethod
    def _get_skipped_message(stages: list) -> str:
        """Generate skipped explanation message"""

        labels = []
        if "CHECK" in stages:
            labels.append("CHECK")
        if "BUILD BIN" in stages:
            labels.append("BUILD BIN")
        if len(labels) == 1:
            msg = labels[0]
        else:
            msg = f"{', '.join(labels[:-1])} or {labels[-1]}"
        msg += " of package was skipped because the BUILD step failed"
        return msg

    def get_status_messages(self) -> Dict[str, str]:
        """Get status messages"""

        buildtype = BBSvars.buildtype
        stages = self._get_stage_labels()

        msg = {}
        msg["timeout"] = self._get_TIMEOUT_message(stages)
        msg["error"] = self._get_ERROR_message(stages)

        if 'CHECK' in stages:
            msg["check"] = self._get_WARNINGS_message()

        msg["ok"] = self._get_OK_message(stages)
        msg["na"] = self._get_NA_message(stages)

        if 'CHECK' in stages or 'BUILD BIN' in stages:
            msg["skipped"] = self._get_skipped_message(stages)

        return msg

    def __init__(self) -> None:

        self.nodes = []
        BBSreportutils.set_NODES(BBSutils.getenv('BBS_REPORT_NODES'))
        products_in_rdir = BBSvars.products_in_rdir
        for node in BBSreportutils.NODES:
            Node_rdir = products_in_rdir.subdir(node.node_id)
            self.nodes.append({"hostname": node.hostname,
                               "os": node.os_html,
                               "arch": node.arch,
                               "platform": node.platform,
                               "r_version": get_Rversion(Node_rdir),
                               "r_installed_packages": 0,
                               "has_buildbin": BBSreportutils.is_doing_buildbin(node)})

        self.motd = os.environ.get("BBS_REPORT_MOTD", "")
        self.skipped_pkgs = \
                bbs.parse.get_meat_packages(BBSutils.skipped_index_file)
        self.pkgs = list(MEAT_INDEX.keys()) + self.skipped_pkgs
        self.pkgs.sort(key=str.lower)
        self.version = BBSvars.bioc_version
        self.stages = [s.lower() for s in \
                BBSreportutils.stages_to_display(BBSvars.buildtype)]
        self.explanations = self.get_status_messages()

        # Load package dep graph
        if BBSvars.buildtype in ["bioc", "bioc-mac-arm64"]:
            node0 = BBSreportutils.NODES[0]
            Node0_rdir = BBSvars.products_in_rdir.subdir(node0.node_id)
            print(f"BBS> [stage6d] Get {BBSutils.pkg_dep_graph_file} from "
                  f"{Node0_rdir.label}/")
            Node0_rdir.Get(BBSutils.pkg_dep_graph_file)
            print(f"BBS> [stage6d] Loading {BBSutils.pkg_dep_graph_file} file ...")
            sys.stdout.flush()
            self.pkg_dep_graph = \
                bbs.parse.load_pkg_dep_graph(BBSutils.pkg_dep_graph_file)
            print("OK")
            self.pkgs_inner_rev_deps = \
                BBSreportutils.get_inner_reverse_deps(self.pkgs, self.pkg_dep_graph)
            sys.stdout.flush()
        else:
            self.pkgs_inner_rev_deps = None

        self.quickstats = BBSreportutils.import_BUILD_STATUS_DB(self.pkgs)
        for i in range(len(self.nodes)):
            self.quickstats[self.nodes[i]['hostname']]['os_arch'] = \
                    f"{self.nodes[i]['os']} {self.nodes[i]['arch']}"

        self.snapshot = BBSreportutils.get_vcs_meta(None, "Snapshot Date")

        print(f"BBS> [stage6d] Snapshot taken at {self.snapshot}")

        print(f"BBS> [stage6d] Getting info for all packages ...")
        sys.stdout.flush()

        for i in range(len(self.pkgs)):
            for node in BBSreportutils.NODES:
                if self.pkgs[i] not in BBSreportutils.supported_pkgs(node):
                    continue

                dcf_meat_index = MEAT_INDEX[self.pkgs[i]]
                dcf_gitlog = os.path.join(BBSvars.central_rdir_path, 'gitlog',
                                          f"git-log-{self.pkgs[i]}.dcf")
                git_url = BBSreportutils.WReadDcfVal(BBSvars.Central_rdir,
                                                     dcf_gitlog, "git_url")
                git_branch = BBSreportutils.WReadDcfVal(BBSvars.Central_rdir,
                                                        dcf_gitlog,
                                                        "git_branch")
                git_last_commit = \
                    BBSreportutils.WReadDcfVal(BBSvars.Central_rdir,
                                               dcf_gitlog, "git_last_commit")
                git_last_commit_date = \
                    BBSreportutils.WReadDcfVal(BBSvars.Central_rdir,
                                               dcf_gitlog,
                                               "git_last_commit_date")

                self.pkgs[i] = \
                    BBSPackageReference(self.pkgs[i],
                                        dcf_meat_index['Maintainer'],
                                        dcf_meat_index['Version'],
                                        dcf_meat_index.get('PackageStatus'),
                                        git_url,
                                        git_branch,
                                        git_last_commit,
                                        git_last_commit_date,
                                        self.stages)

        print("OK")

    def set_r_installed_packages(self, hostname: str,
                                 r_installed_packages: int) -> None:
        """Set r_installed_packages"""

        for i in range(len(self.nodes)):
            if self.nodes[i]["hostname"] == hostname:
                self.nodes[i]["r_installed_packages"] = r_installed_packages
        return


##############################################################################
### General stuff displayed on all pages
##############################################################################

def get_notes_to_developers(pkg: str, extra_note: str | None = None) -> str:
    """Notes for developer

    Args:
        pkg: Package name
        extra_note: Message in node

    Returns:
        Announcement to the package's developers
    """

    notes = ""
    if BBSvars.buildtype != "bioc" and not os.path.exists('Renviron.bioc'):
        return ""
    notes = "To {pkg}'s developers/maintainers:"
    if BBSvars.buildtype == "bioc":
        url = "https://bioconductor.org/developers/how-to/troubleshoot-build-report/"
        notes += (f"Allow up to 24 hours (and sometimes 48 hours) for "
                  f"your latest push to"
                  f"git@git.bioconductor.org:packages/{pkg}.git "
                  f"to reflect on this report. "
                  f"See <a href=\"{url}\">Troubleshooting Build Report</a> "
                  f"for more information.")
    if os.path.exists("Renviron.bioc"):
        notes += (f"Use the following "
                  f"<a href=\"../Renviron.bioc\">Renviron.bioc</a>"
                  f"to reproduce errors and warnings. Note: If \"R CMD "
                  f"check\" recently failed on the Linux builder over a "
                  f"missing dependency, add the missing dependency to "
                  f"\"Suggests\" in your DESCRIPTION file. See the "
                  f"<a href=\"../Renviron.bioc\">Renviron.bioc</a> "
                  f"for details.")
    if extra_note != None:
        notes += extra_note
    return notes

def get_Rversion(Node_rdir:str) -> str:
    """Get Node's R version

    Args:
        Node's R path

    Returns:
        Version of R
    """

    filename = "NodeInfo/R-version.txt"
    with Node_rdir.WOpen(filename) as f:
        r_version = bbs.parse.bytes2str(f.readline())
    return r_version

def get_Rconfig_value_from_file(Node_rdir: str, var: str) -> str:
    """Get R configuration values from Node

    Args:
        Node_rdir: R path on node
        var: name of variable on Node

    Returns:
        Output of R configuration value

    Raises:
        bbs.parse.DcfFieldNotFoundError
    """

    filename = 'NodeInfo/R-config.txt'
    with Node_rdir.WOpen(filename) as dcf:
        val = bbs.parse.get_next_DCF_val(dcf, var, True)
    if val == None:
        filename = f"{ Node_rdir.label }/{ filename }"
        raise bbs.parse.DcfFieldNotFoundError(filename, var)
    return val

def get_SysCommandVersion_from_file(Node_rdir: str,
                                    var: str,
                                    compiler: bool = True) -> str:
    """Get system command version

    Args:
        Node_rdir: R path on node
        var: name of variable on Node
        compiler: True if the command is for a compiler

    Returns:
        Output of system command version
    """

    filename = f"NodeInfo/{var}-version.txt"
    system_command_version = ""
    with Node_rdir.WOpen(filename, return_None_on_error=True) as f:
        if f == None:
            return 
        for line in f:
            system_command_version += bbs.parse.bytes2str(line)
    return system_command_version

def make_info_node_page(Node_rdir: str, node: dict, content: BBSReportContent,
                        config: BBSReportConfiguration) -> str:
    """Create an info Node page

    Args:
        Node_rdir: R path on node
        node: a node
        content: report content
        config: report configuration

    Returns:
        Name of file
    """

    page_file = f"{node['hostname']}-NodeInfo.html"
    print(f"BBS> [make_info_node_page] Write {page_file} in {os.getcwd()} ... ")
    summary = {"hostname": node["hostname"],
               "os": node["os"],
               "arch": node["arch"],
               "platform": node["platform"],
               "r_version": node["r_version"],
               "r_environment_variables": "Renviron.bioc"}

    sys_cmds = \
        [{"name": "C compiler", "compiler": True,
         "r_vars": ["CC", "CFLAGS", "CPICFLAGS"]},
        {"name": "C++ compiler", "compiler": True,
         "r_vars": ["CXX", "CXXFLAGS", "CXXPICFLAGS"]},
        {"name": "C++11 compiler", "compiler": True,
         "r_vars": ["CXX11", "CXX11FLAGS", "CXX11PICFLAGS", "CXX11STD"]},
        {"name": "C++14 compiler", "compiler": True,
         "r_vars": ["CXX14", "CXX14FLAGS", "CXX14PICFLAGS", "CXX14STD"]},
        {"name": "C++17 compiler", "compiler": True,
         "r_vars": ["CXX17", "CXX17FLAGS", "CXX17PICFLAGS", "CXX17STD"]},
        {"name": "JAVA", "compiler": False, "r_vars": []},
        {"name": "pandoc", "compiler": False, "r_vars": []}]

    for sys_cmd in sys_cmds:
        sys_cmd["r_var_val"] = {}
        cmd = sys_cmd["r_vars"][0] if len(sys_cmd["r_vars"]) else sys_cmd["name"]
        sys_cmd["sys_cmd_ver"] = \
            get_SysCommandVersion_from_file(Node_rdir, cmd, sys_cmd["compiler"])

        for r_var in sys_cmd["r_vars"]:
            sys_cmd["r_var_val"][r_var] = get_Rconfig_value_from_file(Node_rdir,
                                                                      r_var)

    template = ENV.get_template("node_info.html")

    page = template.render(title            = f"More about {node['hostname']}",
                           buildtype        = BBSvars.buildtype,
                           node             = node,
                           summary          = summary,
                           commands         = sys_cmds,
                           timestamp        = bbs.jobs.currentDateString(),
                           version          = content.version)
    with open(page_file, "w") as file:
        file.write(page)

    print("OK")
    return page_file

def make_all_info_node_pages(content: BBSReportContent,
                             config: BBSReportConfiguration) -> None:
    """Generate all info Node pages

    Args:
        content: report content
        config: report configuration
    """

    products_in_rdir = BBSvars.products_in_rdir
    for node in content.nodes:
        Node_rdir = products_in_rdir.subdir(node["hostname"])
        make_info_node_page(Node_rdir, node, content, config)
    return

def make_R_instpkgs_page(Node_rdir: str, node: dict, content: BBSReportContent,
                         config: BBSReportConfiguration) -> Tuple[str, str]:
    """Create an R packages installed on Node html page

    Args:
        Node_rdir: R path on node
        node: node
        content: report content
        config: report configuration

    Returns:
        A tuple of the html page, number of of R packages installed on Node
    """

    page_file = f"{node['hostname']}-R-instpkgs.html"
    print(f"BBS> [make_R_instpkgs_page] Write {page_file} in {os.getcwd()}")
    sys.stdout.flush()

    packages = []
    r_installed_packages = 0

    with Node_rdir.WOpen("NodeInfo/R-instpkgs.txt") as f:
        r_installed_packages = 0
        for line in f:
            package = bbs.parse.bytes2str(line).split()
            if package == ['LibPath', 'Version', 'Built']:
                continue
            packages.append({"Name": package[0],
                             "LibPath": package[1],
                             "Version": package[2],
                             "Built": package[3]})
            r_installed_packages += 1

    content.set_r_installed_packages(node["hostname"], r_installed_packages)

    template = ENV.get_template("r_packages_installed.html")
    title = f"R packages installed on {node['hostname']}"
    page = template.render(title                = title,
                           buildtype            = BBSvars.buildtype,
                           node                 = node,
                           packages             = packages,
                           timestamp            = bbs.jobs.currentDateString(),
                           version              = content.version)
    with open(page_file, "w") as file:
        file.write(page)

    print("OK")
    return (page_file, r_installed_packages)

def make_all_R_instpkgs_pages(content: BBSReportContent,
                              config: BBSReportConfiguration) -> None:
    """Generate all R packages installed on Node pages

    Args:
        content: report content
        config: report configuration
    """

    products_in_rdir = BBSvars.products_in_rdir
    for node in content.nodes:
        Node_rdir = products_in_rdir.subdir(node["hostname"])
        make_R_instpkgs_page(Node_rdir, node, content, config)
    return

def _url_to_pkg_landing_page(pkg: str) -> str:
    """Get the URL for the package's landing page"""

    buildtype = BBSvars.buildtype
    if buildtype == "cran":
        return f"https://cran.rstudio.com/package={pkg}"
    if buildtype == "books":
        return f"/books/{bioc_version}/{pkg}"
    url = f"/packages/{bioc_version}/{pkg}"
    return url

def _get_incoming_raw_result_path(pkg, node_id, stage, suffix):
    filename = f"{pkg}.{stage}-{suffix}"
    path = os.path.join(BBSvars.central_rdir_path, "products-in",
                        node_id, stage, filename)
    return path

def _get_outgoing_raw_result_path(pkg, node_id, stage, suffix):
    filename = f"{stage}-{suffix}"
    return os.path.join(pkg, "raw-results", node_id, filename)

def _get_Rcheck_path(pkg, node_id):
    Rcheck_dir = pkg + ".Rcheck"
    path = os.path.join(BBSvars.central_rdir_path, "products-in",
                        node_id, "checksrc", Rcheck_dir)
    return path

def get_summary_output(pkg: str, node_id: str, stage: str,
                       config: BBSReportConfiguration) -> Dict[str, str]:
    """Copy summary to raw results and return summary

    Args:
        pkg: package name
        node_id: node name
        stage: stage name
        config: BBS report configuration

    Return:
        DCF file contents
    """

    filepath = _get_incoming_raw_result_path(pkg, node_id, stage, 'summary.dcf')
    if not config.no_raw_results:
        dest = _get_outgoing_raw_result_path(pkg, node_id, stage, 'summary.dcf')
        pkg_raw_results_node_path = os.path.join(pkg, 'raw-results', node_id)
        if not os.path.exists(pkg_raw_results_node_path):
            os.makedirs(pkg_raw_results_node_path)
        shutil.copyfile(filepath, dest)
    return bbs.parse.parse_DCF(filepath, merge_records=True)

def write_info_dcf(pkg: str, node_id: str) -> None:
    """Write package information into a DCF file"""

    filename = f"git-log-{pkg}.dcf"
    filepath = os.path.join(BBSvars.central_rdir_path, 'gitlog', filename)
    dest = os.path.join(pkg, 'raw-results', 'info.dcf')
    shutil.copyfile(filepath, dest)
    dcf_record = MEAT_INDEX[pkg]
    info = {}
    info['Package'] = dcf_record.get('Package', 'NA')
    info['Version'] = dcf_record.get('Version', 'NA')
    info['Maintainer'] = dcf_record.get('Maintainer', 'NA')
    maintainer_email = dcf_record.get('MaintainerEmail', 'NA')
    info['MaintainerEmail'] = maintainer_email.replace('@', ' at ')
    if not os.path.exists(os.path.join(pkg, 'raw-results')):
        os.makedirs(os.path.join(pkg, 'raw-results'))
    with open(dest, 'a', encoding='utf-8') as dcf:
        for key, value in info.items():
            dcf.write('{key}: {value}\n')
    return

def get_file_contents(filepath: str, node_hostname,
                      pattern: str = None) -> Dict[str, str]:
    """Return contents of file at filepath

    Encoding is unknown so the file is opened in binary mode and decoded with
    bbs.parse.bytes2str().

    Args:
        filepath: file
        node_hostname: hostname
        pattern: regex

    Return:
        contents
    """

    contents = ""
    encoding = BBSutils.getNodeSpec(node_hostname, "encoding")
    pattern_detected = False
    if pattern != None:
        regex = re.compile(pattern)
    i = 0
    with open(filepath, "rb") as f:
        for line in f:
            i = i + 1
            if i > 99999:
                contents += "... [output truncated]\n"
                break
            line = bbs.parse.bytes2str(line)
            if pattern != None and regex.match(line):
                pattern_detected = True
            html_line = html.escape(line)  # untrusted
            try:
                contents += html_line
            except UnicodeEncodeError:
                contents += html_line.encode(encoding)
    return contents

def get_command_output(node_hostname: str, pkg: str, stage: str,
                       config: BBSReportConfiguration) -> str:
    """Get command output

    Args:
        node_hostname: hostname
        pkg: package name
        stage: stage name
        config: BBS report configuration

    Return:
        the results of the command
    """

    filepath = _get_incoming_raw_result_path(pkg, node_hostname, stage,
                                             'out.txt')
    if not os.path.exists(filepath):
        contents = ""
        contents = "Due to an anomaly in the Build System, this output "
        contents += "is not available. We apologize for the inconvenience."
        return contents

    if not config.no_raw_results:
        dest = _get_outgoing_raw_result_path(pkg, node_hostname, stage,
                                             'out.txt')
        shutil.copyfile(filepath, dest)
    return get_file_contents(filepath, node_hostname)

def get_installation_output(node_hostname: str, pkg: str) -> Dict[str, str]:
    """Get installation output

    Args:
        node_hostname: hostname
        pkg: package name

    Return:
        a dict where the file path and the results
    """

    output_filepath = {}
    Rcheck_path = _get_Rcheck_path(pkg, node_hostname)
    filename = '00install.out'
    filepath = os.path.join(Rcheck_path, filename)
    if os.path.exists(filepath):
        Rcheck_dir = pkg + ".Rcheck"
        output_filepath = os.path.join(Rcheck_dir, filename)
        return {output_filepath: get_file_contents(filepath, node_hostname)}
    return {}

def build_test2filename_dict(dirpath: str, dups: list) -> Dict[str, str]:
    """Return a dic of test files given a directory path"""

    p = re.compile('(.*)\.Rout.*')
    test2filename = {}
    for filename in os.listdir(dirpath):
        m = p.match(filename)
        if m != None:
            testname = m.group(1)
            if testname in test2filename:
                dups.append(filename)
            else:
                test2filename[testname] = filename
    return test2filename

def get_tests_outputs_from_dir(Rcheck_dir: str,
                               tests_dir: str) -> Dict[str, str]:
    """Get tests output given a directory

    Args:
        Rcheck_dir: path to Rcheck directory
        test_dir: test directory name

    Return:
        a dict where the file path is the key and the value is the results
    """

    contents = {}
    p = re.compile('(.*)\.Rout.*')
    filenames = []
    for filename in os.listdir(tests_dir):
        m = p.match(filename)
        if m != None:
             filenames.append(filename)
    filenames.sort(key=str.lower)
    for filename in filenames:
        filepath = os.path.join(tests_dir, filename)
        contents[os.path.join(Rcheck_dir, filepath)] = \
            get_file_contents(filepath, node_hostname)
    return contents

def get_tests_output(node_hostname: str, pkg: str) -> Dict[str, str]:
    """Get tests output

    Args:
        node_hostname: hostname
        pkg: package name

    Return:
        a dict where the file path is the key and the value is the results
    """

    contents = {}
    Rcheck_dir = f"{pkg}.Rcheck"
    Rcheck_path = os.path.join(BBSvars.central_rdir_path, "products-in",
                               node_hostname, "checksrc")
    if not os.path.exists(Rcheck_path):
        contents["error"] = "Due to an anomaly in the Build System, this "
        contents["error"] += "output is not available. We apologize for the "
        contents["error"] += "inconvenience.\n"
        return contents
    old_cwd = os.getcwd()
    os.chdir(Rcheck_path)
    tests_dirs = []
    # Will there be more than 1 tests directory?
    for tests_dir in os.listdir("."):
        if os.path.isdir(tests_dir) and \
           fnmatch.fnmatch(tests_dir, "tests*"):
            tests_dirs.append(tests_dir)
    for tests_dir in tests_dirs:
        contents = contents |  get_tests_outputs_from_dir(Rcheck_dir,
                                                          tests_dir)
    os.chdir(old_cwd)
    return contents

def get_example_timings(node_hostname: str, pkg: str) -> Dict[str, str]:
    """Get example timings

    Args:
        node_hostname: hostname
        pkg: package name

    Return:
        a dict where the file path is the key and the value is the results
    """

    contents = {}
    Rcheck_dir = pkg + ".Rcheck"
    Rcheck_path = os.path.join(BBSvars.central_rdir_path, "products-in",
                               node_hostname, "checksrc", Rcheck_dir)
    if not os.path.exists(Rcheck_path):
        contents["error"] = "Due to an anomaly in the Build System, this "
        contents["error"] += "output is not available. We apologize for the "
        contents["error"] += "inconvenience.\n"
        return contents
    old_cwd = os.getcwd()
    os.chdir(Rcheck_path)
    file = f"{pkg}-Ex.timings"
    if os.path.isfile(file):
        filepath = os.path.join(Rcheck_dir, file)
        with open(file, "rb") as f:
            contents[filepath] = ""
            for line in f:
                contents[filepath] += bbs.parse.bytes2str(line)
    os.chdir(old_cwd)
    return contents

def make_package_raw_results(pkg: BBSPackageReference,
                             config: BBSReportConfiguration) -> None:
    """Generate package raw-results directory

    Args:
        pkg: package
        config: report configuration
    """

    if BBSvars.buildtype != "bioc-longtests" and not config.no_raw_results:
        for node in BBSreportutils.NODES:
            if pkg.name in BBSreportutils.supported_pkgs(node) and \
                    pkg.results[node.node_id]["install"] != "skipped":
                os.makedirs(os.path.join(pkg.name, "raw-results"))
                write_info_dcf(pkg.name, node.node_id)
    return

def make_package_report(pkg: BBSPackageReference,
                        pkgs_rev_deps: dict | None,
                        content: BBSReportContent,
                        config: BBSReportConfiguration) -> None:
    """Generate package report

    Args:
        pkg: package
        pkgs_rev_deps: dependent packages
        content: report content
        config: report configuration
    """

    title = f"All results for package {pkg.name}"
    page_file = os.path.join(pkg.name, "index.html")

    quickstats_rev_deps = None
    if BBSvars.buildtype in ["bioc", "bioc-mac-arm64"] and len(pkgs_rev_deps):
        quickstats_rev_deps = BBSreportutils.compute_quickstats(pkgs_rev_deps)

    template = ENV.get_template("package_report.html")
    page = template.render(title                = title,
                           buildtype            = BBSvars.buildtype,
                           motd                 = content.motd,
                           nodes                = content.nodes,
                           ntd                  = get_notes_to_developers(pkg),
                           package              = pkg,
                           packages_rev_deps    = pkgs_rev_deps,
                           quickstats_rev_deps  = quickstats_rev_deps,
                           quickstats           = content.quickstats,
                           stages               = content.stages,
                           timestamp            = bbs.jobs.currentDateString(),
                           version              = content.version,
                           url                  = page_file)

    if not os.path.exists(pkg.name):
        os.makedirs(pkg.name)
    with open(page_file, "w") as file:
        file.write(page)
    return

def make_package_status_report(pkg: BBSPackageReference,
                               stage: str,
                               node_hostname: str,
                               content: BBSReportContent,
                               config: BBSReportConfiguration) -> None:
    """Generate node-specific package report

    Args:
        pkg: package
        stage: build stage
        node_hostname: a node hostname
        content: report content
        config: report configuration
    """

    summary = get_summary_output(pkg.name, node_hostname, stage, config)
    command_output = get_command_output(node_hostname, pkg.name, stage, config)
    installation_output = {}
    tests_output = {}
    example_timings = {}

    if stage == "checksrc":
        installation_output = get_installation_output(node_hostname, pkg.name)
        if BBSvars.buildtype != "bioc-longtests":
            tests_output = get_tests_output(node_hostname, pkg.name)
            example_timings = get_example_timings(node_hostname, pkg.name)
    title = f"{stage.removesuffix('src').capitalize()} results for {pkg.name} on {node_hostname}"
    page_file = os.path.join(pkg.name, f"{node_hostname}-{stage}.html")
    custom_note = BBSutils.getNodeSpec(node_hostname,
                                       'displayOnHTMLReport',
                                       key_is_optional=True)
    template = ENV.get_template("package_status_report.html")
    page = template.render(title                = title,
                           buildtype            = BBSvars.buildtype,
                           command_output       = command_output,
                           custom_note          = custom_note,
                           example_timings      = example_timings,
                           installation_output  = installation_output,
                           motd                 = content.motd,
                           nodes                = content.nodes,
                           ntd                  = get_notes_to_developers(pkg),
                           package              = pkg,
                           summary              = summary,
                           tests_output         = tests_output,
                           skipped_packages     = content.skipped_pkgs,
                           stage                = stage,
                           timestamp            = bbs.jobs.currentDateString(),
                           version              = content.version)

    with open(page_file, "w") as file:
        file.write(page)
    return

def make_package_reports(content: BBSReportContent,
                         config: BBSReportConfiguration) -> None:
    """Write html for all individual package reports

    Args:
        content: report content
        config: report configuration
    """

    print(f"BBS> [make_package_reports] Package Reports: BEGIN ...")
    sys.stdout.flush()

    for pkg in content.pkgs:
        try:
            pkg_rev_deps = content.pkgs_rev_deps[pkg.name]
        except:
            pkg_rev_deps = []
        make_package_report(pkg, pkg_rev_deps, content, config)
        if not config.no_raw_results:
            make_package_raw_results(pkg, config)
        for node in BBSreportutils.NODES:
            if pkg.name in BBSreportutils.supported_pkgs(node):
                for stage in content.stages:
                    if stage == "buildbin" and \
                            not BBSreportutils.is_doing_buildbin(node):
                        continue
                    status = pkg.results[node.node_id][stage.removesuffix('src')]
                    if status not in ["skipped", "NA"]:
                        make_package_status_report(pkg, stage, node.hostname,
                                                   content, config)

    print(f"BBS> [make_package_reports] Package Report: END.")
    sys.stdout.flush()
    return


##############################################################################
### Node-specific reports
##############################################################################

def make_node_report(node: dict, content: BBSReportContent,
                     config: BBSReportConfiguration) -> str:
    """Write html for all packages on a Node

    Args:
        node: a node
        content: report content
        config: report configuration

    Returns:
        Name of the file
    """

    print(f"BBS> [make_node_report] Node {node['hostname']}: BEGIN ...")
    sys.stdout.flush()

    page_file = f"{node['hostname']}-index.html"
    template = ENV.get_template("packages_report.html")


    page = template.render(title            = f"All results on {node['hostname']}",
                           buildtype        = BBSvars.buildtype,
                           compact          = config.compact,
                           motd             = content.motd,
                           nodes            = [node],
                           packages         = content.pkgs,
                           quickstats       = content.quickstats,
                           show_statuses    = True,
                           skipped_packages = content.skipped_pkgs,
                           snapshot         = content.snapshot,
                           stages           = content.stages,
                           explanations     = content.explanations,
                           timestamp        = bbs.jobs.currentDateString(),
                           version          = content.version)

    with open(page_file, "w") as file:
        file.write(page)

    print(f"BBS> [make_node_report] Node {node['hostname']}: END.")
    sys.stdout.flush()
    return page_file

def make_node_reports(content: BBSReportContent,
                      config: BBSReportConfiguration) -> None:
    """Write html files for all packages on all Nodes

    Args:
        content: report content
        config: report configuration
    """

    for node in content.nodes:
        make_node_report(node, content, config)
    return


##############################################################################
### Main page (multiple platform report)
##############################################################################

def make_main_report(content: BBSReportContent,
                     config: BBSReportConfiguration) -> None:
    """Generate the main report

    Args:
        content: report content
        config: report configuration
    """

    print(f"BBS> [make_main_report] BEGIN ...")
    sys.stdout.flush()

    title = f"Multiple platform build/check for BioC {content.version}"
    template = ENV.get_template("packages_report.html")
    page_file = "index.html"

    if not config.compact:
        page_file = "long-report.html"

    page = template.render(title            = title,
                           buildtype        = BBSvars.buildtype,
                           compact          = config.compact,
                           motd             = content.motd,
                           nodes            = content.nodes,
                           packages         = content.pkgs,
                           quickstats       = content.quickstats,
                           skipped_packages = content.skipped_pkgs,
                           stages           = content.stages,
                           timestamp        = bbs.jobs.currentDateString(),
                           version          = content.version)

    with open(page_file, "w") as file:
        file.write(page)

    print("BBS> [make_main_report] END.")

    sys.stdout.flush()
    return

def make_reports(config: BBSReportConfiguration) -> None:
    """Generate all reports

    Args:
        config: report configuration
    """

    content = BBSReportContent()
    make_all_info_node_pages(content, config)
    make_all_R_instpkgs_pages(content, config)
    make_package_reports(content, config)
    make_node_reports(content, config)
    make_main_report(content, config)
    return


##############################################################################
### MAIN SECTION
##############################################################################

def parse_options(argv):
    """Parse options

    Args:
        argv: list of command line arguments

    Returns:
        a dict with 2 key value pairs
        Key                       Value
        'no-alphabet-dispatch' -> True or False
        'no-raw-results'       -> True or False
    """

    usage_msg = 'Usage:\n' + \
        '    BBS-report.py [simple-layout] [no-alphabet-dispatch] [no-raw-results]\n'
    valid_options = ['simple-layout', 'no-alphabet-dispatch', 'no-raw-results']
    argv = set(argv[1:])
    if not argv.issubset(valid_options):
        sys.exit(usage_msg)
    options = {}
    for option in valid_options:
        options[option] = option in argv
    return options

if __name__ == "__main__":
    options = parse_options(sys.argv)
    print()
    if not os.path.isfile(BBSreportutils.BUILD_STATUS_DB_file):
        print(f"{BBSreportutils.BUILD_STATUS_DB_file} missing")
        print(f"Make sure to be in {BBSvars.Central_rdir.path}")
        print(f"before running the BBS-report.py script.")
        sys.exit("=> EXIT.")

    print('BBS> ==============================================================')
    print(f"BBS> [stage6d] STARTING stage6d at {time.asctime()} ...")
    sys.stdout.flush()

    config = BBSReportConfiguration(options['simple-layout'],
                                    options['no-raw-results'])

    print(f"BBS> [stage6d] remake_dir {config.path}")
    bbs.fileutils.remake_dir(config.path)

    print(f"BBS> [stage6d] cp {BBSutils.meat_index_file} {config.path}/")
    shutil.copy(BBSutils.meat_index_file, config.path)

    print(f"BBS> [stage6d] cp {BBSutils.skipped_index_file} {config.path}/")
    shutil.copy(BBSutils.skipped_index_file, config.path)

    print(f"BBS> [stage6d] cp {BBSreportutils.BUILD_STATUS_DB_file} {config.path}/")
    shutil.copy(BBSreportutils.BUILD_STATUS_DB_file, config.path)

    if os.path.exists(BBSreportutils.PROPAGATION_STATUS_DB_file):
        print(f"BBS> [stage6d] cp BBSreportutils.PROPAGATION_STATUS_DB_file "
              f"{config.path}/")
        shutil.copy(BBSreportutils.PROPAGATION_STATUS_DB_file, config.path)

    print(f"BBS> [stage6d] cd {config.path}/")
    os.chdir(config.path)

    BBSreportutils.write_htaccess_file()

    if config.r_environ_user:
        dst = os.path.join(config.path, 'Renviron.bioc')
        print(f"BBS> [stage6d] cp {config.r_environ_user} {dst}")
        shutil.copy(config.r_environ_user, dst)

    print(f"BBS> [stage6d] cp {config.base_css_file} {config.path}/")
    shutil.copy(config.base_css_file, config.path)

    if config.css_file:
        print(f"BBS> [stage6d] cp {config.css_file} {config.path}/")
        shutil.copy(config.css_file, config.path)

    if config.bgimg_file:
        print(f"BBS> [stage6d] cp {config.bgimg_file} {config.path}/")
        shutil.copy(config.bgimg_file, config.path)

    if config.js_file:
        print(f"BBS> [stage6d] cp {config.js_file} {config.path}/")
        shutil.copy(config.js_file, config.path)

    for color in ["Red", "Green", "Blue"]:
        icon = "%s/images/120px-%s_Light_Icon.svg.png" % \
               (os.getenv("BBS_HOME"), color)
        shutil.copy(icon, config.path)

    print(f"BBS> [stage6d] Will generate HTML report for nodes: "
          f"{BBSreportutils.NODES}")

    make_reports(config)

    print(f"BBS> [stage6d] DONE at {time.asctime()}.")
