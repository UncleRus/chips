#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from jsonrpcclient.clients.http_client import HTTPClient
from jsonrpcclient.requests import Request
from jsonrpcclient.id_generators import random
from jsonrpcclient.exceptions import ReceivedErrorResponseError
import unittest


class JsonRpcTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.gen_id = random()

    def setUp(self):
        self.client = HTTPClient('http://127.0.0.1:8080')

    def tearDown(self):
        self.client.session.close()

    def test_single_args(self):
        r = self.client.request('test.hello', 'WORLD',
                                id_generator=self.gen_id)
        self.assertEqual(r.data.result, 'Hello WORLD!')

    def test_single_kwargs(self):
        r = self.client.request('test.hello', who='WORLD',
                                id_generator=self.gen_id)
        self.assertEqual(r.data.result, 'Hello WORLD!')

    def test_single_notification(self):
        r = self.client.notify('test.hello', who='WORLD')
        print(r.text)

    def test_single_err(self):
        with self.assertRaises(ReceivedErrorResponseError) as cm:
            self.client.request('test.test_div', 10, 0,
                                id_generator=self.gen_id)
        exception = cm.exception
        self.assertEqual(exception.args[0], 'division by zero')

    def test_batch(self):
        gen_id = iter(range(100))
        batch = (
            Request('vadd.test', 5, 10, id_generator=gen_id),
            Request('vsub.test', arg1=10, arg2=9, id_generator=gen_id),
            Request('test.hello', 'WORLD', id_generator=gen_id),
            Request('nonexistent_method', id_generator=gen_id),
            Request('test.test_div', 10, 0, id_generator=gen_id),
        )
        resp = self.client.send(batch)
        self.assertEqual(len(resp.data), 5)
        for r in resp.data:
            if r.id == 0:
                self.assertEqual(r.result, 15)
            elif r.id == 1:
                self.assertEqual(r.result, 1)
            elif r.id == 2:
                self.assertEqual(r.result, 'Hello WORLD!')
            elif r.id == 3:
                self.assertFalse(r.ok)
                self.assertEqual(r.code, -32601)
            elif r.id == 4:
                self.assertFalse(r.ok)
                self.assertEqual(r.code, -32000)
                self.assertEqual(r.message, 'division by zero')


if __name__ == '__main__':
    unittest.main()
