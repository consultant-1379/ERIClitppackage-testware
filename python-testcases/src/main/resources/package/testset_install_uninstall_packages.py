#!/usr/bin/env python

'''
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     February 2014
@author:    Stefan
@summary:   System Test for "InstallUninstallPkg"
            Agile: EPIC-xxxx, STORY-xxxx, Sub-task: STORY-xxxx
'''

from litp_generic_test import GenericTest, attr
from litp_cli_utils import CLIUtils
from redhat_cmd_utils import RHCmdUtils
import test_constants


class InstallUninstallPkg(GenericTest):

    """
    Description:
        TESTS MOVED FROM SYSTEM TEST

        These tests are checking the litp  mechanism
        for installing/uninstalling rpm packages that
        are present in LITP Repositories.
    """

    def setUp(self):
        super(InstallUninstallPkg, self).setUp()

        self.nano_pkg = 'nano'
        self.telnet_pkg = 'telnet'
        self.finger_pkg = 'finger'
        self.wireshark_pkg = 'wireshark'
        self.dstat_pkg = 'dstat'
        self.zsh_pkg = 'zsh'
        self.pkg_list_1 = 'pkg_list_1'
        self.pkg_list_2 = 'pkg_list_2'

        self.ms_node = self.get_management_node_filename()
        self.mn_nodes = self.get_managed_node_filenames()
        self.redhat = RHCmdUtils()
        self.cli = CLIUtils()
        self.timeout_mins = 50

        # Get all software-items
        self.items_path = self.find(self.ms_node, "/software",
                                    "collection-of-software-item")[0]
        # Get peer node1/peer node2 litp path present in litp tree
        self.nodes_path = self.find(self.ms_node, "/deployments", "node")

    def tearDown(self):
        """Runs for every test"""
        super(InstallUninstallPkg, self).tearDown()

    #TEST MOVED FROM ST
    #tests merged:
    #-testset_install_uninstall_packages.py.test_03_create_pkg_list
    #-testset_install_uninstall_packages.py.test_05_add_pkg_to_node
    #-testset_install_uninstall_packages.py.test_06_remove_pkg_list
    #-testset_install_uninstall_packages.py.test_07_remove_pkg_after_inherit

    #Functionality moved to AT:
    #ats/package/install_uninstall_packages/install_uninstall_packages.at
    #-testset_install_uninstall_packages.py.test_09_multiple_references
    @attr('all', 'revert', 'install_uninstall_packages',
          'install_uninstall_packages_tc03')
    def test_03_create_pkg_list(self):
        """
        @tms_id: litpcds_2093st_tc01
        @tms_requirements_id: LITPCDS-2093
        @tms_title: Test installation and removal of packages.
        @tms_description:
            -Creates the definition for a list of rpm packages.
            Inherit the previously created package list on nodes
            -Checking that a new package can be added
            to an existing package list.
            -Checking that a package list that was
            previously installed can be successfully removed.
            -LITP should not install the removed package on peer nodes that
            inherit the package-list.
            -Check if LITP Model is throwing an error
            when user tries to install two packages that are refering
            to the same package.

            -Updated test to cover LITPCDS-12018:
                -Check that user can remove inherit source/or their inherited
                descendent Items

        @tms_test_steps:
            @step: Create a list of commands to install/delete packages
            @result: Command list created
            @step: Execute commands
            @result: Model updated as expected
            @step: Create plan
            @result: Plan created
            @step: Run the plan
            @result: Plan runs to success
            @step: Check telnet package not intalled on nodes
            @result: Telnet package is not on nodes
            @step: Create a new wireshark package in the model
            @result: item created in model
            @step: Run remove on package zsh installed on the node
            @result: item goes to ForRemoval state
            @step: Create and run a plan
            @result: Plan runs to success.
            @step: Check wireshark package was installed to nodes.
            @result: Wireshare package is installed on nodes
            @step: Check zsh package is no longer present on nodes
            @result: zsh package is no longer present on nodes.
            @step: Remove dstat package from source
            @result: model updated as expected
            @step: Create and run plan.
            @result: Plan completes to success
            @step: check dstat package is removed from node
            @result: Package removed from node.
            @step: Run remove on packages from all nodes
            @result: model updated as expected
            @step: create and run plan.
            @result: plan completes to success.
        @tms_test_precondition: na
        @tms_execution_type: Automated
        """
        cmd_list = list()

        self.log("info", "# 1. Create the package-list definition.")
        # create package list
        props = 'name=' + self.pkg_list_1
        cmd_list.append(self.cli.get_create_cmd(self.items_path + '/' + \
                        self.pkg_list_1, 'package-list', props))

        # create all the packages inside the package-list
        # create nano package
        props = 'name=' + self.nano_pkg
        cmd_list.append(self.cli.get_create_cmd(self.items_path + '/' + \
                        self.pkg_list_1 + '/packages/' + self.nano_pkg, \
                        'package', props))

        # create telnet package
        props = 'name=' + self.telnet_pkg
        cmd_list.append(self.cli.get_create_cmd(self.items_path + '/' + \
                        self.pkg_list_1 + '/packages/' + self.telnet_pkg, \
                        'package', props))

        # create finger package
        props = 'name=' + self.finger_pkg
        cmd_list.append(self.cli.get_create_cmd(self.items_path + '/' + \
                        self.pkg_list_1 + '/packages/' + self.finger_pkg, \
                        'package', props))

        props = 'name=' + self.pkg_list_2
        cmd_list.append(self.cli.get_create_cmd(self.items_path + '/' + \
                        self.pkg_list_2, 'package-list', props))

        # create all the packages inside the package-list
        # create zsh package
        props = 'name=' + self.zsh_pkg
        cmd_list.append(self.cli.get_create_cmd(self.items_path + '/' + \
                        self.pkg_list_2 + '/packages/' + self.zsh_pkg, \
                        'package', props))

        # create dstat package
        props = 'name=' + self.dstat_pkg
        cmd_list.append(self.cli.get_create_cmd(self.items_path + '/' + \
                        self.pkg_list_2 + '/packages/' + self.dstat_pkg, \
                        'package', props))

        self.log("info", "# 2. Inherit package-list on nodes.")
        for path in self.nodes_path:
            for pkg_list in [self.pkg_list_1, self.pkg_list_2]:
                # Create a link to package list on node1
                cmd_list.append(self.cli.get_inherit_cmd(path + \
                                '/items/' + pkg_list,
                                self.items_path + '/' + pkg_list))

        self.log("info", "# 3. Remove a telnet from  package list")
        # Remove a telnet from  package list
        cmd_list.append(self.cli.get_remove_cmd(self.items_path + '/' + \
                        self.pkg_list_1 + '/packages/' + self.telnet_pkg))

        # Check you can create a plan without error
        cmd_results = self.run_commands(self.ms_node, cmd_list)
        self.assertEqual(self.get_errors(cmd_results),
                         [],
                         "Error in commands")
        self.assertTrue(self.is_std_out_empty(cmd_results),
                        "Error std_out not empty")

        self.log("info", "# 4. Create and Run Plan.")
        # CREATE PLAN
        self.execute_cli_createplan_cmd(self.ms_node)
        # SHOW PLAN
        self.execute_cli_showplan_cmd(self.ms_node)
        # RUN PLAN
        self.execute_cli_runplan_cmd(self.ms_node)
        # Check if plan completed successfully
        completed_successfully = \
            self.wait_for_plan_state(self.ms_node,
                                     test_constants.PLAN_COMPLETE,
                                     self.timeout_mins)
        self.assertTrue(completed_successfully, "Plan was not successful")

        self.log("info", "# 5. Check that 'telnet' rpm package was not" + \
                 " installed on peer nodes")
        # Check that "telnet" rpm package was not installed on peer nodes
        cmd = self.redhat.check_pkg_installed([self.telnet_pkg])
        for node in self.mn_nodes:
            out, err, rc = self.run_command(node, cmd)
            self.assertNotEqual(0, rc)
            self.assertEqual([], out)
            self.assertEqual([], err)

        self.log("info", "# 6. Add a package rpm to package list.")
        # Add a new package to package list
        props = 'name=' + self.wireshark_pkg
        cmd = self.cli.get_create_cmd(self.items_path + '/' + \
                        self.pkg_list_1 + '/packages/' + self.wireshark_pkg,
                        'package', props)
        self.run_command(self.ms_node, cmd, default_asserts=True)

        self.log("info", "# 7. Remove an inherited package 'zsh'" + \
                         "list.")
        for path in self.nodes_path:
            self.execute_cli_remove_cmd(self.ms_node,
                '{0}/items/{1}/packages/{2}'.format(path,
                                                   self.pkg_list_2,
                                                   self.zsh_pkg))

        self.log("info", "# 8. Create and Run Plan.")
        # CREATE PLAN
        self.execute_cli_createplan_cmd(self.ms_node)
        # SHOW PLAN
        self.execute_cli_showplan_cmd(self.ms_node)
        # RUN PLAN
        self.execute_cli_runplan_cmd(self.ms_node)
        # Check if plan completed successfully
        completed_successfully = \
            self.wait_for_plan_state(self.ms_node,
                                     test_constants.PLAN_COMPLETE,
                                     self.timeout_mins)
        self.assertTrue(completed_successfully, "Plan was not successful")

        self.log("info", "# 9. Check package 'wireshark' was successfully" + \
                 " installed on nodes")
        # Check that the new rpm package was installed on peer nodes
        cmd = self.redhat.check_pkg_installed([self.wireshark_pkg])
        for node in self.mn_nodes:
            self.run_command(node, cmd, default_asserts=True)

        self.log("info", "# 10. Check package 'zsh' was successfully" + \
                 " removed from nodes")
        for node in self.mn_nodes:
            self.assertFalse(self.check_pkgs_installed(node, [self.zsh_pkg]))

        self.log("info", "# 11. Remove an inherit source package-list.")
        self.execute_cli_remove_cmd(self.ms_node,
                                    "{0}/{1}".format(self.items_path,
                                                     self.pkg_list_2))
        self.run_and_check_plan(self.ms_node,
                                test_constants.PLAN_COMPLETE,
                                self.timeout_mins)
        self.log("info", "# 12. Check package 'dstat' was successfully" + \
                 " removed from nodes")
        for node in self.mn_nodes:
            self.assertFalse(self.check_pkgs_installed(node,
                                                       [self.dstat_pkg]))

        self.log("info", "# 13. Run remove command against an existing" + \
                 " package list.")
        cmd_list3 = list()
        # Remove package list item from all peer nodes
        cmd_list3.append(self.cli.get_remove_cmd(self.nodes_path[0] + \
                        '/items/' + self.pkg_list_1))

        # Remove the package list from software items
        cmd_list3.append(self.cli.get_remove_cmd(self.items_path + '/' + \
                        self.pkg_list_1))

        # Run LITP CLI Commands
        cmd_results = self.run_commands(self.ms_node, cmd_list3)
        self.assertEqual(self.get_errors(cmd_results), [],
                         "Error in commands")
        self.assertTrue(self.is_std_out_empty(cmd_results),
                        "Error std_out not empty")

        self.log("info", "# 14. Create and Run Plan.")
        # CREATE PLAN
        self.execute_cli_createplan_cmd(self.ms_node)
        # SHOW PLAN
        self.execute_cli_showplan_cmd(self.ms_node)
        # RUN PLAN
        self.execute_cli_runplan_cmd(self.ms_node)
        # Check if plan completed successfully
        completed_successfully = \
            self.wait_for_plan_state(self.ms_node,
                                     test_constants.PLAN_COMPLETE,
                                     self.timeout_mins)
        self.assertTrue(completed_successfully, "Plan was not successful")
