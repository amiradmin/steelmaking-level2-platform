from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from api import plc_packets, plc_sources, real_plc_values, system_map


class SimulatorModeTests(SimpleTestCase):
    def request(self):
        request = APIRequestFactory().get('/')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, is_superuser=True))
        return request

    @patch.dict('os.environ', {'REAL_PLC_ENABLED': '0'})
    @patch('api.real_plc_values._latest_real_values')
    def test_disabled_physical_values_do_not_query_history(self, read):
        response = real_plc_values.real_plc_latest(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['enabled'])
        self.assertFalse(response.data['verified'])
        self.assertEqual(response.data['values'], [])
        read.assert_not_called()

    @patch.dict('os.environ', {'REAL_PLC_ENABLED': '1'})
    @patch('api.real_plc_values._latest_real_values', return_value=[])
    def test_explicit_physical_mode_still_reads_verified_path(self, read):
        response = real_plc_values.real_plc_latest(self.request())
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with('EAF')

    @patch.dict('os.environ', {'REAL_PLC_ENABLED': '0'})
    @patch('api.plc_packets._real_plc_entry')
    @patch('api.plc_packets._passive_real_packets')
    @patch('pathlib.Path.read_text', return_value='{"controllers":{"EAF":{"packets":[]}}}')
    def test_disabled_mode_never_probes_physical_plc(self, capture, passive, probe):
        response = plc_packets.plc_packets(self.request())
        self.assertIn('EAF', response.data['controllers'])
        self.assertNotIn('REAL', response.data['controllers'])
        probe.assert_not_called()
        passive.assert_not_called()

    @patch.dict('os.environ', {'REAL_PLC_ENABLED': '0', 'CCM_PLC_SOURCE_MODE': 'SIMULATOR'})
    @patch('api.system_map._latest_controller_samples', return_value={'eaf': {}, 'lf': {}, 'ccm': {}})
    @patch('api.system_map._latest_opcua_sample', return_value=None)
    @patch('api.system_map._service_health', return_value=True)
    @patch('api.system_map._resolve_ip', return_value=None)
    @patch('api.system_map._tcp_reachable')
    def test_map_disables_physical_node_and_omits_flow_without_tcp_probe(self, tcp, *_):
        response = system_map.live_system_map(self.request())
        node = next(n for n in response.data['nodes'] if n['id']=='real-plc')
        self.assertFalse(node['enabled'])
        self.assertEqual(node['status'], 'idle')
        self.assertFalse(any(f['from']=='real-plc' for f in response.data['flows']))
        tcp.assert_not_called()

    @patch.dict('os.environ', {'EAF_PLC_SOURCE': 'simulator', 'EAF_PLC_MODEL': 'Siemens S7-400'})
    def test_simulator_is_labeled_as_simulator(self):
        source = plc_sources._source('EAF', 'eaf-plc-simulator')
        self.assertEqual(source['source_label'], 'SIMULATOR')
        self.assertEqual(source['model'], 'S7-400 process simulator')
