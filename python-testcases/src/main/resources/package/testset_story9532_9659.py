"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     May 2015
@author:    Padraic Doyle, Jose Martinez, Jenny Schulze
@summary:   Integration test for story 9532: As a packager of a product to be
            deployed on LITP I want the contents of my LITP compliant ISO to be
            imported.

            Agile: STORY-9532

            Integration test for story LITPCDS-9659:
            Given a LITP deployment when I issue an LITP
            create_plan/run_plan command sequence then yum repo
            reconfiguration and peer node package updates will be supported
            in the same deployment plan.

            Agile: STORY-9659
"""

from litp_generic_test import GenericTest, attr
from litp_cli_utils import CLIUtils
import os
import sys
import socket
import exceptions
from redhat_cmd_utils import RHCmdUtils
from time import sleep
import test_constants


class Story9532(GenericTest):
    """
    Description:
        I want the contents of my LITP compliant ISO to be imported.
    """

    def setUp(self):
        """ Setup variables for every test """
        super(Story9532, self).setUp()
        self.ms_node = self.get_management_node_filename()
        self.mn_nodes = self.get_managed_node_filenames()
        self.cli = CLIUtils()
        self.rhcmd = RHCmdUtils()

        self.iso_remote_path = "/tmp/story9532_9659/"
        self.repo_remote_path = test_constants.PARENT_PKG_REPO_DIR

        self.test_pkgs = ["testpackage", "hello", "world", "popcorn-kernel"]

        self.upg_rpms = ["testpackage-1.1-1.el6.x86_64.rpm",
                          "world-1.1-1.el6.x86_64.rpm",
                          "hello-1.1-1.el6.x86_64.rpm",
                          "popcorn-kernel-1.1-1.el6.x86_64.rpm"]

        self.orig_rpms = ["testpackage-1.0-1.el6.x86_64.rpm",
                          "world-1.0-1.el6.x86_64.rpm",
                          "hello-1.0-1.el6.x86_64.rpm",
                          "popcorn-kernel-1.0-1.el6.x86_64.rpm"]

        self.plan_timeout_mins = 10

    def tearDown(self):
        """ Called after every test"""
        super(Story9532, self).tearDown()

    def _import_iso(self, iso_image_id, iso_path):
        """
        Imports an iso via import_iso
        """
        self.log("info", "a. Mount an ISO")
        self._mount_image(iso_image_id)

        self.log("info", "b. Call 'litp import_iso' on a directory.")
        self.execute_cli_import_iso_cmd(self.ms_node, iso_path)

        self.log("info", "c. Verify that litp is in maintenance mode.")
        self.assertTrue(self._litp_in_mmode())

        self.log("info", "d. Wait for import to complete.")
        self.assertTrue(self.wait_for_log_msg(self.ms_node,
            "ISO Importer is finished, exiting with 0"))

        self.log("info", "e. Verify that litp is no longer in mmode.")
        self.assertFalse(self._litp_in_mmode())

        self.log("info", "f. Verify that puppet is enabled.")
        self.assertTrue(self.check_mco_puppet_is_enabled(self.ms_node))

    def _update_repos_install_packages_run_plan(self, new_repo, repo_names,
            new_packages, upd_nodes, upd_pathes, non_upg_node, sw_items_path,
            upg_rpms, for_removal=False):
        """
        Updates the ms_url_path of a repo, adds new packages and the
        creates/runs plan and verifies the update/install

        :param new_repo: ms_url_path of new repo to be installed
        :param repo_names: name of repo items to be updated
        :param new_packages: new packages to be modelled
        :param upd_nodes: nodes that should be updated
        :param upd_pathes: path to the upd_nodes
        :param non_upg_node: node that should not be updated
        :param sw_item_path: path to /softwate/items
        :param upg_rpms: rpms to be upgraded
        :param for_removal: if set to True removes repos
        """
        self.log("info", "a. Add upgrade item")
        for (new, old) in zip(new_repo, repo_names):
            props = "ms_url_path=/{0}".format(new)
            self.execute_cli_update_cmd(self.ms_node,
                "{0}/{1}".format(sw_items_path, old),
                props)

        self.log("info", "b. Add install packages for upd_node")
        for package in new_packages:
            props = "name='{0}'".format(package)
            sw_items_url = sw_items_path + "/{0}".format(package)
            self.execute_cli_create_cmd(self.ms_node,
                                        sw_items_url,
                                        "package",
                                        props)
            for path in upd_pathes:
                self.execute_cli_inherit_cmd(self.ms_node,
                    "{0}/{1}".format(path, package),
                    "{0}/{1}".format(sw_items_path, package))

        self.log("info", "c. Add an upgrade item under the deployment.")
        deployment_url = self.find(self.ms_node,
                                       "/deployments",
                                       "deployment")[0]
        self._add_upg_item(deployment_url)

        if for_removal:
            self.log("info", "d. Remove repos from deployment")
            for path in upd_pathes:
                for repo in repo_names:
                    self.execute_cli_remove_cmd(self.ms_node,
                            "{0}/{1}".format(path, repo), add_to_cleanup=False)

            self.log("info", "e. Run 'litp create_plan'.")
            _, err, _ = self.execute_cli_createplan_cmd(self.ms_node,
                    expect_positive=False)

            for node in upd_nodes:
                for repo in repo_names:
                    self.assertTrue(self.is_text_in_list('ValidationError    '
                            'Create plan failed: Create plan failed, an '
                            'upgraded node "{0}" has a yum repository "{1}" '
                            'in "ForRemoval" state.'.format(node, repo),
                        err))

        else:
            self.log("info", "d. Run 'litp create_plan'.")
            self.execute_cli_createplan_cmd(self.ms_node)

            # Get current position in log messages before run plan
            log_path = test_constants.GEN_SYSTEM_LOG_PATH
            prev_log_pos = self.get_file_len(self.ms_node, log_path)

            self.log("info", "e. Verify that there is only one upgrade task"
                " for node")
            for node in upd_nodes:
                self._verify_update_task(node)

            self.log("info", "g. Run 'litp run_plan'.")
            self.execute_cli_runplan_cmd(self.ms_node)

            self.log("info", "h. Verify that the plan is successful.")
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                    test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

            self.log("info", "i. Verify packages updated on modeled node")
            for node in upd_nodes:
                self._verify_packages_upgraded(node, upg_rpms)

            self.log("info", "j. Verify pkgs not updated on unmodeled node")
            self._verify_packages_upgraded(non_upg_node, upg_rpms,
                expect_positive=False)

            #
            # Checking for message in logs: TC10
            #
            self.log("info", "k. Verify log message for upgrade task")
            for node in upd_nodes:
                expected_msg = "A command to upgrade the system will be run "\
                    "on node \\\"{0}\\\". To check the result of this "\
                    "operation log onto the node and run the command 'yum "\
                    "history info'".format(node)
                curr_log_pos = self.get_file_len(self.ms_node, log_path)
                test_logs_len = curr_log_pos - prev_log_pos

                cmd = self.rhcmd.get_grep_file_cmd(log_path,
                                               expected_msg,
                                               file_access_cmd="tail -n {0}"
                                               .format(test_logs_len))
                out, _, _ = self.run_command(self.ms_node, cmd,
                    default_asserts=True)
                self.assertNotEqual([], out)

    def _mount_image(self, iso_id, as_root=True):
        """ Simulate mounting an ISO on the MS by copying an image directory
        to the MS.

        All images will be in the test scripts local directory
        ./9532_9659_isos/
        They will be named "iso_dir_<iso_id>
        e.g.  .../core/9532_9659_isos/iso_dir_01/
        """
        iso_dir = "iso_dir_{0}".format(iso_id)
        tar_filename = iso_dir + ".gz.tar"
        iso_local_path = os.path.join(os.path.dirname(__file__),
                "9532_9659_isos/")
        local_tar_file = iso_local_path + tar_filename

        self.create_dir_on_node(self.ms_node, self.iso_remote_path)

        # 1. Tar up local directory
        tar_cmd = self.rhcmd.get_tar_cmd("czvf", local_tar_file, iso_dir)
        cmd = "cd {0} ; ".format(iso_local_path) + tar_cmd
        self.run_command_local(cmd)

        # 2. Copy tar file to MS
        self.copy_file_to(self.ms_node,
                          local_tar_file,
                          self.iso_remote_path,
                          root_copy=as_root)

        # 3. Untar the tar file in /tmp
        dest_dir = "--directory={0}".format(self.iso_remote_path)
        untar_cmd = self.rhcmd.get_tar_cmd("xmzvf",
                                     self.iso_remote_path + tar_filename,
                                     dest=dest_dir)

        out, _, _ = self.run_command(self.ms_node, untar_cmd,
                                     default_asserts=True)
        self.assertNotEqual([], out)

        # 4. Remove local tar files
        cmd = "rm {0}".format(local_tar_file)
        self.run_command_local(cmd)

    def _litp_in_mmode(self):
        """ Determine if litp is in maintenance mode. """
        show_cmd = self.cli.get_show_cmd("/")
        _, err, _ = self.run_command(self.ms_node, show_cmd)
        exp_err = ["ServerUnavailableError    LITP is in maintenance mode"]
        return err == exp_err

    def _backup_repos(self, repos=None):
        """ Backup the yum repositories. By default it backs up '3pp', 'litp" &
        'litp_plugins'. If a repo doen't exist it creates a directory:
        '<reponame>_none' """
        if repos is None:
            repos = ["3pp", "litp", "litp_plugins"]

        repo_paths = [os.path.join(self.repo_remote_path, repo)
                      for repo in repos]

        for repo in repo_paths:
            if self.remote_path_exists(self.ms_node, repo, expect_file=False):
                cmds = ["/bin/mv {0} {0}_bak".format(repo),
                        "/usr/bin/rsync -azH  {0}_bak/ {0}/".format(repo)]
                for cmd in cmds:
                    out, _, _ = self.run_command(self.ms_node,
                                                          cmd,
                                                          su_root=True,
                                                          su_timeout_secs=600,
                                                          default_asserts=True)
                    self.assertEqual([], out)
            else:
                cmd = "/bin/mkdir {0}_none".format(repo)
                out, _, _ = self.run_command(self.ms_node,
                                                      cmd,
                                                      su_root=True,
                                                      default_asserts=True)
                self.assertEqual([], out)

    def _restore_repos(self, repos=None):
        """ Restore the repos that were backed up by _backup_repos(). """
        if repos is None:
            repos = ["3pp", "litp", "litp_plugins"]

        repo_paths = [os.path.join(self.repo_remote_path, repo)
                      for repo in repos]

        for repo in repo_paths:
            if self.remote_path_exists(self.ms_node, "{0}_bak".format(repo),
                                       expect_file=False):
                cmds = ["/bin/rm -rf {0}".format(repo),
                        "/bin/mv {0}_bak/ {0}/".format(repo)]
                for cmd in cmds:
                    self.run_command(self.ms_node,
                                     cmd,
                                     su_root=True)
            elif self.remote_path_exists(self.ms_node, "{0}_none"
                                         .format(repo),
                                         expect_file=False):
                cmds = ["/bin/rm -rf {0}".format(repo),
                        "/bin/rmdir {0}_none".format(repo)]
                for cmd in cmds:
                    self.run_command(self.ms_node,
                                     cmd,
                                     su_root=True)

    def _create_my_repo(self, repo_dir):
        """
        Function which creates a test repo to be used for these tests
        """
        self.rhc.get_createrepo_cmd(repo_dir, update=False)
        self.run_command(
            self.ms_node, "createrepo {0}".format(repo_dir), su_root=True)
        self._check_yum_repo_is_present(repo_dir)

    def _check_yum_repo_is_present(self, repo_path):
        """
        Check that file /repodata/repomd.xml file exist under repo folder
        """
        repmod_path = repo_path + '/repodata/repomd.xml'
        self.assertTrue(self.remote_path_exists(self.ms_node, repmod_path),
            '<{0}> not found'.format(repmod_path))

    def _install_test_rpms(self, nodes, rpms):
        """ Install rpm packages on a nodes. """
        rpm_local_dir = os.path.join(os.path.dirname(__file__),
            "9532_9659_rpms")
        for node in nodes:
            self.assertTrue(self.copy_and_install_rpms(node,
                [os.path.join(rpm_local_dir, rpm) for rpm in rpms], "/tmp"))

    def _uninstall_test_rpms(self, nodes, test_pkgs):
        """ Uninstall rpm packages from nodes. """
        for node in nodes:
            for pkg in test_pkgs:
                self.remove_rpm_on_node(node, pkg)

    def _dummy_yum(self, node):
        """ Dummy the yum command on a node."""
        # 1. Replace the yum binary with a dummy that returns non-zero
        # yum_path = "/usr/bin/yum"
        yum_path = self.rhcmd.get_yum_cmd("").strip()

        cmd = self.rhcmd.get_move_cmd(yum_path,
                                      (yum_path + "_old"))

        out, _, _ = self.run_command(node, cmd, su_root=True,
                default_asserts=True)
        self.assertEqual([], out)

        file_contents = ["#!/bin/bash", "echo \"Dummy yum failure\" >&2",
                         "exit 93"]
        create_success = self.create_file_on_node(node, yum_path,
                                                  file_contents,
                                                  su_root=True,
                                                  add_to_cleanup=False)
        self.assertTrue(create_success, "File could not be created")

        cmd = "/bin/chmod +x " + yum_path
        self.run_command(node, cmd, su_root=True, default_asserts=True)

    def _fix_yum(self, node):
        """ Restore original yum to the proper location. """
        yum_path = self.rhcmd.get_yum_cmd("").strip()
        cmd = self.rhcmd.get_move_cmd((yum_path + "_old"), yum_path, True)

        self.run_command(node, cmd, su_root=True)

    def _verify_packages_upgraded(self, node, rpm_list, expect_positive=True):
        """
        Check if packages are installed.
        """
        rpm_clean_list = [rpm[:-4] for rpm in rpm_list]
        self.assertEqual(expect_positive,
            self.check_pkgs_installed(node, rpm_clean_list))

    def _cleanup_repos(self, nodes, rpm_list, repo_path):
        """
        This method downgrades packages to prev version and cleans up yum repos
        after running tests.
            1. Remove RPMs from the yum repository on MS.
            2. Update the yum repository.
            3. Clean the yum cache so queries will use actual repo contents.
            4. Uninstall test packages
        """
        all_nodes = nodes + [self.ms_node]

        # 1. Remove RPMs from the yum repository on MS.
        for rpm in rpm_list:
            self.log("info", "Removing: {0} from the repo: {1}"
                     .format(rpm, repo_path))
            repo_to_rm = repo_path + '/' + rpm
            self.remove_item(self.ms_node,
                             repo_to_rm,
                             su_root=True)

        # 2. Update the yum repository.
        cmd = "/usr/bin/createrepo --update " + repo_path
        self.run_command(self.ms_node,
                         cmd,
                         su_root=True,
                         su_timeout_secs=120)

        # 3. Clean the yum cache.
        cmd = self.rhcmd.get_yum_cmd("clean all")
        for node in all_nodes:
            self.run_command(node, cmd, su_root=True)

        # 4. Uninstall test packages
        for node in nodes:
            for package in self.test_pkgs:
                cmd = "/bin/rpm -e " + package
                self.run_command(node, cmd, su_root=True)

    def _add_upg_item(self, item):
        """ Add an upgrade item at a path. """
        if item[0] == "/":
            # Item is a deployment path.
            self.execute_cli_upgrade_cmd(self.ms_node, item)
        else:
            # Item is a node.
            node_url = self.get_node_url_from_filename(self.ms_node, item)
            self.execute_cli_upgrade_cmd(self.ms_node, node_url)

    def _remove_upgrade_items_from_model(self, nodes, run_plan=True):
        """Remove an upgrade item from a node"""
        for node in nodes:
            upg_state = self._get_nodes_upgrade_state(node)

            node_url = self.get_node_url_from_filename(self.ms_node, node)
            upg_url = node_url + "/upgrade"
            cmd_remove = self.cli.get_remove_cmd(upg_url)
            self.run_command(self.ms_node, cmd_remove)
            if upg_state in ["Updated", "Applied", "ForRemoval"]:
                self.log("info", "Removing upgrade in {0} state."
                         .format(upg_state))

                if run_plan:
                    # Run 'litp create_plan'.
                    cmd_create = self.cli.get_create_plan_cmd()
                    self.run_command(self.ms_node, cmd_create)

                    # Run 'litp run_plan'.
                    cmd_run = self.cli.get_run_plan_cmd()
                    self.run_command(self.ms_node, cmd_run)

                    # 10. Verify that the plan completes.
                    self.wait_for_plan_state(self.ms_node,
                        test_constants.PLAN_COMPLETE, self.plan_timeout_mins)

    def _get_nodes_upgrade_state(self, node):
        """ Get the state of a node's upgrade item.
            Returns False if upgrade doesn't exist
        """
        upg_url = self.get_node_url_from_filename(self.ms_node, node) \
            + "/upgrade"

        # Get a cmd which finds the 'state' value of the returned ip range path
        get_data_cmd = self.cli.get_show_data_value_cmd(upg_url,
                                                    "state")
        # Now we run the passed command, the state value is output to stdout
        stdout, _, _ = self.run_command(self.ms_node, get_data_cmd)
        if stdout:
            return stdout[0]
        else:
            return False

    def _node_rebooted(self, node):
        """
            Verify that a node  has rebooted.
        """
        node_restarted = False
        max_duration = 400
        elapsed_sec = 0
        cmd = self.rhcmd.get_cat_cmd('/proc/uptime')
        while elapsed_sec < max_duration:
            try:
                out, _, _ = self.run_command(node, cmd,
                                                  su_root=True,
                                                  default_asserts=True)
                self.assertNotEqual([], out)
                uptime_seconds = float(out[0].split()[0])
                self.log("info", "{0} is up for {1} seconds"
                         .format(node, str(uptime_seconds)))

                if uptime_seconds < 180.0:
                    self.log("info", "{0} has been rebooted"
                             .format(node))
                    node_restarted = True
                    break
            except (socket.error, exceptions.AssertionError):
                self.log("info", "{0} is not up at the moment"
                         .format(node))
            except:
                self.log("error", "Reboot check. Unexpected Exception: {0}"
                         .format(sys.exc_info()[0]))
                self.disconnect_all_nodes()

            sleep(10)
            elapsed_sec += 10

        if not node_restarted:
            self.log("error", "{0} not rebooted in last {1} seconds."
                     .format(node, str(max_duration)))
        return node_restarted

    def _import_rpms(self, rpms, repo=test_constants.OS_UPDATES_PATH_RHEL7):
        """
        Description:
            This method will import some rpms to test the upgrade process.
            Kernel upgrades's require the node to be rebooted after the package
            is installed so we support with and without kernel packages.
        Actions:
            1. Select RPM packages to upgrade.
            2. Create a directory for rpms
            3. Copy RPMs into /tmp on the MS.
            4. Import RPMs with LITP import cmd into update repo.
        """
        rpms_local_paths = []
        rpms_remote_paths = []
        rpm_remote_dir = '/tmp/story9532_9659'
        dir_to_import = rpm_remote_dir + "/rpm_to_import"
        rpm_local_dir = "9532_9659_rpms/"
        for rpm in rpms:
            rpms_local_paths.append(os.path.join(os.path.dirname(__file__),
                                                 rpm_local_dir + rpm)
                                    )

            rpms_remote_paths.append(os.path.join(dir_to_import,
                                                  rpm)
                                     )

        # 1. Select RPM packages to upgrade.
        local_file_paths = rpms_local_paths

        # 2. Create a directory for rpms to import. If it exists, remove it and
        # create it again
        self.create_dir_on_node(self.ms_node, rpm_remote_dir)
        if self.remote_path_exists(self.ms_node,
                                   dir_to_import,
                                   expect_file=False):
            self.assertTrue(self.remove_item(self.ms_node, dir_to_import))

        self.create_dir_on_node(self.ms_node, dir_to_import)

        # 3. Copy RPMs into /tmp on the ms
        for loc_path in local_file_paths:
            self.assertTrue(self.copy_file_to(self.ms_node,
                                              loc_path,
                                              dir_to_import))

        # 4. Import them with LITP import cmd into update repo
        self.execute_cli_import_cmd(self.ms_node,
                                    dir_to_import,
                                    repo)

    def _set_litp_mmode(self, enable=True):
        """ Set the maintenance mode of litp. Defaults to enabling it. """
        if enable:
            prop_val = "enabled=true"
        else:
            prop_val = "enabled=false"
        self.execute_cli_update_cmd(self.ms_node,
                                    '/litp/maintenance',
                                    prop_val)

    def _upgrade_modeled_repos_on_inherited_nodes(self, reboot_expected=False):
        """
        Combined testcase for test_01 and test_02,
        if reboot_expected a kernel package will
        be installed to force the reboot
        """

        last_rpm_index = 4 if reboot_expected else 3

        self.log("info", "1. Query model elements.")

        iso_image_id = "01"
        iso_path = self.iso_remote_path + "iso_dir_" + iso_image_id

        new_repos = ["story9532_9659_test01_1_rhel7",
                     "story9532_9659_test01_1_SUB_rhel7",
                     "story9532_9659_test01_2_rhel7"]

        # Get path in model of software items.
        sw_items_path = self.find(self.ms_node,
                             "/software",
                             "collection-of-software-item")[0]

        # Get 1st nodes path
        node_paths = self.find(self.ms_node, "/deployments", "node", True)
        upg_node_path = node_paths[0]
        non_upg_node_path = node_paths[1]

        upg_node = self.get_node_filename_from_url(self.ms_node,
                                                   upg_node_path)

        non_upg_node = self.get_node_filename_from_url(self.ms_node,
                                                       non_upg_node_path)

        nodes = self.mn_nodes
        node_1_sw_items_url = upg_node_path + "/items"

        # 2. Select upg_rpms to upgrade.
        upg_rpms = self.upg_rpms[:last_rpm_index]

        try:
            self.log("info", "2. Install old versions of test packages.")
            self._install_test_rpms(nodes, self.orig_rpms[:last_rpm_index])

            self.log("info", "3. Backup the  Litp repositories.")
            self._backup_repos(new_repos)

            self.log('info', "4. Import test ISO")
            self._import_iso(iso_image_id, iso_path)

            self.log("info", "5. Run create_repo command for each repo dir")

            for repo_name in new_repos:
                self._create_my_repo(self.repo_remote_path +
                                     repo_name)

            self.log("info", "5.5 Remove all /upgrade items")
            try:
                self.remove_itemtype_from_model(self.ms_node, 'upgrade')
            except AssertionError:
                pass
            finally:
                self.execute_cli_removeplan_cmd(
                    self.ms_node,
                    expect_positive=False
                )

            self.log("info", "6. Create yum repo in LITP model for each repo")
            yum_repo_urls = list()
            for repo_name in new_repos:
                sw_items_url = sw_items_path + "/{0}".format(repo_name)
                yum_repo_urls.append(sw_items_url)
                props = "name='{0}' ms_url_path='/{1}'".format(
                    repo_name, repo_name)
                self.execute_cli_create_cmd(self.ms_node,
                                            sw_items_url,
                                            "yum-repository",
                                            props)
            # delete repo files after cleanup
            all_nodes = self.mn_nodes + [self.ms_node]
            for repo_name in new_repos:
                for node in all_nodes:
                    self.del_file_after_run(node,
                                "/etc/yum.repos.d/{0}.repo".format(repo_name))

            self.log("info", "7. The Peer node inherits from yum repo item")
            for repo_name in new_repos:
                self.execute_cli_inherit_cmd(self.ms_node,
                    "{0}/{1}".format(node_1_sw_items_url, repo_name),
                    "{0}/{1}".format(sw_items_path, repo_name))

            self.log("info", "8. Run 'litp create_plan'.")
            self.execute_cli_createplan_cmd(self.ms_node)

            self.log("info", "9. Run 'litp run_plan'.")
            self.execute_cli_runplan_cmd(self.ms_node)

            self.log("info", "10. Verify that the plan is successful.")
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

            self.log("info", "11. Add an upgrade item under the deployment.")
            deployment_url = self.find(self.ms_node,
                                       "/deployments",
                                       "deployment")[0]
            self._add_upg_item(deployment_url)

            self.log("info", "12. Run 'litp create_plan'.")
            self.execute_cli_createplan_cmd(self.ms_node)

            self.log("info", "13. Run 'litp run_plan'.")
            self.execute_cli_runplan_cmd(self.ms_node)

            if reboot_expected:
                # Dis/reconnect to nodes. MNs may have been rebooted.
                self.disconnect_all_nodes()

                self.log("info", "14. Verify that managed node has rebooted.")
                self.assertTrue(self._node_rebooted(upg_node))

            self.log("info", "15. Verify that the plan is successful.")
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

            self.log("info", "16. Verify packages updated on modeled node")
            self._verify_packages_upgraded(upg_node, upg_rpms)

            self.log("info", "17. Verify  pkgs not updated on unmodeled node")
            self._verify_packages_upgraded(non_upg_node, upg_rpms,
                expect_positive=False)

            self.log("info", "Verify that the upgrade is Applied")
            self.assertEqual("Applied",
                        self._get_nodes_upgrade_state(upg_node))
        finally:
            self._set_litp_mmode(False)
            self.log("info", "18. Remove the upgrade item from model.")
            self._remove_upgrade_items_from_model(nodes, run_plan=False)

            self.log("info", "19. Restore the original Litp repositories.")
            self._restore_repos(new_repos)

            self.log("info", "20. Revert orig pkg, remove new rpm from repo")
            self._cleanup_repos(nodes,
                                upg_rpms,
                                test_constants.OS_UPDATES_PATH_RHEL7)

    def _verify_update_task(self, node):
        """
        for a plan in initial state, this function verifies that there is only
        one update task for the node
        """
        tasks = self.get_plan_task_states(self.ms_node,
                test_constants.PLAN_TASKS_INITIAL)
        self.assertNotEqual([], tasks)

        node_url = self.get_node_url_from_filename(self.ms_node, node)
        single_update_task = {'PATH': '{0}/upgrade'.format(node_url),
                'MESSAGE': 'Update packages on node "{0}"'.format(node)}
        self.assertTrue(single_update_task in tasks)

        for (path, message) in tasks:
            if node_url in path:
                # task affects the node, verify that there is no update task
                self.assertFalse("Update package " in message)

    @attr('all', 'revert', 'story9532_9659', 'story9532_9659_tc1')
    def test_01_p_upgrade_modeled_repos_on_inherited_nodes(self):
        """
        @tms_id: litpcds_9532_9659_tc01
        @tms_requirements_id: LITPCDS-9532, LITPCDS-9659
        @tms_title: Upgrade modeled repos on inherited nodes
        @tms_description: Verify that when there are updates in a
            litp modeled repo, and an upgrade item is added under the node
            then the managed node is updated when the user runs
            create_plan/run_plan.
        @tms_test_steps:
            @step: Install old versions of test packages
            @result: packages installed
            @step: Backup the Litp repositories
            @result: litp backed up
            @step: execute import_iso
            @result: command executed successfully
            @step: Run create_repo command for each repo dir
            @result: command executed successfully
            @step: Create yum repo in LITP model for each repo
            @result: repo created
            @step: inherit yum item onto peer nodes
            @result: item inherited
            @step: create and run plan
            @result: command executed successfully
            @step: create upgrade item under the deployment
            @result: item created
            @result: item is initial
            @step: create and run plan
            @result: command executed successfully
            @result: nodes rebooted
            @result: packages updated on modeled node
            @result:  packages not updated on un modeled node
            @step: remove upgrade item from nodes
            @result: items removed
            @step: Restore the original Litp repositories
            @result: repositories restored
            @step: Revert original package and remove new rpm from repo
            @result: packaged reverted and new repo removed
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        self._upgrade_modeled_repos_on_inherited_nodes(True)

    @attr('all', 'revert', 'story9532_9659', 'story9532_9659_tc5')
    def test_05_p_user_can_upgrade_node_new_repo_initial_state(self):
        """
        @tms_id: litpcds_9532_9659_tc05
        @tms_requirements_id: LITPCDS-9532, LITPCDS-9659
        @tms_title: user can upgrade node new repo initial state
        @tms_description: This test will verify that the user can run an
                upgrade plan for a node when there are new repos in an
                'Initial' state.
        @tms_test_steps:
            @step: Install old versions of test packages
            @result: packages installed
            @step: Create yum repo in LITP model for each repo
            @result: repo created
            @step: inherit yum item onto peer nodes
            @result: item inherited
            @result: items in Initial state
            @step:  Import a rpm to 3PP repo
            @result: rpm imported to 3PP repo
            @step: create upgrade item under the deployment
            @result: item created
            @step: create and run plan
            @result: command executed successfully
            @step: remove upgrade item from nodes
            @result: items removed
            @step: Remove yum repos and their inherited items
            @result: repositories and items removed
            @step: create and run plan
            @result: command executed successfully
            @step: Revert original package and remove new rpm from repo
            @result: packaged reverted and new repo removed
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        # 1. Query model elements.
        # Name of empty test repos
        repo_names = ["story9532_9659_test05_1",
                      "story9532_9659_test05_2"]

        # Get path in model of software items.
        sw_items_path = self.find(self.ms_node,
                             "/software",
                             "collection-of-software-item")[0]

        # Get 1st nodes path
        nodes = self.mn_nodes[:1]
        node_paths = self.find(self.ms_node, "/deployments", "node", True)
        upg_node_path = node_paths[0]

        node_1_sw_items_url = upg_node_path + "/items"

        try:
            # 2. Install old versions of test packages
            self._install_test_rpms(nodes,
                                    ["testpackage-1.0-1.el6.x86_64.rpm"])

            # 3. Run 'mkdir' to create test repo.
            for repo_name in repo_names:
                cmd = "/bin/mkdir {0}{1}".format(
                    self.repo_remote_path, repo_name)
                out, _, _ = self.run_command(self.ms_node,
                                                      cmd,
                                                      su_root=True,
                                                      default_asserts=True)
                self.assertEqual([], out)

            # 4. Run createrepo command for test repo.
            for repo_name in repo_names:
                self._create_my_repo(self.repo_remote_path +
                                     repo_name)

            # 5. Create yum repo in LITP model.
            for repo_name in repo_names:
                sw_items_url = sw_items_path + "/{0}".format(repo_name)
                props = "name='{0}' ms_url_path='/{1}'".format(
                        repo_name, repo_name)
                self.execute_cli_create_cmd(self.ms_node,
                                            sw_items_url,
                                            "yum-repository",
                                            props)

            # 6. The Peer node inherits from yum repo item.
            for repo_name in repo_names:
                self.execute_cli_inherit_cmd(self.ms_node,
                                             "{0}/{1}"
                                             .format(node_1_sw_items_url,
                                                     repo_name),
                                             "{0}/{1}".format(sw_items_path,
                                                              repo_name))

            # 7. Verify that repos are in the 'Initial' state.
            for repo_name in repo_names:
                state = self.execute_show_data_cmd(self.ms_node,
                                                  "{0}/{1}"
                                                  .format(node_1_sw_items_url,
                                                          repo_name),
                                                  "state")
                self.assertEqual(state, "Initial")

            # 8. Import a rpm to UPDATES repo
            self._import_rpms(["testpackage-1.1-1.el6.x86_64.rpm"],
                              test_constants.OS_UPDATES_PATH_RHEL7)

            # 9. Add an upgrade item under the node.
            self._add_upg_item(upg_node_path)

            # 10. Run 'litp create_plan'.
            self.execute_cli_createplan_cmd(self.ms_node)

            # 11. Run 'litp run_plan'.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 12. Verify that the plan is successful.
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                            test_constants.PLAN_COMPLETE,
                            self.plan_timeout_mins))

        finally:

            # 13. Remove the upgrade item from model.
            cmd_remove = self.cli.get_remove_cmd("{0}/{1}".format(
                                                            upg_node_path,
                                                            "upgrade"))
            self.run_command(self.ms_node, cmd_remove)

            # 14. Remove yum repos and their inherited items
            for repo_name in repo_names:
                cmd_remove_repo = self.cli.get_remove_cmd("{0}/{1}".format(
                                                          upg_node_path,
                                                          "upgrade"))
                self.run_command(self.ms_node, cmd_remove_repo)

                cmd_remove_inherit = self.cli.get_remove_cmd("{0}/{1}".format(
                                                             upg_node_path,
                                                             "upgrade"))
                self.run_command(self.ms_node, cmd_remove_inherit)

            # 15. Run 'rm -rf' to remove test repos.
            for repo_name in repo_names:
                cmd = "/bin/rm -rf {0}{1}".format(
                    self.repo_remote_path, repo_name)
                self.run_command(self.ms_node,
                                 cmd,
                                 su_root=True)
            # Remove repo files
            all_nodes = self.mn_nodes + [self.ms_node]
            for repo in repo_names:
                for node in all_nodes:
                    self.del_file_after_run(node,
                                "/etc/yum.repos.d/{0}.repo".format(repo))

            # 16. Create Plan.
            cmd_create = self.cli.get_create_plan_cmd()
            self.run_command(self.ms_node, cmd_create)

            # 17. Run Plan.
            cmd_run = self.cli.get_run_plan_cmd()
            self.run_command(self.ms_node, cmd_run)

            # 18. Wait for the plan to complete.
            self.wait_for_plan_state(self.ms_node,
                                     test_constants.PLAN_COMPLETE)

            # 19. Revert orig pkg, remove new rpm from repo
            self._cleanup_repos(nodes,
                                ["testpackage-1.1-1.el6.x86_64.rpm"],
                                test_constants.OS_UPDATES_PATH_RHEL7)

    @attr('all', 'revert', 'story9532_9659', 'story9532_9659_tc11')
    def test_11_install_reconfigure_remove_repos(self):
        """
        @tms_id: litpcds_9532_9659_tc11
        @tms_requirements_id: LITPCDS-9532, LITPCDS-9659
        @tms_title: install reconfigure remove repos
        @tms_description:
                This test will verify that it is possible to update/install
            packages from repos in initial/updated state and that an error is
            returned for update/install tasks for repos in ForRemoval state
        @tms_test_steps:
            @step: Install old versions of test packages
            @result: packages installed
            @step: Backup the Litp repositories
            @result: litp backed up
            @step: execute import_iso
            @result: command executed successfully
            @step: Run create_repo command for each repo dir
            @result: command executed successfully
            @step: Create yum repo in LITP model for each repo
            @result: repo created
            @step: inherit yum item onto peer nodes
            @result: item inherited
            @step: update yum item ms_url_path
            @result: yum item updated
            @step: create package items and inherit onto nodes
            @result: item created and inherited on to nodes
            @step: execute upgrade on deployment
            @result: command executed successfully
            @step: create and run plan
            @result: command executed successfully
            @step: update yum item ms_url_path
            @result: yum item updated
            @step: create third package item and inherit onto node
            @result: item created and inherited on to node
            @step: execute upgrade on deployment
            @result: command executed successfully
            @step: create and run plan
            @result: command executed successfully
            @step: update yum item ms_url_path
            @result: yum item updated
            @step: create fourth package item and inherit onto node
            @result: item created and inherited on to node
            @step: execute upgrade on deployment
            @result: command executed successfully
            @step: remove yum items on nodes
            @result: command executed successfully
            @step: create and run plan
            @result: command executed successfully
            @step: Restore the original Litp repositories
            @result: repositories restored
            @step: Revert original package and remove new rpm from repo
            @result: packaged reverted and new repo removed
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        new_packages = [
                ["newpackage", "newpackage2"],
                ["newpackage3"],
                ["newpackage4"]
                ]
        upg_rpms = [
                         ["testpackage-1.1-1.el6.x86_64.rpm",
                          "world-1.1-1.el6.x86_64.rpm",
                          "hello-1.1-1.el6.x86_64.rpm",
                          "newpackage-1.1-1.el6.x86_64.rpm",
                          "newpackage2-1.1-1.el6.x86_64.rpm"],
                         ["testpackage-2.1-1.el6.x86_64.rpm",
                          "world-1.1-1.el6.x86_64.rpm",
                          "hello-1.1-1.el6.x86_64.rpm",
                          "newpackage-1.1-1.el6.x86_64.rpm",
                          "newpackage2-1.1-1.el6.x86_64.rpm",
                          "newpackage3-1.1-1.el6.x86_64.rpm"
                          ]
                      ]
        orig_rpms = ["testpackage-1.1-1.el6.x86_64.rpm",
                          "world-1.0-1.el6.x86_64.rpm",
                          "hello-1.0-1.el6.x86_64.rpm"]

        iso_image_id = "11"
        iso_path = self.iso_remote_path + "iso_dir_" + iso_image_id

        new_repos_step = [
            ["story9532_9659_test01_1_rhel7",
             "story9532_9659_test01_1_SUB_rhel7"],
            ["story9532_9659_test11_1_rhel7",
             "story9532_9659_test11_1_SUB_rhel7"],
            ["story9532_9659_test21_1_rhel7",
             "story9532_9659_test21_1_SUB_rhel7"]
            ]

        self.log("info", "1. Query model elements.")
        # Get path in model of software items.
        sw_items_path = self.find(self.ms_node,
                             "/software",
                             "collection-of-software-item")[0]

        # Get 1st nodes path
        node_paths = self.find(self.ms_node, "/deployments", "node", True)
        upg_node_path = node_paths[0]
        non_upg_node_path = node_paths[1]

        upg_node = self.get_node_filename_from_url(self.ms_node,
                                                   upg_node_path)

        non_upg_node = self.get_node_filename_from_url(self.ms_node,
                                                       non_upg_node_path)

        # 2. Select upg_rpms to upgrade.
        nodes = self.mn_nodes
        node_1_sw_items_url = upg_node_path + "/items"

        upd_nodes = [upg_node]
        upd_pathes = [node_1_sw_items_url]

        try:
            #
            # 1st part: install rpms, upgrade
            #

            self.log("info", "2. Install old versions of test packages.")
            self._install_test_rpms(nodes, orig_rpms)

            self.log("info", "3. Backup the  Litp repositories.")
            self._backup_repos(new_repos_step[0])

            self.log('info', "4. Import test ISO")
            self._import_iso(iso_image_id, iso_path)

            self.log("info", "5. Run create_repo command for each repo dir")

            for repo_name in new_repos_step[0]:
                self._create_my_repo(self.repo_remote_path +
                                     repo_name)

            self.log("info", "6. Create yum repo in LITP model for each repo")
            yum_repo_urls = list()
            for repo_name in new_repos_step[0]:
                sw_items_url = sw_items_path + "/{0}".format(repo_name)
                yum_repo_urls.append(sw_items_url)
                props = "name='{0}' ms_url_path='/{1}'".format(
                    repo_name, repo_name)
                self.execute_cli_create_cmd(self.ms_node,
                                            sw_items_url,
                                            "yum-repository",
                                            props)
            # delete repo files after cleanup
            all_nodes = self.mn_nodes + [self.ms_node]
            for repo_name in new_repos_step[0]:
                for node in all_nodes:
                    self.del_file_after_run(node,
                                "/etc/yum.repos.d/{0}.repo".format(repo_name))

            self.log("info", "7. The Peer node inherits from yum repo item")
            for repo_name in new_repos_step[0]:
                for path in [node_1_sw_items_url]:
                    self.execute_cli_inherit_cmd(self.ms_node,
                        "{0}/{1}".format(path, repo_name),
                        "{0}/{1}".format(sw_items_path, repo_name))

            self._update_repos_install_packages_run_plan(new_repos_step[0],
                    new_repos_step[0], new_packages[0], upd_nodes, upd_pathes,
                    non_upg_node, sw_items_path, upg_rpms[0])
            #
            # 2nd part: reconfigure repos
            #
            self.log('info',
                     "8. Reconfigure repos(ms_url_path), add new packages")
            self._update_repos_install_packages_run_plan(new_repos_step[1],
                    new_repos_step[0], new_packages[1], upd_nodes, upd_pathes,
                    non_upg_node, sw_items_path, upg_rpms[1])

            #
            # 3rd part: reconfigure repos, and set repository for removal
            #
            self.log('info', "9. Reconfigure repos, but add them to removal")
            self._update_repos_install_packages_run_plan(new_repos_step[2],
                new_repos_step[0], new_packages[2], upd_nodes, upd_pathes,
                non_upg_node, sw_items_path, upg_rpms[1], for_removal=True)
        finally:
            self._set_litp_mmode(False)
            self._remove_upgrade_items_from_model(self.mn_nodes,
                    run_plan=False)

            # restoring model in order to delete the install tasks in
            # the plan pulled in by the removal test in step 9
            self.execute_cli_restoremodel_cmd(self.ms_node)
            self.log("info", "10. Revert orig pkg, remove new rpm from repo")
            self._cleanup_repos(nodes, upg_rpms[0],
                                test_constants.OS_UPDATES_PATH_RHEL7)

            self.log("info", "11. Restore the original Litp repositories.")
            self._restore_repos(new_repos_step[0])

    @attr('all', 'revert', 'story9532_9659', 'story9532_9659_tc12')
    def test_12_n_upgrade_fails_next_plan_has_upgrade_task(self):
        """
        @tms_id: litpcds_9532_9659_tc12
        @tms_requirements_id: LITPCDS-9532, LITPCDS-9659
        @tms_title: upgrade fails next plan has upgrade task
        @tms_description: Verify that when a deployed yum-repository has new
        upgrades and run_plan fails in the upgrade task. Next create/run_plan
        will contain an upgrade task
        @tms_test_steps:
            @step: Install old versions of test packages
            @result: packages installed
            @step: Backup the Litp repositories
            @result: litp backed up
            @step: execute import_iso
            @result: command executed successfully
            @step: Run create_repo command for each repo dir
            @result: command executed successfully
            @step: Create yum repo in LITP model for each repo
            @result: repo created
            @step: inherit yum item onto peer nodes
            @result: item inherited
            @step: create upgrade item
            @result: upgrade created
            @step: remove yum ex path
            @result: path removed
            @step: create and run plan
            @result: error messages in logs
            @result: plan fails
            @step: update upgrade item under the deployment
            @result: item upgraded
            @step: create plan
            @result: command executed successfully
            @step: restore yum ex path
            @result: yum ex path restored
            @step: Restore the original Litp repositories
            @result: repositories restored
            @step: Revert original package and remove new rpm from repo
            @result: packaged reverted and new repo removed
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        repo = "story9532_9659_test12_1_rhel7"
        test_rpms = ["hello-1.0-1.el6.x86_64.rpm",
                     "world-1.0-1.el6.x86_64.rpm"]
        test_pkgs = ["hello", "world"]

        iso_image_id = "12"
        iso_path = self.iso_remote_path + "iso_dir_" + iso_image_id

        # Get path in model of software items.
        sw_items = self.find(self.ms_node,
                             "/software",
                             "collection-of-software-item")
        self.assertNotEqual([], sw_items)
        sw_items_path = sw_items[0]

        # Get nodes path
        node_paths = self.find(self.ms_node, "/deployments", "node", True)

        nodes = self.mn_nodes
        node_to_fail = nodes[0]

        try:

            self.log("info", "1. Install old version packages")
            self._install_test_rpms(nodes, test_rpms)

            self.log("info", "2. Backup the  Litp repositories.")
            self._backup_repos([repo])

            self.log('info', "3. Import test ISO")
            self._import_iso(iso_image_id, iso_path)

            self.log("info", "4. Create yum repo in the model")
            sw_items = sw_items_path + "/{0}".format(repo)
            props = "name='{0}' ms_url_path='/{1}'".format(repo, repo)
            self.execute_cli_create_cmd(self.ms_node,
                                        sw_items,
                                        "yum-repository",
                                        props)

            self.log("info", "5. Inherit yum repos in nodes")
            for node in node_paths:
                self.execute_cli_inherit_cmd(self.ms_node,
                                        "{0}/items/{1}".format(node, repo),
                                        sw_items)
            # Make sure repo client files are removed at the end of test
            for node in nodes:
                self.del_file_after_run(node,
                            "/etc/yum.repos.d/{0}.repo".format(repo))

            self.log("info", "6. Add an upgrade item under the deployment.")
            deployment_url = self.find(self.ms_node,
                                       "/deployments",
                                       "deployment")[0]
            self._add_upg_item(deployment_url)

            self.log("info", "7. Set yum to fail")
            self._dummy_yum(node_to_fail)

            self.log("info", "8. Create plan")
            self.execute_cli_createplan_cmd(self.ms_node)

            self.log("info", "9. Run plan")
            self.execute_cli_runplan_cmd(self.ms_node)

            self.log("info", "10. Verify error in logs")
            hostname = self.get_node_att(node_to_fail, "hostname")
            self.assertTrue(self.wait_for_log_msg(self.ms_node,
                '{0} failed with message: Dummy yum failure'.format(hostname)))

            self.log("info", "11. Verify that the plan fails in update task")
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_FAILED, self.plan_timeout_mins))

            failed_task = self.get_plan_task_states(self.ms_node,
                                            test_constants.PLAN_TASKS_FAILED)
            failed_task_message = failed_task[0]['MESSAGE'].strip()
            self.assertTrue("Update packages on node" in failed_task_message)

            self.log("info",
                "12. Verify that the upgrade item is in Updated state")
            self.assertEqual("Updated "
                             "(deployment of properties indeterminable)",
                             self._get_nodes_upgrade_state(node_to_fail))

            self.log("info", "13. Create plan and check for update task")
            self.execute_cli_createplan_cmd(self.ms_node)
            plan, _, _ = self.execute_cli_showplan_cmd(self.ms_node)
            plan_dict = self.cli.parse_plan_output(plan)

            task_found = False
            for phase in plan_dict.itervalues():
                for task in phase.itervalues():
                    if self.is_text_in_list(failed_task_message,
                                            task['DESC']):
                        task_found = True
            self.assertTrue(task_found)

        finally:
            self.log("info", "14. Restore yum")
            self._fix_yum(node_to_fail)
            self.log("info", "15. Restore repo")
            self._restore_repos([repo])
            self.log("info", "16. Uninstall test rpms")
            self._uninstall_test_rpms(nodes, test_pkgs)
            self._remove_upgrade_items_from_model(nodes)

    @attr('all', 'revert', 'story9532_9659', 'story9532_9659_tc13')
    def test_13_p_no_reboot_with_kernel_packages(self):
        """
        @tms_id: litpcds_9532_9659_tc13
        @tms_requirements_id: LITPCDS-9532, LITPCDS-9659
        @tms_title: no reboot with kernel packages
        @tms_description:
            Verify that when a new repository is deployed which has kernel
            packages to be upgraded, that no reboot task is created during
            create plan.
        @tms_test_steps:
            @step: Install old versions of test packages
            @result: packages installed
            @step: Backup the Litp repositories
            @result: litp backed up
            @step: execute import_iso
            @result: command executed successfully
            @step: Run create_repo command for each repo dir
            @result: command executed successfully
            @step: Create yum repo in LITP model for each repo
            @result: repo created
            @step: inherit yum item onto peer nodes
            @result: item inherited
            @step: create upgrade item
            @result: upgrade created
            @step: create plan
            @result: plan is created
            @result: no reboot tasks in plan
            @step: Restore the original Litp repositories
            @result: repositories restored
            @step: Revert original package and remove new rpm from repo
            @result: packaged reverted and new repo removed
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        repo = "story9532_9659_test13_1_rhel7"
        test_rpms = ["popcorn-kernel-1.0-1.el6.x86_64.rpm"]
        test_pkgs = ["popcorn-kernel"]

        iso_image_id = "13"
        iso_path = self.iso_remote_path + "iso_dir_" + iso_image_id

        # Get path in model of software items.
        sw_items = self.find(self.ms_node,
                             "/software",
                             "collection-of-software-item")
        self.assertNotEqual([], sw_items)
        sw_items_path = sw_items[0]

        # Get nodes path
        node_paths = self.find(self.ms_node, "/deployments", "node", True)

        nodes = self.mn_nodes

        try:
            self.log("info", "1. Install old version packages")
            self._install_test_rpms(nodes, test_rpms)

            self.log("info", "2. Backup the  Litp repositories.")
            self._backup_repos([repo])

            self.log('info', "3. Import test ISO")
            self._import_iso(iso_image_id, iso_path)

            self.log("info", "4. Create yum repo in the model")
            sw_items = sw_items_path + "/{0}".format(repo)
            props = "name='{0}' ms_url_path='/{1}'".format(repo, repo)
            self.execute_cli_create_cmd(self.ms_node,
                                        sw_items,
                                        "yum-repository",
                                        props)

            self.log("info", "5. Inherit yum repos in nodes")
            for node in node_paths:
                self.execute_cli_inherit_cmd(self.ms_node,
                                        "{0}/items/{1}".format(node, repo),
                                        sw_items)
            # Make sure repo client files are removed at the end of test
            for node in nodes:
                self.del_file_after_run(node,
                            "/etc/yum.repos.d/{0}.repo".format(repo))

            self.log("info", "6. Add an upgrade item under the deployment.")
            deployment_url = self.find(self.ms_node,
                                       "/deployments",
                                       "deployment")[0]
            self._add_upg_item(deployment_url)

            self.log("info", "8. Create plan and check for reboot task")
            self.execute_cli_createplan_cmd(self.ms_node)
            plan, _, _ = self.execute_cli_showplan_cmd(self.ms_node)
            plan_dict = self.cli.parse_plan_output(plan)

            task_found = False
            reboot_message = "Reboot node"
            for phase in plan_dict.itervalues():
                for task in phase.itervalues():
                    if self.is_text_in_list(reboot_message,
                                            task['DESC']):
                        task_found = True
            self.assertFalse(task_found)

        finally:
            self.log("info", "13. Restore repo")
            self._restore_repos([repo])
            self.log("info", "14. Uninstall test rpms")
            self._uninstall_test_rpms(nodes, test_pkgs)
