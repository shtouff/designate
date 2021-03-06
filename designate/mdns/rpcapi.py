# Copyright (c) 2014 Rackspace Hosting
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from oslo.config import cfg
from oslo_log import log as logging
from oslo import messaging

from designate.i18n import _LI
from designate import rpc


LOG = logging.getLogger(__name__)

MDNS_API = None


class MdnsAPI(object):
    """
    Client side of the mdns RPC API.

    Notify API version history:

        1.0 - Added notify_zone_changed and poll_for_serial_number.
    """
    RPC_NOTIFY_API_VERSION = '1.0'

    def __init__(self, topic=None):
        topic = topic if topic else cfg.CONF.mdns_topic

        notify_target = messaging.Target(topic=topic,
                                         namespace='notify',
                                         version=self.RPC_NOTIFY_API_VERSION)
        self.notify_client = rpc.get_client(notify_target, version_cap='1.0')

    @classmethod
    def get_instance(cls):
        """
        The rpc.get_client() which is called upon the API object initialization
        will cause a assertion error if the designate.rpc.TRANSPORT isn't setup
        by rpc.init() before.

        This fixes that by creating the rpcapi when demanded.
        """
        global MDNS_API
        if not MDNS_API:
            MDNS_API = cls()
        return MDNS_API

    def notify_zone_changed(self, context, domain, server, timeout,
                            retry_interval, max_retries, delay):
        LOG.info(_LI("notify_zone_changed: Calling mdns for zone '%(zone)s', "
                     "serial '%(serial)s' to server '%(host)s:%(port)s'") %
                 {'zone': domain.name, 'serial': domain.serial,
                  'host': server.host, 'port': server.port})
        # The notify_zone_changed method is a cast rather than a call since the
        # caller need not wait for the notify to complete.
        return self.notify_client.cast(
            context, 'notify_zone_changed', domain=domain,
            server=server, timeout=timeout, retry_interval=retry_interval,
            max_retries=max_retries, delay=delay)

    def poll_for_serial_number(self, context, domain, server, timeout,
                               retry_interval, max_retries, delay):
        LOG.info(_LI("poll_for_serial_number: Calling mdns for zone '%(zone)s'"
                     ", serial '%(serial)s' to server '%(host)s:%(port)s'") %
                 {'zone': domain.name, 'serial': domain.serial,
                  'host': server.host, 'port': server.port})
        # The poll_for_serial_number method is a cast rather than a call since
        # the caller need not wait for the poll to complete. Mdns informs pool
        # manager of the return value using update_status
        return self.notify_client.cast(
            context, 'poll_for_serial_number', domain=domain,
            server=server, timeout=timeout, retry_interval=retry_interval,
            max_retries=max_retries, delay=delay)
