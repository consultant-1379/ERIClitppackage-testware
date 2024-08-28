'''
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     June 2015
@author:    Philip Daly
@summary:   Integration
            Agile: STORY-10123
'''

from litp_generic_test import GenericTest, attr
import test_constants
from redhat_cmd_utils import RHCmdUtils
import os


class Story10123(GenericTest):
    """
    As an ENM user I want a FOSS rsyslog 8.4.1 (or later) installed so I use
    elasticsearch in my 15B deployment.
    """

    def setUp(self):
        """
        Description:
            Runs before every single test.
        Actions:

            1. Call the super class setup method.
            2. Set up variables used in the tests.
        Results:
            The super class prints out diagnostics and variables
            common to all tests are available.
        """
        # 1. Call super class setup
        super(Story10123, self).setUp()
        self.rh_os = RHCmdUtils()
        self.ms_node = self.get_management_node_filename()
        self.rsyslog8_pkg_name = "EXTRrsyslog8"
        self.rsyslog7_pkg_name = "rsyslog7"

        # 2. Set up variables used in the test
        self.ms_node = self.get_management_node_filename()
        self.test_nodes = self.get_managed_node_filenames()

        self.node_urls = self.find(self.ms_node, "/deployments", "node")
        self.node_urls.sort()
        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.ms_node,
                                         "/deployments", "vcs-cluster")[-1]
        self.primary_node = self.get_managed_node_filenames()[0]
        self.rpm_src_dir = (os.path.dirname(os.path.realpath(__file__))
                            + '/test_lsb_rpms/')
        self.item_url = "/software/items"
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR

    def tearDown(self):
        """
        Description:
            Run after each test and performs the following:
        Actions:
            1. Cleanup after test if global results value has been used
            2. Call the superclass teardown method
        Results:
            Items used in the test are cleaned up and the
            super class prints out end test diagnostics
        """
        super(Story10123, self).tearDown()

    def copy_and_import_test_rpms(self, list_of_lsb_rpms):
        """
        Function to copy the list of test rpm's supplied to the Management
        Server and imports them in to the 3pp repository.
        """
        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(self.rpm_src_dir + rpm,
                                                   '/tmp/'))

        copy_success = self.copy_filelist_to(self.ms_node, filelist,
                                             root_copy=True)
        self.assertTrue(copy_success)

        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(self.ms_node, '/tmp/' + rpm,
                                        self.repo_dir_3pp)

    @attr('all', 'revert', 'story10123', 'story10123_tc13')
    def test_13_p_require_multi_pkg_and_versions(self):
        """
        @tms_id: litpcds_10123_tc13
        @tms_requirements_id: LITPCDS-9630
        @tms_title: install package with multiple version property specified
        @tms_description:
            To ensure that the requires property functions as expected when
            supplied with a list of packages.
        @tms_test_steps:
            @step: import 4 packages
            @result: packages imported
            @step: create 4 package items under /software with 2 packages
            specifying the latest prop value
            @result: items created
            @step: inherit package items onto node 1 and node 2 and ms
            @result: packages inherited
            @step: create and run plan
            @result: run executes successfully
            @result: packages installed on nodes and ms
            @result: packages installed in order
            @result: packages replaced
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        list_of_lsb_rpms_specified = [
            'EXTR-lsbwrapper1-2.0.0.rpm',
            'EXTR-lsbwrapper2-3.0.0.rpm',
            'EXTR-lsbwrapper3-1.0.0.rpm',
            'EXTR-lsbwrapper4-2.0.0.rpm',
        ]
        list_of_lsb_rpms = [
            'EXTR-lsbwrapper1-1.0.0.rpm',
            'EXTR-lsbwrapper2-1.0.0.rpm',
            'EXTR-lsbwrapper2-2.0.0.rpm',
            'EXTR-lsbwrapper3-2.0.0.rpm',
            'EXTR-lsbwrapper4-1.0.0.rpm'
        ]
        list_of_lsb_rpms.extend(list_of_lsb_rpms_specified)
        try:
            self.test_nodes.append(self.ms_node)
            for node in self.test_nodes:
                self.copy_file_to(node, self.rpm_src_dir +
                                  'EXTR-lsbwrapper5-3.0.0.rpm', '/tmp')
                self.install_rpm_on_node(node,
                                         '/tmp/EXTR-lsbwrapper5-3.0.0.rpm')

            # 0
            self.copy_and_import_test_rpms(list_of_lsb_rpms)

            # 1
            rpm_details = {"EXTR-lsbwrapper1": "name='EXTR-lsbwrapper1'" \
                           " requires=EXTR-lsbwrapper2,EXTR-lsbwrapper3,"
                                               "EXTR-lsbwrapper4",
                           "EXTR-lsbwrapper2": "name='EXTR-lsbwrapper2' "
                               "version=latest "
                               "requires='EXTR-lsbwrapper3' "
                               "replaces='EXTR-lsbwrapper5-3.0.0-1.noarch'",
                           "EXTR-lsbwrapper3": "name='EXTR-lsbwrapper3' "
                                               "version=1.0.0-1 "
                                               "requires='EXTR-lsbwrapper4'",
                           "EXTR-lsbwrapper4": "name='EXTR-lsbwrapper4'"}

            for rpm_id in rpm_details:
                url = self.item_url + "/{0}".format(rpm_id)
                props = rpm_details[rpm_id]
                self.execute_cli_create_cmd(self.ms_node, url, 'package',
                                            props)

            # 2
            self.node_urls.append('/ms')
            for node_url in self.node_urls:
                for rpm_id in rpm_details:
                    url = node_url + '/items/{0}'.format(rpm_id)
                    src_url = self.item_url + "/{0}".format(rpm_id)
                    self.execute_cli_inherit_cmd(self.ms_node, url, src_url)

            # 3
            self.run_and_check_plan(self.ms_node,
                    expected_plan_state=test_constants.PLAN_COMPLETE,
                    plan_timeout_mins=30)

            self.test_nodes.append(self.ms_node)
            pkg_names = \
            [x.replace('.rpm', '-1.noarch') for x in
             list_of_lsb_rpms_specified]
            for node in self.test_nodes:
                self.assertTrue(self.check_pkgs_installed(node, pkg_names))
                self.assertFalse(self.check_pkgs_installed(node,
                    ['EXTR-lsbwrapper5-3.0.0-1.noarch']))
        finally:
            for rpm in list_of_lsb_rpms:
                self.run_command(self.ms_node,
                                 "/bin/rm -rf {0}/{1}".format(
                                                    self.repo_dir_3pp, rpm),
                                 add_to_cleanup=False, su_root=True)
            _, _, rcode = self.run_command(
            self.ms_node, self.rh_os.get_createrepo_cmd(self.repo_dir_3pp),
            su_root=True
            )
            self.assertEqual(0, rcode)
