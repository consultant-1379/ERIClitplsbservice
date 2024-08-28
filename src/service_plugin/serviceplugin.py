##############################################################################
# COPYRIGHT Ericsson AB 2014
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

from litp.core.plugin import Plugin
from litp.core.validators import ValidationError
from litp.core.task import ConfigTask
from litp.core.litp_logging import LitpLogger
from litp.extensions.core_extension import CoreExtension

log = LitpLogger()


def new_error(item, msg):
    return ValidationError(item_path=item.get_vpath(), error_message=msg)


def debug(preamble, msg):
    log.trace.debug("%s: %s" % (preamble, msg))


class ServiceValidator(object):
    """ This class contains all the validators for the ServicePlugin.
    """

    DISALLOWED_SERVICES_FOR_MS = [
        'litpd', 'rabbitmq-server', 'httpd', 'puppetmaster'
    ] + CoreExtension.DISALLOWED_SERVICES_GLOBAL

    DISALLOWED_SERVICES_FOR_NODES = ['sshd',
    ] + CoreExtension.DISALLOWED_SERVICES_GLOBAL

    def __init__(self, plugin_api_context):
        """ Sets the plugin_api_context for use in every validator in this
        class.
        """
        self.api = plugin_api_context

    def validate_duplicate_services(self):
        """ Checks whether has duplicated services names in the model for the
        same node.
        """
        errors = []
        msg_format = 'Duplicate service "%s" defined on path: %s'
        msg_format_plr = 'Duplicate service "%s" defined on paths: %s'
        nodes_paths = []
        for node in self.api.query('node') + self.api.query('ms'):
            paths = {}
            for service in node.query('service'):
                if service.is_for_removal() or \
                   service.item_type_id != 'service':
                    # ignore for removal ones
                    continue
                if service.service_name not in paths:
                    paths[service.service_name] = {'service': service,
                                                   'paths': []}
                    continue
                paths[service.service_name]['paths'].append(service)
            nodes_paths.append(paths)

        for node_paths in nodes_paths:
            for service_name, dup in node_paths.items():
                if not dup['paths']:
                    continue
                form = msg_format_plr if len(dup['paths']) > 1 else msg_format
                msg = form % (service_name,
                            ','.join(['"%s"' % s.vpath for s in dup['paths']]))
                errors.append(new_error(dup['service'], msg))
        return errors

    def validate_not_allowed_services(self):
        """ Based on DISALLOWED_SERVICES_* definition, this method checks
        whether the services to be applied are valid or not.
        """
        preamble = '.validate_not_allowed_services'
        errors = []
        nodes_disallowed = [
            (self.api.query('ms'), self.DISALLOWED_SERVICES_FOR_MS),
            (self.api.query('node'), self.DISALLOWED_SERVICES_FOR_NODES),
        ]
        msg_format = CoreExtension.DISALLOWED_SERVICES_VALIDATION_MESSAGE
        for nodes, disallowed in nodes_disallowed:
            for node in nodes:
                for service in node.query('service'):
                    if service.item_type_id != 'service' or \
                       service.is_for_removal():
                        continue
                    if service.service_name in disallowed:
                        msg = msg_format % service.service_name
                        debug(preamble, msg)
                        errors.append(new_error(service, msg))
        return errors

    def validate_over_vcs(self):
        """ Checks whether services to be applied are managed by VCS plugin.
        """
        errors = []
        vcs_services = []
        preamble = '.validate_over_vcs'
        msg_format = 'Service "%s" is managed by the VCS plugin'
        for cluster in self.api.query('cluster'):
            for service in cluster.services:
                if service.item_type_id != 'vcs-clustered-service':
                    continue
                vcs_services += [a.service_name for a in service.applications]
        if not vcs_services:
            return []
        for node in self.api.query('node'):
            for service in node.query('service'):
                if service.item_type_id != 'service' or service.is_applied() \
                   or service.is_for_removal():
                    continue
                if service.service_name in vcs_services:
                    msg = msg_format % service.service_name
                    debug(preamble, msg)
                    errors.append(new_error(service, msg))
        return errors

    def validate(self):
        """ Executes every method of this class that starts with "validate_"
        and retrieves every list of errors.
        """
        errors = []
        for attr in dir(self):
            if attr.startswith('validate_'):
                errors += getattr(self, attr)()
        return errors


class ServicePlugin(Plugin):
    """
    The LITP LSB service plugin enables you to ensure that system services
    are running on either the management server or on peer nodes.
    """

    def validate_model(self, plugin_api_context):
        """
        Validates LSB service model integrity. Validation rules enforced by
        this plugin are:

        - Rules for management server :

          - The ``service_name`` cannot be any of the following services:
            litpd, rabbitmq-server, httpd, puppetmaster. This is because they
            are managed by LITP. In this case, LITP will fail to create the
            plan.

        - Rules common to the management server and peer nodes:

          - The item of type ``service`` must be defined with a
            ``service_name`` which is identical to the name of the service
            defined in the operating system.

          - The ``service_name`` cannot be any of the following services:
            puppet, mcollective, sshd, network. This is because they are
            managed by LITP. In this case, it will fail at service item type
            creation.

          - The item of type ``service`` may be defined with \
            a ``start_command`` as the command that provides the action to
            start the service.

          - The item of type ``service`` may be defined with \
            a ``stop_command`` as the command that provides the action to
            stop the service.

          - The item of type ``service`` may be defined with \
            a ``status_command`` as the command that provides the action to
            show the status of the service.

        """
        validator = ServiceValidator(plugin_api_context)
        return validator.validate()

    def create_configuration(self, plugin_api_context):
        """
        The following are examples of LSB service plugin usage. Note that
        the package must also be created and inherited as a dependency of the
        service. The Package plugin is responsible for installing the package
        on the management server or the peer nodes. For more information about
        the manipulation of packages by LITP, refer to the Package plugin
        documentation.

        *Example CLI to ensure that the "sentinel" service is running on the
        node:*

        .. code-block:: bash

            litp create -t service -p /software/services/sentinel -o \
service_name=sentinel
            litp create -t package -p /software/items/sentinel -o \
name=EXTRlitpsentinellicensemanager_CXP9031488.x86_64
            litp inherit -p /deployments/d1/clusters/c1/nodes/n1/services/\
sentinel -s /software/services/sentinel
            litp inherit -p /software/services/sentinel/packages/sentinel -s \
/software/items/sentinel

        *Example CLI to ensure that the "sentinel" service is NOT running on
        the node:*

        .. code-block:: bash

            litp remove -p /deployments/d1/clusters/c1/nodes/n1/services/\
sentinel
            litp remove -p /software/services/sentinel

        Note that the package is also removed from the node as it is a
        dependency of the sentinel service. The Package plugin is responsible
        for removing it.

        *Example XML to ensure that the "sentinel" service is running on
        the node:*

        .. code-block:: xml

            <?xml version='1.0' encoding='utf-8'?>
            <litp:service xmlns:xsi="http://www.w3.org/2001/XMLSchema-\
instance" xmlns:litp="http://www.ericsson.com/litp" xsi:schemaLocation=\
"http://www.ericsson.com/litp litp-xml-schema/litp.xsd" id="crond">
              <cleanup_command>/bin/true</cleanup_command>
              <service_name>crond</service_name>
              <litp:service-packages-collection id="packages">
                <litp:package-inherit source_path="/software/items/crontabs" \
id="crontabs"/>
              </litp:service-packages-collection>
            </litp:service>

            <?xml version='1.0' encoding='utf-8'?>
            <litp:package xmlns:xsi="http://www.w3.org/2001/XMLSchema-\
instance" xmlns:litp="http://www.ericsson.com/litp" xsi:schemaLocation=\
"http://www.ericsson.com/litp litp-xml-schema/litp.xsd" id="crontabs">
              <epoch>0</epoch>
              <name>crontabs.noarch</name>
            </litp:package>

            <?xml version='1.0' encoding='utf-8'?>
            <litp:service-inherit xmlns:xsi="http://www.w3.org/2001/XMLSchema\
-instance" xmlns:litp="http://www.ericsson.com/litp" xsi:schemaLocation="\
http://www.ericsson.com/litp litp-xml-schema/litp.xsd" id="crond" source_path=\
"/software/services/crond">
              <litp:service-packages-collection-inherit source_path="/\
software/services/crond/packages" id="packages">
                <litp:package-inherit source_path="/software/services/crond/\
packages/crontabs" id="crontabs"/>
              </litp:service-packages-collection-inherit>
            </litp:service-inherit>

        For more information, see "Deploy a Service on a Node" \
from :ref:`LITP References <litp-references>`.

        """
        redeploy_ms = any([True for node in plugin_api_context.query('node')
                           for upgrd_item in node.query('upgrade')
                     if getattr(upgrd_item, 'redeploy_ms', 'false') == 'true'])

        tasks = []
        all_nodes = plugin_api_context.query('node') + \
                    plugin_api_context.query('ms')
        for node in all_nodes:
            for service in node.query('service'):
                if service.item_type_id == 'service' or \
                  (service.item_type_id == 'vm-service' and
                      node.item_type_id == 'ms'):

                    if (node.is_ms() and redeploy_ms and
                        'vm-service' == service.item_type_id and
                        'esmon' == service.service_name):
                        continue

                    if service.is_initial() or service.is_updated():
                        desc = 'Ensure service "%s" is running ' \
                                'on node "%s"' % \
                                (service.service_name, node.hostname)
                        enable = ('false'
                                  if service.item_type_id == 'vm-service'
                                  else 'true')
                        task = self._service_config_task(node, service,
                            desc, ensure='running', enable=enable)
                        for package in service.packages:
                            task.requires.add(package)
                        ms_packages = node.query('package')
                        for package in ms_packages:
                            if package.name == service.service_name:
                                task.requires.add(package)
                        if service.item_type_id == 'vm-service':
                            task.requires.add(service)
                        if (service.item_type_id == 'vm-service' and
                                node.item_type_id == 'ms'):
                            hostname = node.hostname
                            ser_name = service.service_name
                            task.requires.add(("libvirt::install_adaptor",
                                              "ms_libvirt_adaptor_install"))
                            task.requires.add(("libvirt::copy_file",
                                              hostname + "image" + ser_name))
                            task.requires.add(("libvirt::write_file",
                                              hostname + "config" + ser_name))
                            task.requires.add(("libvirt::write_file",
                                              hostname + "metadata"
                                               + ser_name))
                            task.requires.add(("libvirt::write_file",
                                              hostname + "userdata"
                                               + ser_name))
                        tasks.append(task)
                    elif service.is_for_removal():
                        desc = 'Stop service "%s" on node "%s"' % \
                            (service.service_name, node.hostname)
                        tasks.append(self._service_config_task(node, service,
                            desc, ensure='stopped', enable='false'))
        return tasks

    @staticmethod
    def _service_config_task(node, service, description, ensure, enable):
        props = {}
        if service.service_name:
            props['name'] = service.service_name

        if service.start_command:
            props['start'] = service.start_command
        elif service.item_type_id == 'vm-service':
            props['start'] = "systemctl restart {0}".format(
                service.service_name)

        if service.stop_command:
            props['stop'] = service.stop_command
        elif service.item_type_id == 'vm-service':
            props['stop'] = "systemctl stop {0}".format(
                service.service_name)

        if service.status_command:
            props['status'] = service.status_command
        elif service.item_type_id == 'vm-service':
            props['status'] = "/opt/ericsson/nms/litp/lib/litpmnlibvirt/" \
                              "litp_libvirt_adaptor.py {0} status".format(
                service.service_name)
        if service.item_type_id == 'vm-service':
            props['hasstatus'] = "false"
            props['provider'] = "init"

        return ConfigTask(
            node,
            service,
            description,
            'service',
            call_id=service.item_id,
            ensure=ensure,
            enable=enable,
            **props
        )
