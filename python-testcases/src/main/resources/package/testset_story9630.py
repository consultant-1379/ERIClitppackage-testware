"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     May 2015
@author:    Philip Daly, Boyan Mihovski
@summary:   Integration
            Agile: STORY-9630
"""

from litp_generic_test import GenericTest, attr
import test_constants
from redhat_cmd_utils import RHCmdUtils


class Story9630(GenericTest):
    """
    As an ENM user I want a FOSS rsyslog 8.4.1 (or later) installed
    so I use elasticsearch in my 15B deployment.
    """
    # static test data
    RSYSLOG_PKG_NAME = 'EXTRlitprsyslog_CXP9032140'
    RSYSLOG_ELASTICSEARCH = 'EXTRlitprsyslogelasticsearch_CXP9032173'
    RSYSLOG_REPLACE_PGK_NAME = 'rsyslog'
    LIBFASTJSON_PKG_NAME = 'EXTRlitplibfastjson_CXP9037929'
    LIBFASTJSON_REPLACE_PKG_NAME = 'libfastjson'

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
        super(Story9630, self).setUp()
        self.rh_os = RHCmdUtils()

        # 2. Set up variables used in the test
        self.ms_node = self.get_management_node_filename()
        self.test_nodes = self.get_managed_node_filenames()
        self.all_nodes = [self.ms_node] + self.test_nodes
        self.node_urls = self.find(self.ms_node, "/deployments", "node")
        self.node_urls.sort()
        self.node_urls.append('/ms')
        self.packages_url = "/software/items/"

    def tearDown(self):
        """
        Description:
            Run after each test and performs the following:
        Actions:
            1. Cleanup after test if global results value has been
               used
            2. Call the superclass teardown method
        Results:
            Items used in the test are cleaned up and the
            super class prints out end test diagnostics
        """
        # teardown
        super(Story9630, self).tearDown()

    def chk_pkg_and_srvc_status(self, node, pkg=None,
                                service_name='rsyslog',
                                positive=True):
        """
        Checks that the EXTRrsyslog package has been installed
        successfully and that the service is running.
        """
        if not pkg:
            pkg = self.RSYSLOG_PKG_NAME
        found = self.check_pkgs_installed(node, [pkg])
        if positive:
            self.assertTrue(found)
        else:
            self.assertFalse(found)
        stdout, stderr, returnc = \
            self.get_service_status(node, service_name,
                                    assert_running=positive)
        if not positive:
            self.assertNotEqual([], stdout)
            self.assertEqual([], stderr)
            self.assertNotEqual(0, returnc)

    def replaces_property_validation(self):
        """
        Checks that the replaces property accepts only valid string
        values and that the validation error message returned is
        correct.
        """
        validation_pkg_url = "{0}9630_validation".format(self.packages_url)
        validation_pkg_props = "name=validation version=1.1.1 replaces=\"{0}\""
        val_msg = "ValidationError in property: \"replaces\"    " \
                  "Invalid value '{0}'."
        invalid_validation_props = ["%", "*", "&"]
        for invalid_prop in invalid_validation_props:
            stdout, stderr, returnc = (self.execute_cli_create_cmd
                                       (self.ms_node, validation_pkg_url,
                                        'package', validation_pkg_props.format(
                                           invalid_prop),
                                        expect_positive=False))
            self.assertEqual([], stdout)
            self.assertNotEqual([], stderr)
            self.assertNotEqual(0, returnc)

            self.assertTrue(self.is_text_in_list(val_msg.format(invalid_prop),
                                                 stderr))

    @attr('all', 'non-revert', 'story9630', 'story9630_tc02',)
    def test_02_p_replace_rsyslog_on_ms_and_nodes(self):
        """
        @tms_id: litpcds_9630_tc02
        @tms_requirements_id: LITPCDS-9630
        @tms_title: Replace rsyslog on ms and nodes
        @tms_description: Creates an rsyslog package and tests that
            an attempt to update the read only 'replaces' property of
             a package will not be successful.
        @tms_test_steps:
        @step: Check the validation of the replaces property
        @result: Replaces property is successfully validated
        @step: Check that a package cannot replace itself
        @result: A package can't be replaced by itself;
                 error message is returned
        @step: Create a package object in the LITP model for
            EXTRlitprsyslogelasticsearch with property
            replaces=rsyslog
        @result: The package item is created
        @step: Create a package object in the LITP model for
               EXTRlitplibfastjson on which rsyslog is dependant
        @result: The package item is created
        @step: Inherit these package objects to the management server
               and each of the peer nodes.
        @result: The objects are inherited.
        @step: Deploy the configuration.
        @result: Configuration is deployed
        @step: Verify that the EXTRlitprsyslog has been installed
               successfully on the ms and the peer nodes and that the
               service is running and added to chkconfig.
        @result: EXTRlitprsyslog is verified as being successfully
                 installed on the ms and peer nodes
        @result: The service is running
        @step: Attempt to update the 'replaces' property with a new
               value
        @result: The update is not successful
        @result: InvalidRequestError message is returned
        @result: Error message details;
            Unable to modify readonly property: replaces'
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        self.log('info', "0 Check validation of 'replaces' property.")
        self.replaces_property_validation()
        self.log('info', "0.5 (TORF-226381) MANUALLY REMOVE RSYSLOG FROM "
                         "NODES TO CHECK PACKAGE REMOVAL IDEMPOTENCE")
        yum_cmd = self.rh_os.get_yum_remove_cmd(['rsyslog.x86_64'])
        for test_node in self.all_nodes:
            self.run_command(test_node, yum_cmd,
                             add_to_cleanup=False, su_root=True)

        self.log('info', "1. Verify that a package cannot replace itself.")
        replace_pkg_url = '{0}{1}'.format(self.packages_url,
                                          self.RSYSLOG_REPLACE_PGK_NAME)
        replace_pkg_props = 'name={0} replaces={0}'. \
            format(self.RSYSLOG_REPLACE_PGK_NAME)
        err_msg_self = \
            'Replacement of a modelled package "{0}" with "{0}" is ' \
            'not allowed.'.format(self.RSYSLOG_REPLACE_PGK_NAME)
        stdout, stderr, returnc = (
            self.execute_cli_create_cmd(self.ms_node, replace_pkg_url,
                                        'package', replace_pkg_props,
                                        expect_positive=False,
                                        add_to_cleanup=False))
        self.assertEqual([], stdout)
        self.assertNotEqual([], stderr)
        self.assertNotEqual(0, returnc)
        self.assertTrue(self.is_text_in_list(err_msg_self, stderr))

        self.log('info', "Create a package item replacing existing rsyslog "
                         "package.")
        # rsyslog depends on libfastjson, so we need to create it as well
        pckg_dict = {"rsyslog": {"name": self.RSYSLOG_ELASTICSEARCH,
                                 "url": replace_pkg_url,
                                 "replaces": self.RSYSLOG_REPLACE_PGK_NAME},
                     "libfastjson": {"name": self.LIBFASTJSON_PKG_NAME,
                                     "url": '{0}{1}'.format(self.packages_url,
                                            self.LIBFASTJSON_REPLACE_PKG_NAME),
                                     "replaces":
                                         self.LIBFASTJSON_REPLACE_PKG_NAME}
                     }
        for _, options in pckg_dict.items():
            replace_pkg_props = 'name={0} replaces={1}'.format(options["name"],
                                                       options["replaces"])
            stdout, stderr, returnc = (
                self.execute_cli_create_cmd(self.ms_node, options["url"],
                                            'package', replace_pkg_props,
                                            add_to_cleanup=False))
            self.assertEqual([], stdout)
            self.assertEqual([], stderr)
            self.assertEqual(0, returnc)

            self.log('info', "2. Inherit the package to MS and nodes, "
                             "and apply changes")
            for _, url in enumerate(self.node_urls):
                stdout, stderr, returnc = (
                    self.execute_cli_inherit_cmd(self.ms_node,
                                         '{0}/items/{1}'.format(url,
                                                 options["replaces"]),
                                                 options["url"],
                                                 add_to_cleanup=False))
                self.assertEqual([], stdout)
                self.assertEqual([], stderr)
                self.assertEqual(0, returnc)

        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)
        self.wait_for_plan_state(self.ms_node, test_constants.PLAN_COMPLETE)

        self.log('info', "3.  Check that EXTRlitprsyslog package is installed "
                         "successfully.")
        for node in self.all_nodes:
            self.chk_pkg_and_srvc_status(node)

            self.log('info', "Check that the rsyslog process auto-start per "
                             "nodes is active")
            stdout, _, _ = self.get_service_status(node,
                                                self.RSYSLOG_REPLACE_PGK_NAME)
            self.assertTrue(self.is_text_in_list("active", stdout))

        self.log('info', "4. Verify that the 'replaces' package property is "
                         "readonly.")
        self.backup_path_props(self.ms_node, replace_pkg_url)
        stdout, stderr, returnc = \
            self.execute_cli_update_cmd(self.ms_node, replace_pkg_url,
                                        'replaces=invalid',
                                        expect_positive=False)
        self.assertEqual([], stdout)
        self.assertNotEqual([], stderr)
        self.assertNotEqual(0, returnc)
        err_msg_read_only = 'InvalidRequestError in property: ' \
                '"replaces"    Unable to modify readonly property: replaces'
        self.assertTrue(self.is_text_in_list(err_msg_read_only, stderr))
