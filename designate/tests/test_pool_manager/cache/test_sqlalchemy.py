# Copyright 2014 eBay Inc.
#
# Author: Ron Rickard <rrickard@ebaysf.com>
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
from designate.pool_manager import cache
from designate.tests import TestCase
from designate.tests.test_pool_manager.cache import PoolManagerCacheTestCase


class SqlalchemyPoolManagerCacheTest(PoolManagerCacheTestCase, TestCase):
    def setUp(self):
        super(SqlalchemyPoolManagerCacheTest, self).setUp()

        self.cache = cache.get_pool_manager_cache('sqlalchemy')
