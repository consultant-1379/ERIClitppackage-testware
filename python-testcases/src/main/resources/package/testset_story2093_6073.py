"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     June 2014
@author:    Padraic Doyle
@summary:   Integration test for story 2093. As a LITP User I want to upgrade
            RHEL & 3pps on the nodes so that I can apply security patches.
            Agile: STORY_2093
            ALSO
            Integration test for story 6073. As a LITP User I want to specify
            upgrade of RHEL & 3pps packages at cluster level so that I can
            apply security patches.
"""
import os
from litp_generic_test import GenericTest, attr
from litp_cli_utils import CLIUtils
from redhat_cmd_utils import RHCmdUtils
import test_constants


class Story2093(GenericTest):
    """
    As a LITP User I want to upgrade RHEL & 3pps on the nodes so that I can
    apply security patches.
    """

    def setUp(self):
        """Setup variables for every test"""
        super(Story2093, self).setUp()

        self.cli = CLIUtils()
        self.rhcmd = RHCmdUtils()

        self.ms_node = self.get_management_node_filename()
        self.mn_nodes = self.get_managed_node_filenames()

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
        """Runs for every test"""
        super(Story2093, self).tearDown()

    def _install_test_rpms(self, nodes, rpms):
        """ Install rpm packages on a nodes. """

        for node in nodes:
            # 1. Copy rpm package files to node
            filelist = []
            rpm_local_dir = os.path.dirname(__file__)
            rpm_remot_dir = '/tmp/story2093/'
            for rpm_file in rpms:
                rpms_local_path = os.path.join(rpm_local_dir, rpm_file)
                rpms_remot_path = os.path.join(rpm_remot_dir, rpm_file)
                filelist.append(self.get_filelist_dict(rpms_local_path,
                                                       rpms_remot_path))

            self.create_dir_on_node(node, rpm_remot_dir)
            self.assertTrue(self.copy_filelist_to(node, filelist))

            # 2. Install rpm packages.
            for rpm in rpms:
                cmd = "/bin/rpm -ivh {0}".format(rpm_remot_dir + rpm)
                _, err, ret_code = self.run_command(node,
                                                    cmd,
                                                    su_root=True)
                self.assertEqual(0, ret_code)
                self.assertEqual([], err)

    def _import_rpms(self, rpms):
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
        rpm_remote_dir = '/tmp/story2093/'
        for rpm in rpms:
            rpms_local_paths.append(os.path.join(os.path.dirname(__file__),
                                                 rpm)
                                    )

            rpms_remote_paths.append(os.path.join(rpm_remote_dir,
                                                  rpm)
                                     )

        # 1. Select RPM packages to upgrade.
        ms_rpm_paths = rpms_remote_paths
        local_file_paths = rpms_local_paths

        # 2. Create a directory for rpms
        self.create_dir_on_node(self.ms_node, rpm_remote_dir)

        # 3. Copy RPMs into /tmp on the ms
        for loc_path in local_file_paths:
            self.assertTrue(self.copy_file_to(self.ms_node,
                                              loc_path,
                                              rpm_remote_dir))

        # 4. Import them with LITP import cmd into update repo
        for rpm in ms_rpm_paths:
            self.execute_cli_import_cmd(self.ms_node,
                                        rpm,
                                        test_constants.OS_UPDATES_PATH_RHEL7)

    def _verify_test_pkgs_removed(self, nodes):
        """ Verify test packages removed"""
        rpms = self.test_pkgs

        for node in nodes:
            cmd = self.rhcmd.check_pkg_installed(rpms)
            rpm_ver, err, ret_code = self.run_command(node, cmd)
            self.assertEqual([], rpm_ver)
            self.assertEqual([], err)
            self.assertTrue(ret_code <= 1)

    def _verify_packages_upgraded(self, nodes, rpm_list, expect_positive=True):
        """
        Check if packages are installed.
        """
        for node in nodes:
            for rpm_file in rpm_list:
                # Remove '.rpm' file extension
                rpm = rpm_file.split(".rpm")[0]

                # Get command to check install state.
                cmd = RHCmdUtils.check_pkg_installed([rpm])

                # Run command to check install
                out, err, ret_code = self.run_command(node, cmd)

                self.assertFalse(err)
                self.assertEqual(0, ret_code)
                if expect_positive:
                    self.assertEqual(out[0], rpm)
                else:
                    self.assertEqual(out, [])

    def _cleanup_repos(self, nodes, rpm_list, repo_path):
        """
        This method downgrades packages to prev version and cleans up yum repos
        after running tests.
            1. Remove RPMs from the yum repository on MS.
            2. Update the yum repository.
            3. Clean the yum cache so queries will use actual repo contents.
            4. Verify on MS, that new rpms are not available".
            5. Uninstall test packages
        """
        all_nodes = nodes + [self.ms_node]

        # 1. Remove RPMs from the yum repository on MS.
        for rpm in rpm_list:
            self.log("info", "Removing: {0} from the repo: {1}"
                     .format(rpm, repo_path))
            repo_to_rm = repo_path + '/' + rpm
            self.assertTrue(self.remove_item(self.ms_node,
                                             repo_to_rm,
                                             su_root=True))

        # 2. Update the yum repository.
        cmd = "/usr/bin/createrepo --update " + repo_path
        _, err, ret_code = self.run_command(self.ms_node,
                                            cmd,
                                            su_root=True,
                                            su_timeout_secs=120)
        self.assertEqual(0, ret_code)
        self.assertFalse(err)

        # 3. Clean the yum cache.
        cmd = self.rhcmd.get_yum_cmd("clean all")
        for node in all_nodes:
            _, err, ret_code = self.run_command(node, cmd, su_root=True)
            self.assertEqual(0, ret_code)
            self.assertFalse(err)

        # 4. Verify on ms, that new rpms are not available.
        self.assertFalse(self._are_rpms_available(all_nodes, rpm_list))

        # 5. Uninstall test packages
        for node in nodes:
            for package in self.test_pkgs:
                cmd = "/bin/rpm -e " + package
                _, err, ret_code = self.run_command(node, cmd, su_root=True)
                self.assertTrue(ret_code in [0, 1])

        # 6. Verify test packages are not on the nodes.
        self._verify_test_pkgs_removed(nodes)

    def _are_rpms_available(self, node_list, rpms_list):
        """ Check if rpms are available on nodes."""
        _rpm_availability_list = []
        for node in node_list:
            for rpm in rpms_list:
                cmd = ("repoquery -q --qf "
                    "'%{name}-%{version}-%{release}.%{arch}' " + rpm)
                out, err, ret_code = self.run_command(node,
                                                      cmd,
                                                      su_root=True)
                self.assertFalse(err)
                self.assertEqual(0, ret_code)
                result = self.is_text_in_list(rpm, out)
                _rpm_availability_list.append(result)

        return "False" in _rpm_availability_list

    def _add_upg_item(self, item):
        """ Add an upgrade item at a path. """
        if item[0] == "/":
            # Item is a deployment path.
            self.execute_cli_upgrade_cmd(self.ms_node, item)
        else:
            # Item is a node.
            node_url = self.get_node_url_from_filename(self.ms_node, item)
            self.execute_cli_upgrade_cmd(self.ms_node, node_url)

    def _remove_upgrade_items_from_model(self, nodes):
        """Remove an upgrade item from a node"""
        upg_state = []
        for node in nodes:
            node_url = self.get_node_url_from_filename(self.ms_node, node)
            upg_url = node_url + "/upgrade"
            remove_cmd = self.cli.get_remove_cmd(upg_url)
            self.run_command(self.ms_node, remove_cmd)
            upg_state.append(self._get_nodes_upgrade_state(node))

        if "ForRemoval" in upg_state:
            self.log("info", "Removing upgrade items")
            # Run 'litp create_plan'.
            self.execute_cli_createplan_cmd(self.ms_node)

            # Run 'litp run_plan'.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 10. Verify that the plan completes.
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

    def _get_nodes_upgrade_state(self, node):
        """ Get the state of a node's upgrade item.
            Returns False if upgrade doesn't exist
        """
        upg_url = self.get_node_url_from_filename(self.ms_node, node) \
            + "/upgrade"

        #Get a cmd which finds the 'state' value of the returned ip range path
        get_data_cmd = self.cli.get_show_data_value_cmd(upg_url,
                                                    "state")
        #Now we run the passed command, the state value is output to stdout
        stdout, _, _ = self.run_command(self.ms_node, get_data_cmd)
        if stdout:
            return stdout[0]
        else:
            return False

    def _dummy_yum(self, node):
        """ Dummy the yum command on a node."""
        # 1. Replace the yum binary with a dummy that returns non-zero
        #yum_path = "/usr/bin/yum"
        yum_path = self.rhcmd.get_yum_cmd("").strip()

        cmd = self.rhcmd.get_move_cmd(yum_path,
                                      (yum_path + "_old"))

        out, err, ret_code = self.run_command(node, cmd,
                                              su_root=True)
        self.assertEqual(0, ret_code)
        self.assertEqual([], err)
        self.assertEqual([], out)

        file_contents = ["#!/bin/bash", "echo \"Dummy yum failure\" >&2",
                         "exit 93"]
        create_success = self.create_file_on_node(node, yum_path,
                                                  file_contents,
                                                  su_root=True,
                                                  add_to_cleanup=False)
        self.assertTrue(create_success, "File could not be created")

        cmd = "/bin/chmod +x " + yum_path
        _, err, ret_code = self.run_command(node, cmd,
                                              su_root=True)
        self.assertEqual(0, ret_code)
        self.assertEqual([], err)

    def _fix_yum(self, node):
        """ Restore original yum to the proper location. """
        yum_path = self.rhcmd.get_yum_cmd("").strip()
        cmd = self.rhcmd.get_move_cmd((yum_path + "_old"), yum_path, True)

        _, err, ret_code = self.run_command(node, cmd, su_root=True)
        self.assertEqual(0, ret_code)
        self.assertEqual([], err)

    def _create_package_inheritance(self, node_url, package_name, package_url):
        """
        Description:
            Create package inheritance on the test node.
        Args:
            node_url (str): node url
            package_name (str): package name
            package_url (str): package software url
        Actions:
            1. Create package inheritance using CLI.
        Results:
            Path in litp tree to the created package inheritance.
        """
        # 1. Inherit package with cli
        node_package_url = node_url + "/items/{0}".format(package_name)
        self.execute_cli_inherit_cmd(self.ms_node,
                                     node_package_url,
                                     package_url)
        return node_package_url

    def _create_package(self,
                        package_name,
                        version=None,
                        release=None,
                        expected_state=True):
        """
        Description:
            Create test package
        Args:
            package_name (str): package name
            expected_state (bool): If True expect positive is True
                                   if False expect positive is False
        Actions:
            1. Get software items collection path
            2. Create test package
        Results:
            stdmsg, stderr
        """
        # 1. Get items path
        items = self.find(self.ms_node, "/software", "software-item", False)
        items_path = items[0]

        # 2. Create a package with cli
        package_url = items_path + "/" + package_name
        props = "name='{0}'".format(package_name)
        if version:
            props += " version={0}".format(version)
        if release:
            props += " release={0}".format(release)

        self.execute_cli_create_cmd(
            self.ms_node,
            package_url,
            "package",
            props,
            args="",
            expect_positive=expected_state)

        return package_url

    @attr('all', 'revert', 'story2093', '2093_03')
    def test_03_p_no_tasks_nodes_already_upgraded(self):
        """
        @tms_id: litpcds_2093_tc03
        @tms_requirements_id: LITPCDS-2093
        @tms_title: no tasks nodes already upgraded
        @tms_description:
            This test will verify that if an upgrade item is added under a
            deployment and there are RHEL and_or 3pp update packages available,
            tasks are added only for nodes that have available upgrades. If a
            node has been already updated by a plan that subsequently failed, a
            new plan wont contain tasks for nodes already upgraded.
        @tms_test_steps:
            @step: Install old versions of test packages.
            @result: old versions of test packages installed
            @step: Import version 1.1 rpms into the repository
            @result: rpm imported
            @step: create upgrade item under deployment
            @result: item created
            @step: Set yum to fail on first node
            @result: yum set to fail on node 1
            @step: execute create and run plan
            @result: plan fails
            @step: create plan
            @result: plan created
            @step: set yum not to fail on node1
            @result: yum set to not fail
            @step: Revert to original package and remove new rpm from repo.
            @result: rmp removed
            @step: Remove the upgrade item from model.
            @result: Upgrade item removed from model
            @step: Verify that the original packages have been restored.
            @result: package has been restored
            @step: Remove the upgrade item node 1 and node 2
            @result: items removed
            @step: execute create and run plan
            @result: command executed successfully
        @tms_test_precondition:NA
        @tms_execution_type: Automated


        """
        # 1. Define nodes that should be upgraded.
        successful_node = self.mn_nodes[0]

        # 2. Select a node to fail.
        fail_node = self.mn_nodes[-1]

        try:
            # 3. Install old versions of test packages.
            self._install_test_rpms(self.mn_nodes, self.orig_rpms[0:2])

            # 4. Select rpms to upgrade.
            rpms = self.upg_rpms[0:2]

            # 5. Import version 1.1 rpms into the repository.
            self._import_rpms(rpms)

            # 6. Add an upgrade item under the deployment.
            deploy_url = self.find(self.ms_node,
                                   "/deployments",
                                   "deployment")[0]
            self._add_upg_item(deploy_url)

            # 7. Set yum to fail on second node.
            self._dummy_yum(fail_node)

            # 8. Run 'litp create_plan'.
            self.execute_cli_createplan_cmd(self.ms_node)

            # 9. Run 'litp run_plan'.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 10. Verify that the plan fails.
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_FAILED, self.plan_timeout_mins))

            # 11. Verify that packages are updated on the node(s) with good yum
            self._verify_packages_upgraded([successful_node], rpms)

            # 12. Run 'litp create_plan'.
            self.execute_cli_createplan_cmd(self.ms_node)

            # 13. Verify that there are no tasks for the successful node.
            plan, _, _ = self.execute_cli_showplan_cmd(self.ms_node)
            plan_dict = self.cli.parse_plan_output(plan)

            hostname = self.get_node_att(successful_node, "hostname")
            for _, phase in plan_dict.items():
                for _, task in phase.items():
                    self.assertFalse(hostname in task["DESC"])
                    self.log("info", "{0} is not in task {1}"
                             .format(hostname, task["DESC"]))
        finally:
            # 14. Revert the dummy yum.
            self._fix_yum(fail_node)

            # 15. Revert to original package and remove new rpm from repo.
            self._cleanup_repos(self.mn_nodes,
                                rpms,
                                test_constants.OS_UPDATES_PATH_RHEL7)

            # 16. Remove the upgrade item from model.
            self._remove_upgrade_items_from_model(self.mn_nodes)

    @attr('all', 'revert', 'story2093', '2093_05')
    def test_05_n_packages_dependent_on_versions_not_updated(self):
        """
        @tms_id: litpcds_2093_tc05
        @tms_requirements_id: LITPCDS-2093
        @tms_title: packages dependent on versions not updated
        @tms_description:
            This test will verify that upgrades dependent on versions of
            packages in the model with a specific version are not updated.
            Package 'hello' has an rpm dependency on the same version of
            package 'world'. And world is fixed in the model.
        @tms_test_steps:
            @step: Import hello_1.1, hello_1.0, world_1.0 packages
            @result: packages imported
            @step: create upgrade item under node 1
            @result: item created
            @step: execute create and run plan
            @result: error message logged
            @result: plan fails
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        self.log('info',
        "Specify packages to upgrade which doesn't include dependent 'world'")
        upg_rpms = [self.upg_rpms[0], self.upg_rpms[2]]

        node = self.mn_nodes[0]
        try:
            self.log('info', "Install packages on node.")
            self._install_test_rpms([node], self.orig_rpms[0:3])

            self.log('info', "Import version 1.1 rpms into the repository.")
            self._import_rpms(upg_rpms)

            self.log('info', "Add an upgrade item under a node.")
            self._add_upg_item(node)

            self.log('info', "Execute create_plan command")
            self.execute_cli_createplan_cmd(self.ms_node)

            self.log('info', "Run 'litp run_plan'.")
            self.execute_cli_runplan_cmd(self.ms_node)

            self.log('info', "Verify that an error message is logged.")
            hostname = self.get_node_att(node, "hostname")
            expected_msg = ("{0} failed with message: Error: Package: {1}"
                            .format(hostname, upg_rpms[1].split(".rpm")[0]))

            self.assertTrue(self.wait_for_log_msg(self.ms_node, expected_msg))

            self.log('info',
            "Verify that the package cannot be upgraded and the plan fails.")
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_FAILED, self.plan_timeout_mins))

        finally:
            self.log('info', "Remove new rpm from repo.")
            self._cleanup_repos([node],
                                upg_rpms,
                                test_constants.OS_UPDATES_PATH_RHEL7)

            self.log('info', "Remove the upgrade items from model.")
            self._remove_upgrade_items_from_model([node])

    @attr('all', 'revert', 'story2093', '2093_06', 'cdb_priority1')
    def test_06_p_packages_dependent_versions_updated(self):
        """
        @tms_id: litpcds_2093_tc06
        @tms_requirements_id: LITPCDS-2093
        @tms_title: packages dependent versions updated
        @tms_description:
            This test will verify that upgrades dependent on versions of
            packages with a specific version are updated if dependent package
            available.
        @tms_test_steps:
            @step: Install hello_1.0' package and 'world_1.0' package.
            @result: package installed
            @step: Import hello_1.1, world_1.1 packages
            @result: packages imported
            @step: create upgrade item under node 1
            @result: item created
            @step: execute create and run plan
            @result: command executes successfully
            @step: remove rpms
            @result: rpms removed
            @step: remove upgrade item
            @result: item is in for removal state
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        # 1. Specfy packages to upgrade which includes dependent 'world'
        upg_rpms = self.upg_rpms[0:3]

        node = self.mn_nodes[0]
        try:
            # 2. Install version 1.0 of packages on node.
            self._install_test_rpms([node], self.orig_rpms[0:3])

            # 3. Import the version 1.1 RPMs.
            self._import_rpms(upg_rpms)

            # 4. Add an upgrade item under a node.
            self._add_upg_item(node)

            # 5. Execute create_plan command
            self.execute_cli_createplan_cmd(self.ms_node)

            # 6. Run 'litp run_plan'.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 7. Verify that the package is upgraded and the plan succeeds.
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

        finally:
            # 9. Remove new rpm from repo.
            self._cleanup_repos([node],
                                upg_rpms,
                                test_constants.OS_UPDATES_PATH_RHEL7)

            # 10. Remove the upgrade items from model.
            self._remove_upgrade_items_from_model([node])

    @attr('all', 'revert', 'story2093', '2093_07')
    def test_07_p_packages_dependent_on_model_versions_not_updated(self):
        """
        @tms_id: litpcds_2093_tc07
        @tms_requirements_id: LITPCDS-2093
        @tms_title: packages dependent on model versions not updated
        @tms_description:
            This test will verify that upgrades dependent on versions of
            packages in the model with a specific version are not updated.
            Package 'hello' has an rpm dependency on the same version of
            package 'world'. And world is fixed in the model.
        @tms_test_steps:
            @step: create package item under /software
            @result:  package item created
            @step: inherit package item on to nodes
            @result:  package item inherited
            @step: Import hello_1.1, hello_1.0, world_1.0 packages
            @result: packages imported
            @step: create upgrade item under node 1
            @result: item created
            @step: execute create and run plan
            @result: plan fails
            @result: error message logged
            @step: remove rpms
            @result: rpms removed
            @step: remove upgrade item
            @result: item is in for removal state
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        # 1. Specfy packages to attempt to upgrade.
        orig_rpms = self.orig_rpms[0:3]
        upg_rpms = self.upg_rpms[0:3]

        node = self.mn_nodes[0]
        log_path = test_constants.GEN_SYSTEM_LOG_PATH
        log_len = self.get_file_len(self.ms_node, log_path)
        try:
            # 2. Import version 1.0 rpms into the repository.
            self._import_rpms(orig_rpms)

            # 3. Install version 1.0 of packages on node.
            self._install_test_rpms([node], self.orig_rpms[0:3])

            # 4. Create the world package in the model fixing version.
            package_url = self._create_package("world", "1.0", "1.el6")

            # 5. Inherit the package item to a node.
            node_url = self.get_node_url_from_filename(self.ms_node, node)
            self._create_package_inheritance(node_url, "world", package_url)

            # 6. Create a plan.
            self.execute_cli_createplan_cmd(self.ms_node)

            # 7. Run the plan.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 8. Verify that the plan succeeds.
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

            # 9. Import version 1.1 rpms into the repository.
            self._import_rpms(upg_rpms)

            # 10. Add an upgrade item under a node.
            self._add_upg_item(node)

            # 11. Execute create_plan command
            self.execute_cli_createplan_cmd(self.ms_node)

            # 12. Run 'litp run_plan'.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 13. Verify that the package cannot be upgraded and the plan fails
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_FAILED, self.plan_timeout_mins))

            # 14. Verify that an appropriate error message is logged.
            expect_msg = "Requires: world = 1.1"
            log_msg = self.wait_for_log_msg(self.ms_node, expect_msg,
                                            log_file=log_path,
                                            log_len=log_len,
                          rotated_log=test_constants.LOGROTATED_SYSLOG_FILE1)

            self.assertTrue(log_msg, 'Expected Error message is missing in {0}'
                            .format(log_path))
        finally:
            # 15. Uninstall test packages and cleanup repos
            self._cleanup_repos([node],
                                orig_rpms + upg_rpms,
                                test_constants.OS_UPDATES_PATH_RHEL7)

            # 16. Remove the upgrade items from model.
            self._remove_upgrade_items_from_model([node])

    @attr('all', 'revert', 'story2093', '2093_19')
    def test_19_p_node_already_upgraded_subsequent_deployment_upgrade(self):
        """
        @tms_id: litpcds_2093_tc19
        @tms_requirements_id: LITPCDS-2093
        @tms_title: node already upgraded subsequent deployment upgrade
        @tms_description:
            This test verifies that when 1st node has been upgraded with a node
            level upgrade and subsequently a "deployment upgrade" is requested
            then create_plan doesn't create tasks for upgraded node (1st node).
        @tms_test_steps:
            @step: Install old versions of test packages.
            @result: old versions of test packages installed
            @step: Import version 1.1 rpms into the repository
            @result: rpms imported
            @step: execute upgrade on node 1
            @result: node 1 upgraded
            @step: execute create and run plan
            @result: command executed successfully
            @result: packages are updated
            @step: execute upgrade on deployment level
            @result: item is created
            @step: execute create and run plan
            @result: command executed successfully
            @result: No upgrade task for node 1
            @step: Revert to original package and remove new rpm from repo.
            @result: rmp removed
            @step: Remove the upgrade item from model.
            @result: Upgrade item removed from model
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        rpms_for_update = self.upg_rpms[0:2]
        node = self.mn_nodes[0]
        node_hostname = self.get_node_att(node, "hostname")

        try:
            # 1. Install version 1.0 of packages on nodes.
            self._install_test_rpms(self.mn_nodes, self.orig_rpms[0:2])

            # 2. Import RPMs.
            self._import_rpms(rpms_for_update)

            # 3. Add an upgrade item under a selected node.
            self._add_upg_item(node)

            # 4. Execute create_plan command.
            self.execute_cli_createplan_cmd(self.ms_node)

            # 5. Run 'litp run_plan'.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 6. Verify that the plan is successful.
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

            # 7. Verify that packages are updated on the node.
            self._verify_packages_upgraded([node], rpms_for_update)

            # 8. Add an upgrade at deployment level.
            deployment_url = self.find(self.ms_node,
                                       "/deployments",
                                       "deployment")[0]
            self._add_upg_item(deployment_url)

            # 9. Execute create_plan command.
            self.execute_cli_createplan_cmd(self.ms_node)

            # 10. Verify that there is no upgrade for the first node.
            self.execute_cli_showplan_cmd(self.ms_node)

            plan, _, _ = self.execute_cli_showplan_cmd(self.ms_node)
            plan_dict = self.cli.parse_plan_output(plan)

            for _, phase in plan_dict.items():
                for _, task in phase.items():
                    self.assertFalse(self.is_text_in_list(node_hostname,
                                     task["DESC"]))

                    self.log("info", "No upgrade task for {0} in task {1}"
                             .format(node_hostname, task["DESC"]))

        finally:
            # 11. Revert to original package and remove new rpm from repo.
            self._cleanup_repos(self.mn_nodes,
                                rpms_for_update,
                                test_constants.OS_UPDATES_PATH_RHEL7)

            # 12. Remove the upgrade items from model.
            self._remove_upgrade_items_from_model(self.mn_nodes)

    @attr('all', 'revert', 'story6073', '6073_24')
    def test_24_p_existing_packages_preserved_new_package(self):
        """
        Description:
            This test will verify that if a new package with a pinned version
            is installed, existing pinned packages are preserved in the
            versionlock file
        Actions:
            1. Import rpms.
            2. Create the world package in the model fixing version.
            3. Inherit the package item to a node.
            4. Create a plan.
            5. Run the plan.
            6. Verify that the plan succeeds.
            7. Create a second 'pinned' package.
            8. Inherit the package item to a node.
            9. Create a plan.
            10. Run the plan.
            11. Verify that the plan succeeds.
            12. Verify that packages versions are present in versionlock.
            13. Revert to original package and remove new rpm from repo.
        Result:
            If a new package with a pinned version is installed on a node,
            the first package version should be present in the versionlock file
        """
        node = self.mn_nodes[0]
        rpms = self.orig_rpms[0:2]

        try:
            # 1. Import rpms.
            self._import_rpms(rpms)

            # 2. Create the world package in the model fixing version.
            package_url = self._create_package("world", "1.0", "1.el6")

            # 3. Inherit the package item to a node.
            node_url = self.get_node_url_from_filename(self.ms_node, node)
            self._create_package_inheritance(node_url, "world", package_url)

            # 4. Create a plan.
            self.execute_cli_createplan_cmd(self.ms_node)

            # 5. Run the plan.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 6. Verify that the plan succeeds.
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

            # 7. Create a second 'pinned' package.
            package_url2 = self._create_package("testpackage", "1.0", "1.el6")
            node_url2 = self.get_node_url_from_filename(self.ms_node, node)

            # 8. Inherit the package item to a node.
            self._create_package_inheritance(node_url2,
                                             "testpackage",
                                             package_url2)
            # 9. Create a plan.
            self.execute_cli_createplan_cmd(self.ms_node)

            # 10. Run the plan.
            self.execute_cli_runplan_cmd(self.ms_node)

            # 11. Verify that the plan succeeds.
            self.assertTrue(self.wait_for_plan_state(self.ms_node,
                test_constants.PLAN_COMPLETE, self.plan_timeout_mins))

            # 12. Verify that packages versions are present in versionlock.
            cmd = "/usr/bin/yum versionlock"

            versionlock_list, err, ret_code = self.run_command(node,
                                                       cmd,
                                                       su_root=True)
            self.assertFalse(err)
            self.assertEqual(0, ret_code)
            self.assertNotEqual([], versionlock_list)
            self.assertTrue(
                self.is_text_in_list("testpackage-1.0", versionlock_list)
                )
            self.assertTrue(
                self.is_text_in_list("world-1.0", versionlock_list)
                )

        finally:
            # 11. Revert to original package and remove new rpm from repo.
            self._cleanup_repos([node],
                                rpms,
                                test_constants.OS_UPDATES_PATH_RHEL7)
