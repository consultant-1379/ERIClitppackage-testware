"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     September 2018
@author:    Paul Chambers
@summary:   Integration test for story 271865. As a LITP User I want a node
            reboot task to be marked as successful as soon as puppet starts
            running on that node
"""
import os
from litp_generic_test import GenericTest, attr
import test_constants
from redhat_cmd_utils import RHCmdUtils
import time


class Story271865(GenericTest):
    """
    TORF-271865
    LITP marks the node reboot as successful as soon as puppet on that node is
    running without waiting for completion of the Puppet catalog run.
    """

    def setUp(self):
        """ Setup variables for every test """
        super(Story271865, self).setUp()
        self.ms_node = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.primary_node_url = self.get_node_url_from_filename(
            self.ms_node, self.primary_node)
        self.rpm_src_dir = \
            "{0}/9532_9659_rpms/".format(
                os.path.dirname(os.path.realpath(__file__)))
        # Repo where rpms will be installed
        self.repo_dir_3pp = \
            test_constants.PP_PKG_REPO_DIR
        # ==================================================
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # ===================================================
        # List of rpms required for this test
        self.dummy_lsb_rpms = [
            "popcorn-kernel-1.0-1.el6.x86_64.rpm",
            "popcorn-kernel-1.1-1.el6.x86_64.rpm",
        ]
        self.rpm_remote_dir = '/tmp/'
        self.rhcmd = RHCmdUtils()
        self.software_items_path = \
            self.find(self.ms_node, '/software',
                      'collection-of-software-item')[0]
        self.software_pkg = '{0}/pkg1'.format(self.software_items_path)
        self.pn_ip = self.get_node_att(self.primary_node, 'ipv4')

    def tearDown(self):
        """ Called after every test"""
        super(Story271865, self).tearDown()
        self.run_command(self.ms_node,
                         '/bin/rm -f {0}{1}'.format(self.repo_dir_3pp,
                                               "/popcorn-kernel-1.*"),
                         su_root=True)
        cmd = self.rhcmd.get_createrepo_cmd(self.repo_dir_3pp, ".", False)
        self.run_command(self.ms_node, cmd)

    # ==================================================
    # This test (test_04_p_upgrade_with_reboot_node_check)
    # has been deemed not fit for purpose and is being removed
    # from the KGB until it is refactored as a part of TORF-538931:
    # https://jira-oss.seli.wh.rnd.internal.ericsson.com/browse/TORF-538931
    # ==================================================
    @attr('pre-reg', 'revert', 'story271865', '271865_04')
    def test_04_p_upgrade_with_reboot_node_check(self):
        """
        @tms_id: litpcds_271865_tc04
        @tms_requirements_id: TORF-271865
        @tms_title: Reboot task successful without catalogue run
        @tms_description:
            This test will verify that the reboot node phase of a plan will be
            marked as a success as soon as puppet is running on that node
            without waiting for completion of the Puppet catalog run.
        @tms_test_steps:
            @step: Importing dummy test RPMS to MS.
            @result: dummy test RPMS imported to MS.
            @step: Move dummy rpms to MS
            @result: Dummy test rpms moved to MS
            @step: create dummy package called another-kernel
            @result: dummy package called another-kernel created
            @step: Inherit dummy package into node 1 items
            @result: dummy package into node 1 items inherited
            @step: create and run plan
            @result: plan created and ran
            @step: Import updated version of dummy package
            @result: Imported updated version of dummy package
            @step: Issue upgrade command.
            @result: Upgrade command issued
            @step: create plan
            @result: plan created
            @step: Find phase with node reboot
            @result: Phase with Node reboot found.
            @step: run plan
            @result: plan ran
            @step: wait till node reboot phase
            @result: plan monitored till reboot phase
            @step: Wait for puppet to start running
            @result: The node was watched until puppet started running.
            @step: Watch node reboot phase till it is labeled successful.
            @result: reboot node phase was watched until phase was marked
                    successful.
            @step: Compare reboot time to puppet times
            @result: Time between puppet starting and the nodes successful
                    reboot was compared.
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        self.log("info", "Step 1. Copy RPMs to Management Server")
        files = []

        for rpm in self.dummy_lsb_rpms:
            rpms_remote_path = "{0}".format(self.rpm_remote_dir, rpm)
            files.append(self.get_filelist_dict(
                                            "{0}{1}".format(self.rpm_src_dir,
                                                            rpm),
                                            rpms_remote_path))

        self.copy_filelist_to(self.ms_node, files,
                              add_to_cleanup=False, root_copy=True)

        self.execute_cli_import_cmd(self.ms_node,
                                    "{0}{1}".format(self.rpm_remote_dir,
                                                    self.dummy_lsb_rpms[0]),
                                    self.repo_dir_3pp)

        self.log("info", "Step 2. create dummy package called another-kernel")

        self.execute_cli_create_cmd(self.ms_node,
                                    self.software_pkg,
                                    "package",
                                    "name=popcorn-kernel")

        self.log("info", "Step 3. Inherit dummy package into node 1 items")

        self.execute_cli_inherit_cmd(self.ms_node,
                                     "{0}/items/pkg1".format(
                                         self.primary_node_url),
                                     self.software_pkg)

        self.log("info", "Step 4. create and run plan")
        self.run_and_check_plan(self.ms_node,
                                test_constants.PLAN_COMPLETE,
                                6)

        self.log("info", "Step 5. import dummy TO package")
        self.execute_cli_import_cmd(self.ms_node,
                                    "{0}{1}".format(self.rpm_remote_dir,
                                                    self.dummy_lsb_rpms[1]),
                                    self.repo_dir_3pp)

        self.log("info", "Step 6. upgrade")
        self.execute_cli_upgrade_cmd(self.ms_node, self.primary_node_url)

        self.log("info", "Step 7. create plan")

        self.execute_cli_createplan_cmd(self.ms_node)

        self.execute_cli_showplan_cmd(self.ms_node)

        self.log("info", "Step 8. run second plan")

        try:
            self.execute_cli_runplan_cmd(self.ms_node)

            self.log("info", "Step 9. wait till node reboot phase")

            self.wait_for_task_state(self.ms_node, "Reboot node",
                                     expected_state=test_constants.
                                     PLAN_TASKS_RUNNING)

            self.wait_for_ping(self.pn_ip, False)

            self.log("info", "Step 10. wait for puppet to be running")
            puppet_success_time = timeout = 0
            puppet_running = waiting_for_node = False

            while puppet_running is not True and timeout < 300:
                while waiting_for_node is False:
                    waiting_for_node = self.wait_for_node_up(self.primary_node)

                puppet_status, _, _ = self.get_service_status(
                                                        self.primary_node,
                                                        "puppet",
                                                        assert_running=False)

                puppet_running = self.is_text_in_list("active",
                                                      puppet_status)

                if puppet_running:
                    puppet_success_time = time.time()
                    break
                timeout += 1
                time.sleep(2)

            self.log("info", "Step 11. wait for node reboot phase to be "
                             "labeled successful")
            reboot_success_time, time_diff = 0, 0

            if self.get_current_plan_state(self.ms_node) == \
                    test_constants.PLAN_COMPLETE:
                reboot_success_time = time.time()

            elif self.wait_for_task_state(self.ms_node, "Reboot node",
                                          test_constants.PLAN_TASKS_SUCCESS,
                                          seconds_increment=1):
                reboot_success_time = time.time()

                self.execute_cli_showplan_cmd(self.ms_node)

            self.log("info", "Step 12. compare reboot time to puppet times. ")
            if reboot_success_time and puppet_success_time:
                time_diff = reboot_success_time - puppet_success_time

                self.assertTrue(time_diff < 40, "Greater then 40 second gap "
                                                "between puppet running and"
                                                "reboot node task completion.")
            else:
                self.log("info",
                         "Invalid timers: reboot-success-time {0} and/or "
                         "puppet-success-time {1}".format(
                             reboot_success_time, puppet_success_time))
                self.assertTrue(False, "Test failure")

            self.log("info",
                     "Reboot success time: {0}, puppet success time: {1}, "
                     "difference: {2}, threshold: 40".format(
                         reboot_success_time, puppet_success_time, time_diff))

        finally:
            self.assertTrue(self.wait_for_plan_state(
                self.ms_node,
                test_constants.PLAN_COMPLETE
            ))
