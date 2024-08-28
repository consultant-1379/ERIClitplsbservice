##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

import mock
import unittest
import itertools
from mock import MagicMock

from service_plugin.serviceplugin import ServicePlugin, ServiceValidator

from litp.extensions.core_extension import CoreExtension
from litp.core.model_manager import ModelManager
from litp.core.plugin_manager import PluginManager
from litp.core.plugin_context_api import PluginApiContext
from package_extension.package_extension import PackageExtension
from vcs_extension.vcs_extension import VcsExtension
from volmgr_extension.volmgr_extension import VolMgrExtension
from network_extension.network_extension import NetworkExtension

class TestServicePlugin(unittest.TestCase):

    dependent_apis = [
        PackageExtension,
        VcsExtension,
        VolMgrExtension,
        NetworkExtension
    ]

    def setUp(self):
        """
        Construct a model, sufficient for test cases
        that you wish to implement in this suite.
        """
        #import pdb; pdb.set_trace()
        self.model = ModelManager()
        self.api = PluginApiContext(self.model)
        self.plugin_manager = PluginManager(self.model)
        # Use add_property_types to add property types defined in
        # model extenstions
        # For example, from CoreExtensions (recommended)
        self.plugin_manager.add_property_types(
            CoreExtension().define_property_types())
        # Use add_item_types to add item types defined in
        # model extensions
        # For example, from CoreExtensions
        self.plugin_manager.add_item_types(
            CoreExtension().define_item_types())
        # Add default minimal model (which creates '/' root item)
        self.plugin_manager.add_default_model()

        # Instantiate your plugin and register with PluginManager
        self.plugin = ServicePlugin()
        self.validator = ServiceValidator(self.api)
        self.register_dependent_apis()

    def register_dependent_apis(self):
        for Ext in self.dependent_apis:
            ext = Ext()
            self.plugin_manager.add_property_types(ext.define_property_types())
            self.plugin_manager.add_item_types(ext.define_item_types())


    def setup_model(self):
        # Use ModelManager.crete_item and ModelManager.create_inherited
        # to create and inherit items in the model.
        self.model.create_item('ms', '/ms', hostname='ms1')
        self.model.create_item('ms', '/ms/services')
        soft = self.model.create_item('software-item', '/software/items')
        it = self.model.create_item('software-item', '/software/items')
        self.model.create_item('deployment', '/deployments/d1')
        self.model.create_item('cluster', '/deployments/d1/clusters/c1')
        self.node1 = self.model.create_item("node",
            '/deployments/d1/clusters/c1/nodes/n1', hostname="node1")
        #self.node1 = self.create_item("node",
        #    '/deployments/d1/clusters/c1/nodes/n2/services', hostname="special")

    def setup_apache_model(self):
        apache = self.create_item('service', '/software/services/httpd',
             service_name="httpd",
             start_command="/etc/init.d/httpd start",
             stop_command="/etc/init.d/httpd stop",
             status_command="/etc/init.d/httpd status"
        )
        htt = self.create_item('package', '/software/items/httpd',
                               name="httpd")
        self.model.create_inherited("/software/items/httpd",
                                    "/software/services/httpd/packages/httpd")
        inh = self.model.create_inherited(
            "/software/services/httpd",
            "/deployments/d1/clusters/c1/nodes/n1/services/httpd",
        )
        return apache, inh

    def setup_sentinel_model(self):
        serv = self.create_item('service', '/software/services/sentinel',
            service_name="sentinel",
            start_command="/etc/init.d/sentinel start",
            stop_command="/etc/init.d/sentinel stop",
            status_command="/etc/init.d/sentinel status"
        )
        sent = self.create_item('package', '/software/items/sentinel',
                                      name="sentinel")
        self.create_item('service', '/ms/services/sentinel',
            service_name="sentinel",
            start_command="/etc/init.d/sentinel start",
            stop_command="/etc/init.d/sentinel stop",
            status_command="/etc/init.d/sentinel status"
        )
        inher = self.model.create_inherited(
            "/software/items/sentinel",
            "/ms/items/sentinel",
        )
        self.model.create_inherited(
            "/software/items/sentinel",
            "/software/services/sentinel/packages/sentinel",
        )
        serv_inh = self.model.create_inherited(
            "/software/services/sentinel",
            "/deployments/d1/clusters/c1/nodes/n1/services/sentinel",
        )
        return serv, serv_inh

    def create_item(self, *args, **kwargs):
        item = self.model.create_item(*args, **kwargs)
        if isinstance(item, list):
            raise Exception(". ".join([str(e) for e in item]))
        return item

    def test_validate_model(self):
        self.setup_model()
        errors = self.plugin.validate_model(self.api)
        self.assertEqual(0, len(errors))

    def test_validate_service_allowed(self):
        self.setup_model()
        self.setup_sentinel_model()
        errors = self.validator.validate_not_allowed_services()
        self.assertEqual(0, len(errors))

    def test_validate_duplicate_services(self):
        self.setup_model()
        self.setup_apache_model()
        self.create_item('service', '/ms/services/foo',
            service_name="foo"
        )
        item = self.create_item('service', '/ms/services/bar',
            service_name="foo"
        )
        item2 = self.create_item('service', '/ms/services/other',
            service_name="foo"
        )

        errors = self.validator.validate_duplicate_services()

        err_perms = ['Duplicate service "foo" defined on paths: "%s","%s"'
                     % spp for spp in
                     [tuple('/ms/services/%s' % (s,) for s in sp) for sp in
                      itertools.permutations(('bar', 'foo', 'other'), 2)]]

        self.assertEqual(1, len(errors))
        self.assertTrue(errors[0].error_message in err_perms)

        item.set_for_removal()
        item2.set_for_removal()
        errors = self.validator.validate_duplicate_services()
        self.assertEqual(0, len(errors))

    def test_validate_service_not_allowed(self):
        self.setup_model()
        self.setup_apache_model()
        item = self.create_item('service', '/ms/services/httpd',
            service_name="httpd",
            start_command="/etc/init.d/httpd start",
            stop_command="/etc/init.d/httpd stop",
            status_command="/etc/init.d/httpd status"
        )
        errors = self.validator.validate_not_allowed_services()
        self.assertEqual(1, len(errors))
        item.set_for_removal()
        errors = self.validator.validate_not_allowed_services()
        self.assertEqual(0, len(errors))

    def test_validate_over_vcs(self):
        self.setup_model()
        self.create_item(
            'vcs-clustered-service',
            '/deployments/d1/clusters/c1/services/apachecs',
            active=2,
            standby=0,
            name='vcs1',
            online_timeout=45,
            node_list='n1,n2'
        )
        self.create_item('service', '/software/services/service1',
                         service_name='httpd')
        self.model.create_inherited("/software/services/service1",
            "/deployments/d1/clusters/c1/services/apachecs/"
            "applications/service1")
        item, inh = self.setup_apache_model()
        errors = self.validator.validate_over_vcs()
        self.assertEqual(1, len(errors))
        item.set_for_removal()
        inh.set_for_removal()
        errors = self.validator.validate_over_vcs()
        self.assertEqual(0, len(errors))

    def test_create_configuration(self):
        self.setup_model()
        item, inh = self.setup_sentinel_model()
        tasks = self.plugin.create_configuration(self.api)
        self.assertEqual(2, len(tasks))
        item.set_for_removal()
        inh.set_for_removal()
        tasks = self.plugin.create_configuration(self.api)
        self.assertEqual(2, len(tasks))

    def test_validate_vm_service(self):
        ms = mock.MagicMock()
        ms.item_type_id = 'ms'
        ms.hostname = 'ms1'
        service = mock.MagicMock()
        service.item_type_id = 'vm-service'
        service.service_name = 'fmmed'
        service.is_initial = lambda: True
        service.is_updated = lambda: False
        def query_mock(query):
            if query == 'node':
                return []
            elif query == 'ms':
                return [ms]
            elif query == 'service':
                return [service]
            elif query == "package":
                return []
            else:
                self.fail('Item type unexpected. %s' % query)
        ms.query = query_mock
        self.api.query = query_mock
        tasks = self.plugin.create_configuration(self.api)
        self.assertEqual(list, type(tasks))
        self.assertEqual(1, len(tasks))
        self.assertEqual(set([('libvirt::copy_file', 'ms1imagefmmed'), service, ('libvirt::write_file', 'ms1userdatafmmed'), ('libvirt::write_file', 'ms1metadatafmmed'), ('libvirt::install_adaptor', 'ms_libvirt_adaptor_install'), ('libvirt::write_file', 'ms1configfmmed')]), tasks[0].requires)
        self.assertEqual('false', tasks[0].kwargs['enable'])
        self.assertEqual('Ensure service "%s" is running on node "%s"' %
                        (service.service_name, ms.hostname),
                        tasks[0].description)

    def test_service_config_task(self):
        ms = mock.MagicMock()
        ms.item_type_id = 'ms'
        ms.hostname = 'ms1'
        service = mock.MagicMock()
        service.item_type_id = 'service'
        service.service_name = 'fmmed'
        service.start_command = None
        service.stop_command = None
        service.status_command = None

        task = self.plugin._service_config_task(ms, service, "foo", "fee", "faa")
        self.assertEqual('foo', task.description)
        self.assertEqual(task.kwargs, {'enable': 'faa', 'ensure': 'fee', 'name': 'fmmed'})

        service.start_command = "start"
        service.stop_command = "stop"
        service.status_command = "status"
        task = self.plugin._service_config_task(ms, service, "foo", "fee", "faa")
        self.assertEqual(task.kwargs, {'status': 'status', 'start': 'start', 'enable': 'faa',
                                       'ensure': 'fee', 'name': 'fmmed', 'stop': 'stop'})

    def test_service_config_task_vm_service(self):
        ms = mock.MagicMock()
        ms.item_type_id = 'ms'
        ms.hostname = 'ms1'
        service = mock.MagicMock()
        service.item_type_id = 'vm-service'
        service.service_name = 'fmmed'
        service.start_command = None
        service.stop_command = None
        service.status_command = None

        task = self.plugin._service_config_task(ms, service, "foo", "fee", "faa")
        self.assertEqual('foo', task.description)
        self.assertEqual(task.kwargs,  {'status': '/opt/ericsson/nms/litp/lib/litpmnlibvirt/litp_libvirt_adaptor.py fmmed status',
                                        'enable': 'faa', 'name': 'fmmed', 'hasstatus': 'false',
                                        'stop': 'systemctl stop fmmed', 'start': 'systemctl restart fmmed',
                                        'ensure': 'fee', 'provider': 'init'})

        service.start_command = "start"
        service.stop_command = "stop"
        service.status_command = "status"
        task = self.plugin._service_config_task(ms, service, "foo", "fee", "faa")
        self.assertEqual(task.kwargs, {'status': 'status', 'enable': 'faa', 'name': 'fmmed',
                                       'hasstatus': 'false', 'stop': 'stop', 'start': 'start',
                                       'ensure': 'fee', 'provider': 'init'})

    # TORF-603456
    def test_esmon_vm_service_in_ms_redeploy_plan(self):

        nservice = MagicMock(item_type_id = 'service',
                             is_initial = lambda: True,
                             is_updated = lambda: False,
                             service_name = 'noddy')

        mservice = MagicMock(item_type_id = 'vm-service',
                             is_initial = lambda: True,
                             is_updated = lambda: False,
                             service_name = 'esmon')

        upgrade = MagicMock(redeploy_ms='false')

        def node_mock_query(itemtype):
            if 'upgrade' == itemtype:
                return [upgrade]
            elif 'service' == itemtype:
                return [nservice]
            else:
                return []

        def ms_mock_query(itemtype):
            if 'service' == itemtype:
                return [mservice]
            else:
                return []

        node = MagicMock(query=node_mock_query,
                         hostname = 'svc-1',
                         item_type_id = 'node',
                         is_initial = lambda: True,
                         is_updated = lambda: False)

        ms = MagicMock(query=ms_mock_query,
                       hostname = 'ms-1',
                       item_type_id = 'ms',
                       is_initial = lambda: True,
                       is_updated = lambda: False)

        def pac_mock_query(itemtype):
            if 'node' == itemtype:
                return [node]
            elif 'ms' == itemtype:
                return [ms]
            else:
                return []

        pac = MagicMock(query=pac_mock_query)

        tasks = self.plugin.create_configuration(pac)

        self.assertEqual(2, len(tasks))
        node_task = tasks[0]
        ms_task = tasks[1]
        template = 'Ensure service "{0}" is running on node "{1}"'
        expected1 = template.format(nservice.service_name, node.hostname)
        expected2 = template.format(mservice.service_name, ms.hostname)

        self.assertEqual(expected1, node_task.description)
        self.assertEqual(expected2, ms_task.description)

        # ---
        upgrade.redeploy_ms = 'true'

        tasks = self.plugin.create_configuration(pac)

        self.assertEqual(1, len(tasks))
        node_task = tasks[0]
        self.assertEqual(expected1, node_task.description)

        # ---

        mservice.service_name = 'not-esmon'
        tasks = self.plugin.create_configuration(pac)

        self.assertEqual(2, len(tasks))
        node_task = tasks[0]
        ms_task = tasks[1]
        new_expected2 = template.format(mservice.service_name, ms.hostname)
        self.assertEqual(expected1, node_task.description)
        self.assertEqual(new_expected2, ms_task.description)
