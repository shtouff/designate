# Copyright 2013 Hewlett-Packard Development Company, L.P.
#
# Author: Kiall Mac Innes <kiall@managedit.ie>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from mock import patch
from oslo import messaging
from oslo_log import log as logging

from designate import exceptions
from designate.central import service as central_service
from designate.tests.test_api.test_v2 import ApiV2TestCase

LOG = logging.getLogger(__name__)


class ApiV2RecordSetsTest(ApiV2TestCase):
    def setUp(self):
        super(ApiV2RecordSetsTest, self).setUp()

        # Create a domain
        self.domain = self.create_domain()

    def test_create_recordset(self):
        # Prepare a RecordSet fixture
        fixture = self.get_recordset_fixture(self.domain['name'], fixture=0)
        response = self.client.post_json(
            '/zones/%s/recordsets' % self.domain['id'], {'recordset': fixture})

        # Check the headers are what we expect
        self.assertEqual(201, response.status_int)
        self.assertEqual('application/json', response.content_type)

        # Check the body structure is what we expect
        self.assertIn('recordset', response.json)
        self.assertIn('links', response.json['recordset'])
        self.assertIn('self', response.json['recordset']['links'])

        # Check the values returned are what we expect
        self.assertIn('id', response.json['recordset'])
        self.assertIn('created_at', response.json['recordset'])
        self.assertIsNone(response.json['recordset']['updated_at'])
        self.assertIn('records', response.json['recordset'])
        # The action and status are NONE and ACTIVE as there are no records
        self.assertEqual('NONE', response.json['recordset']['action'])
        self.assertEqual('ACTIVE', response.json['recordset']['status'])

    def test_create_recordset_with_records(self):
        # Prepare a RecordSet fixture
        fixture = self.get_recordset_fixture(
            self.domain['name'], 'A', fixture=0, values={'records': [
                '192.0.2.1',
                '192.0.2.2',
            ]}
        )

        response = self.client.post_json(
            '/zones/%s/recordsets' % self.domain['id'], {'recordset': fixture})

        # Check the headers are what we expect
        self.assertEqual(202, response.status_int)
        self.assertEqual('application/json', response.content_type)

        # Check the body structure is what we expect
        self.assertIn('recordset', response.json)

        # Check the values returned are what we expect
        self.assertIn('records', response.json['recordset'])
        self.assertEqual(2, len(response.json['recordset']['records']))
        self.assertEqual('CREATE', response.json['recordset']['action'])
        self.assertEqual('PENDING', response.json['recordset']['status'])

    def test_create_recordset_invalid_id(self):
        self._assert_invalid_uuid(self.client.post, '/zones/%s/recordsets')

    def test_create_recordset_validation(self):
        # NOTE: The schemas should be tested separatly to the API. So we
        #       don't need to test every variation via the API itself.
        # Fetch a fixture
        fixture = self.get_recordset_fixture(self.domain['name'], fixture=0)

        # Add a junk field to the wrapper
        body = {'recordset': fixture, 'junk': 'Junk Field'}

        url = '/zones/%s/recordsets' % self.domain['id']

        # Ensure it fails with a 400
        self._assert_exception(
            'invalid_object', 400, self.client.post_json, url, body)

        # Add a junk field to the body
        fixture['junk'] = 'Junk Field'
        body = {'recordset': fixture}

        # Ensure it fails with a 400
        self._assert_exception(
            'invalid_object', 400, self.client.post_json, url, body)

    @patch.object(central_service.Service, 'create_recordset',
                  side_effect=messaging.MessagingTimeout())
    def test_create_recordset_timeout(self, _):
        fixture = self.get_recordset_fixture(self.domain['name'], fixture=0)

        body = {'recordset': fixture}

        url = '/zones/%s/recordsets' % self.domain['id']

        self._assert_exception('timeout', 504, self.client.post_json, url,
                               body)

    @patch.object(central_service.Service, 'create_recordset',
                  side_effect=exceptions.DuplicateRecordSet())
    def test_create_recordset_duplicate(self, _):
        fixture = self.get_recordset_fixture(self.domain['name'], fixture=0)

        body = {'recordset': fixture}

        url = '/zones/%s/recordsets' % self.domain['id']

        self._assert_exception('duplicate_recordset', 409,
                               self.client.post_json, url, body)

    def test_create_recordset_invalid_domain(self):
        fixture = self.get_recordset_fixture(self.domain['name'], fixture=0)

        body = {'recordset': fixture}

        url = '/zones/ba751950-6193-11e3-949a-0800200c9a66/recordsets'

        self._assert_exception('domain_not_found', 404, self.client.post_json,
                               url, body)

    def test_recordsets_invalid_url(self):
        url = '/zones/recordsets'
        self._assert_exception('not_found', 404, self.client.get, url)
        self._assert_exception('not_found', 404, self.client.post_json, url)

        # Pecan returns a 405 for Patch and delete operations
        response = self.client.patch_json(url, status=405)
        self.assertEqual(405, response.status_int)

        response = self.client.delete(url, status=405)
        self.assertEqual(405, response.status_int)

    def test_get_recordsets(self):
        url = '/zones/%s/recordsets' % self.domain['id']

        response = self.client.get(url)

        # Check the headers are what we expect
        self.assertEqual(200, response.status_int)
        self.assertEqual('application/json', response.content_type)

        # Check the body structure is what we expect
        self.assertIn('recordsets', response.json)
        self.assertIn('links', response.json)
        self.assertIn('self', response.json['links'])

        # We should start with 2 pending recordsets for SOA & NS
        # pending because pool manager is not active
        self.assertEqual(2, len(response.json['recordsets']))
        for recordset in response.json['recordsets']:
            self.assertEqual('CREATE', recordset['action'])
            self.assertEqual('PENDING', recordset['status'])

        soa = self.central_service.find_recordset(
            self.admin_context, criterion={'domain_id': self.domain['id'],
                                           'type': 'SOA'})
        ns = self.central_service.find_recordset(
            self.admin_context, criterion={'domain_id': self.domain['id'],
                                           'type': 'NS'})
        data = [self.create_recordset(self.domain,
                name='x-%s.%s' % (i, self.domain['name']))
                for i in xrange(0, 10)]
        data.insert(0, ns)
        data.insert(0, soa)

        self._assert_paging(data, url, key='recordsets')

        self._assert_invalid_paging(data, url, key='recordsets')

    def test_get_recordsets_filter(self):
        # Add recordsets for testing
        fixtures = [
            self.get_recordset_fixture(
                self.domain['name'], 'A', fixture=0, values={'records': [
                    '192.0.2.1',
                    '192.0.2.2',
                ]}
            ),
            self.get_recordset_fixture(
                self.domain['name'], 'A', fixture=1, values={'records': [
                    '192.0.2.1',
                    '192.0.2.3'
                ]}
            ),
        ]

        for fixture in fixtures:
            response = self.client.post_json(
                '/zones/%s/recordsets' % self.domain['id'],
                {'recordset': fixture})

        get_urls = [
            '/zones/%s/recordsets?data=192.0.2.1' % self.domain['id'],
            '/zones/%s/recordsets?data=192.0.2.2' % self.domain['id'],
            '/zones/%s/recordsets?data=192.0.2.1&name=%s' % (
                self.domain['id'], fixtures[0]['name'])
        ]

        correct_results = [2, 1, 1]

        for get_url, correct_result in zip(get_urls, correct_results):

            response = self.client.get(get_url)

            # Check the headers are what we expect
            self.assertEqual(200, response.status_int)
            self.assertEqual('application/json', response.content_type)

            # Check that the correct number of recordsets match
            self.assertEqual(correct_result, len(response.json['recordsets']))

    def test_get_recordsets_invalid_id(self):
        self._assert_invalid_uuid(self.client.get, '/zones/%s/recordsets')

    @patch.object(central_service.Service, 'get_domain',
                  side_effect=messaging.MessagingTimeout())
    def test_get_recordsets_timeout(self, _):
        url = '/zones/ba751950-6193-11e3-949a-0800200c9a66/recordsets'

        self._assert_exception('timeout', 504, self.client.get, url)

    def test_get_deleted_recordsets(self):
        zone = self.create_domain(fixture=1)
        self.create_recordset(zone)
        url = '/zones/%s/recordsets' % zone['id']

        response = self.client.get(url)

        # Check the headers are what we expect
        self.assertEqual(200, response.status_int)

        # now delete the domain and get the recordsets
        self.client.delete('/zones/%s' % zone['id'], status=202)

        # Simulate the domain having been deleted on the backend
        domain_serial = self.central_service.get_domain(
            self.admin_context, zone['id']).serial
        self.central_service.update_status(
            self.admin_context, zone['id'], "SUCCESS", domain_serial)

        # Check that we get a domain_not_found error
        self._assert_exception('domain_not_found', 404, self.client.get, url)

    def test_get_recordset(self):
        # Create a recordset
        recordset = self.create_recordset(self.domain)

        url = '/zones/%s/recordsets/%s' % (self.domain['id'], recordset['id'])
        response = self.client.get(url)

        # Check the headers are what we expect
        self.assertEqual(200, response.status_int)
        self.assertEqual('application/json', response.content_type)

        # Check the body structure is what we expect
        self.assertIn('recordset', response.json)
        self.assertIn('links', response.json['recordset'])
        self.assertIn('self', response.json['recordset']['links'])

        # Check the values returned are what we expect
        self.assertIn('id', response.json['recordset'])
        self.assertIn('created_at', response.json['recordset'])
        self.assertIsNone(response.json['recordset']['updated_at'])
        self.assertEqual(recordset['name'], response.json['recordset']['name'])
        self.assertEqual(recordset['type'], response.json['recordset']['type'])
        # The action and status are NONE and ACTIVE as there are no records
        self.assertEqual('NONE', response.json['recordset']['action'])
        self.assertEqual('ACTIVE', response.json['recordset']['status'])

    def test_get_recordset_invalid_id(self):
        self._assert_invalid_uuid(self.client.get, '/zones/%s/recordsets/%s')

    @patch.object(central_service.Service, 'get_recordset',
                  side_effect=messaging.MessagingTimeout())
    def test_get_recordset_timeout(self, _):
        url = '/zones/%s/recordsets/ba751950-6193-11e3-949a-0800200c9a66' % (
            self.domain['id'])

        self._assert_exception('timeout', 504, self.client.get, url,
                               headers={'Accept': 'application/json'})

    @patch.object(central_service.Service, 'get_recordset',
                  side_effect=exceptions.RecordSetNotFound())
    def test_get_recordset_missing(self, _):
        url = '/zones/%s/recordsets/ba751950-6193-11e3-949a-0800200c9a66' % (
            self.domain['id'])

        self._assert_exception('recordset_not_found', 404,
                               self.client.get, url,
                               headers={'Accept': 'application/json'})

    def test_update_recordset(self):
        # Create a recordset
        recordset = self.create_recordset(self.domain)

        # Prepare an update body
        body = {'recordset': {'description': 'Tester'}}

        url = '/zones/%s/recordsets/%s' % (recordset['domain_id'],
                                           recordset['id'])
        response = self.client.put_json(url, body, status=200)

        # Check the headers are what we expect
        self.assertEqual(200, response.status_int)
        self.assertEqual('application/json', response.content_type)

        # Check the body structure is what we expect
        self.assertIn('recordset', response.json)
        self.assertIn('links', response.json['recordset'])
        self.assertIn('self', response.json['recordset']['links'])

        # Check the values returned are what we expect
        self.assertIn('id', response.json['recordset'])
        self.assertIsNotNone(response.json['recordset']['updated_at'])
        self.assertEqual('Tester', response.json['recordset']['description'])
        # The action and status are NONE and ACTIVE as there are no records
        self.assertEqual('NONE', response.json['recordset']['action'])
        self.assertEqual('ACTIVE', response.json['recordset']['status'])

    def test_update_recordset_with_record_create(self):
        # Create a recordset
        recordset = self.create_recordset(self.domain, 'A')

        # The action and status are NONE and ACTIVE as there are no records
        self.assertEqual('NONE', recordset['action'])
        self.assertEqual('ACTIVE', recordset['status'])

        # Prepare an update body
        body = {'recordset': {'description': 'Tester',
                              'records': ['192.0.2.1', '192.0.2.2']}}

        url = '/zones/%s/recordsets/%s' % (recordset['domain_id'],
                                           recordset['id'])
        response = self.client.put_json(url, body, status=202)

        # Check the headers are what we expect
        self.assertEqual(202, response.status_int)
        self.assertEqual('application/json', response.content_type)

        # Check the body structure is what we expect
        self.assertIn('recordset', response.json)

        # Check the values returned are what we expect
        self.assertIn('records', response.json['recordset'])
        self.assertEqual(2, len(response.json['recordset']['records']))
        self.assertEqual(set(['192.0.2.1', '192.0.2.2']),
                         set(response.json['recordset']['records']))
        self.assertEqual('UPDATE', response.json['recordset']['action'])
        self.assertEqual('PENDING', response.json['recordset']['status'])

    def test_update_recordset_with_record_replace(self):
        # Create a recordset with one record
        recordset = self.create_recordset(self.domain, 'A')
        self.create_record(self.domain, recordset)

        # Prepare an update body
        body = {'recordset': {'description': 'Tester',
                              'records': ['192.0.2.201', '192.0.2.202']}}

        url = '/zones/%s/recordsets/%s' % (recordset['domain_id'],
                                           recordset['id'])
        response = self.client.put_json(url, body, status=202)

        # Check the headers are what we expect
        self.assertEqual(202, response.status_int)
        self.assertEqual('application/json', response.content_type)

        # Check the body structure is what we expect
        self.assertIn('recordset', response.json)

        # Check the values returned are what we expect
        self.assertIn('records', response.json['recordset'])
        self.assertEqual(2, len(response.json['recordset']['records']))
        self.assertEqual(set(['192.0.2.201', '192.0.2.202']),
                         set(response.json['recordset']['records']))

    def test_update_recordset_with_record_clear(self):
        # Create a recordset with one record
        recordset = self.create_recordset(self.domain, 'A')
        self.create_record(self.domain, recordset)

        # Prepare an update body
        body = {'recordset': {'description': 'Tester', 'records': []}}

        url = '/zones/%s/recordsets/%s' % (recordset['domain_id'],
                                           recordset['id'])
        response = self.client.put_json(url, body, status=200)

        # Check the headers are what we expect
        self.assertEqual(200, response.status_int)
        self.assertEqual('application/json', response.content_type)

        # Check the body structure is what we expect
        self.assertIn('recordset', response.json)

        # Check the values returned are what we expect
        self.assertIn('records', response.json['recordset'])
        self.assertEqual(0, len(response.json['recordset']['records']))

    def test_update_recordset_invalid_id(self):
        self._assert_invalid_uuid(
            self.client.put_json, '/zones/%s/recordsets/%s')

    def test_update_recordset_validation(self):
        # NOTE: The schemas should be tested separatly to the API. So we
        #       don't need to test every variation via the API itself.
        # Create a zone
        recordset = self.create_recordset(self.domain)

        # Prepare an update body with junk in the wrapper
        body = {'recordset': {'description': 'Tester',
                              'records': ['192.3.3.17'],
                              'junk': 'Junk Field'}}

        # Ensure it fails with a 400
        url = '/zones/%s/recordsets/%s' % (recordset['domain_id'],
                                           recordset['id'])

        self._assert_exception('invalid_object', 400, self.client.put_json,
                               url, body)

        # Prepare an update body with junk in the body
        body = {'recordset': {'description': 'Tester', 'junk': 'Junk Field'}}

        # Ensure it fails with a 400
        self._assert_exception('invalid_object', 400, self.client.put_json,
                               url, body)

    @patch.object(central_service.Service, 'get_recordset',
                  side_effect=exceptions.DuplicateRecordSet())
    def test_update_recordset_duplicate(self, _):
        # Prepare an update body
        body = {'recordset': {'description': 'Tester'}}

        # Ensure it fails with a 409
        url = ('/zones/%s/recordsets/ba751950-6193-11e3-949a-0800200c9a66'
               % (self.domain['id']))

        self._assert_exception('duplicate_recordset', 409,
                               self.client.put_json, url, body)

    @patch.object(central_service.Service, 'get_recordset',
                  side_effect=messaging.MessagingTimeout())
    def test_update_recordset_timeout(self, _):
        # Prepare an update body
        body = {'recordset': {'description': 'Tester'}}

        # Ensure it fails with a 504
        url = ('/zones/%s/recordsets/ba751950-6193-11e3-949a-0800200c9a66'
               % (self.domain['id']))

        self._assert_exception('timeout', 504, self.client.put_json, url,
                               body)

    @patch.object(central_service.Service, 'get_recordset',
                  side_effect=exceptions.RecordSetNotFound())
    def test_update_recordset_missing(self, _):
        # Prepare an update body
        body = {'recordset': {'description': 'Tester'}}

        # Ensure it fails with a 404
        url = ('/zones/%s/recordsets/ba751950-6193-11e3-949a-0800200c9a66'
               % (self.domain['id']))

        self._assert_exception('recordset_not_found', 404,
                               self.client.put_json, url, body)

    def test_delete_recordset(self):
        recordset = self.create_recordset(self.domain)

        url = '/zones/%s/recordsets/%s' % (recordset['domain_id'],
                                           recordset['id'])
        self.client.delete(url, status=204)

    @patch.object(central_service.Service, 'delete_recordset',
                  side_effect=exceptions.RecordSetNotFound())
    def test_delete_recordset_missing(self, _):
        url = ('/zones/%s/recordsets/ba751950-6193-11e3-949a-0800200c9a66'
               % (self.domain['id']))

        self._assert_exception('recordset_not_found', 404,
                               self.client.delete, url)

    def test_delete_recordset_invalid_id(self):
        self._assert_invalid_uuid(
            self.client.delete, '/zones/%s/recordsets/%s')

    def test_metadata_exists(self):
        url = '/zones/%s/recordsets' % self.domain['id']

        response = self.client.get(url)

        # Make sure the fields exist
        self.assertIn('metadata', response.json)
        self.assertIn('total_count', response.json['metadata'])

    def test_total_count(self):
        url = '/zones/%s/recordsets' % self.domain['id']

        response = self.client.get(url)

        # The NS and SOA records are there by default
        self.assertEqual(2, response.json['metadata']['total_count'])

        # Create a recordset
        fixture = self.get_recordset_fixture(self.domain['name'], fixture=0)
        response = self.client.post_json(
            '/zones/%s/recordsets' % self.domain['id'], {'recordset': fixture})

        response = self.client.get(url)

        # Make sure total_count picked up the change
        self.assertEqual(3, response.json['metadata']['total_count'])

    def test_total_count_pagination(self):
        # Create two recordsets
        fixture = self.get_recordset_fixture(self.domain['name'], fixture=0)
        response = self.client.post_json(
            '/zones/%s/recordsets' % self.domain['id'], {'recordset': fixture})

        fixture = self.get_recordset_fixture(self.domain['name'], fixture=1)
        response = self.client.post_json(
            '/zones/%s/recordsets' % self.domain['id'], {'recordset': fixture})

        # Paginate the recordsets to two, there should be four now
        url = '/zones/%s/recordsets?limit=2' % self.domain['id']

        response = self.client.get(url)

        # There are two recordsets returned
        self.assertEqual(2, len(response.json['recordsets']))

        # But there should be four in total (NS/SOA + the created)
        self.assertEqual(4, response.json['metadata']['total_count'])
