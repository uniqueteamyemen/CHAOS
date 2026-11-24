import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.audits import p2_a_usgs_magnitude_provenance as audit

class P2AMagnitudeProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.belt={"id":"test","minlatitude":-10,"maxlatitude":10,"minlongitude":100,"maxlongitude":120}
        self.accepted={"us123":{"time":"2020-01-01T00:00:00Z","mag":5.0,"type":"mb"}}

    def test_csv_requires_mag_source(self):
        good=b"time,latitude,longitude,depth,mag,magType,net,id,magSource\n2020-01-01T00:00:00Z,1,2,3,5,mb,us,us123,us\n"
        self.assertEqual(audit.parse_csv(good)[0]["magSource"],"us")
        with self.assertRaisesRegex(ValueError,"MAG_SOURCE_FIELD_MISSING"):
            audit.parse_csv(b"time,mag,magType,id\n2020-01-01,5,mb,us123\n")

    def test_fetch_window_records_inclusive_api_bounds(self):
        data=b"time,latitude,longitude,depth,mag,magType,net,id,magSource\n2020-01-01T00:00:00Z,1,2,3,5,mb,us,us123,us\n"
        with tempfile.TemporaryDirectory() as d:
            manifest=[]
            with patch.object(audit.p2,"get",return_value=data):
                rows=audit.fetch_window(self.belt,"2020-01-01T00:00:00","2021-01-01T00:00:00",Path(d)/"raw",manifest)
            self.assertEqual(len(rows),1)
            self.assertEqual(manifest[0]["api_boundary_semantics"],"START_AND_END_INCLUSIVE")

    def test_saturated_query_splits(self):
        header="time,latitude,longitude,depth,mag,magType,net,id,magSource\n"
        first=(header+"2020-01-01T00:00:00Z,1,2,3,5,mb,us,us123,us\n2020-01-02T00:00:00Z,1,2,3,5,mb,us,us124,us\n").encode()
        left=(header+"2020-01-01T00:00:00Z,1,2,3,5,mb,us,us123,us\n").encode()
        right=(header+"2020-01-02T00:00:00Z,1,2,3,5,mb,us,us124,us\n").encode()
        with tempfile.TemporaryDirectory() as d:
            manifest=[]
            with patch.object(audit,"SATURATION",2),patch.object(audit.p2,"get",side_effect=[first,left,right]):
                rows=audit.fetch_window(self.belt,"2020-01-01T00:00:00","2022-01-01T00:00:00",Path(d)/"raw",manifest)
            self.assertEqual(len(manifest),3)
            self.assertEqual(len(rows),2)

    def test_missing_source_is_unresolved(self):
        rows=[{"id":"us123","time":"2020-01-01T00:00:00Z","mag":"5","magType":"mb","magSource":"","net":"us"}]
        with tempfile.TemporaryDirectory() as d:
            result=audit.reconcile("test",self.accepted,rows,Path(d))
        self.assertEqual(result["status"],"PARTIAL_MAG_SOURCE_MISSING_REQUIRES_REVIEW")
        self.assertEqual(result["magnitude_source_missing_events"],1)

    def test_mixed_sources_require_stratification(self):
        accepted={"us123":{"time":"2020-01-01T00:00:00Z","mag":5.0,"type":"mb"},
                  "us124":{"time":"2020-01-02T00:00:00Z","mag":5.1,"type":"mb"}}
        rows=[{"id":"us123","time":"2020-01-01T00:00:00Z","mag":"5.0","magType":"mb","magSource":"us","net":"us"},
              {"id":"us124","time":"2020-01-02T00:00:00Z","mag":"5.1","magType":"mb","magSource":"ak","net":"us"}]
        with tempfile.TemporaryDirectory() as d:
            result=audit.reconcile("test",accepted,rows,Path(d))
        self.assertEqual(result["status"],"SOURCE_OR_MAG_TYPE_MIXTURE_REQUIRES_STRATIFICATION")

    def test_magnitude_type_mixture_requires_stratification(self):
        accepted={"us123":{"time":"2020-01-01T00:00:00Z","mag":5.0,"type":"mb"},
                  "us124":{"time":"2020-01-02T00:00:00Z","mag":5.1,"type":"mw"}}
        rows=[{"id":"us123","time":"2020-01-01T00:00:00Z","mag":"5.0","magType":"mb","magSource":"us","net":"us"},
              {"id":"us124","time":"2020-01-02T00:00:00Z","mag":"5.1","magType":"mw","magSource":"us","net":"us"}]
        with tempfile.TemporaryDirectory() as d:
            result=audit.reconcile("test",accepted,rows,Path(d))
        self.assertEqual(result["status"],"SOURCE_OR_MAG_TYPE_MIXTURE_REQUIRES_STRATIFICATION")

    def test_magnitude_type_mixture_requires_stratification(self):
        accepted={"us123":{"time":"2020-01-01T00:00:00Z","mag":5.0,"type":"mb"},
                  "us124":{"time":"2020-01-02T00:00:00Z","mag":5.1,"type":"mw"}}
        rows=[{"id":"us123","time":"2020-01-01T00:00:00Z","mag":"5.0","magType":"mb","magSource":"us","net":"us"},
              {"id":"us124","time":"2020-01-02T00:00:00Z","mag":"5.1","magType":"mw","magSource":"us","net":"us"}]
        with tempfile.TemporaryDirectory() as d:
            result=audit.reconcile("test",accepted,rows,Path(d))
        self.assertEqual(result["status"],"SOURCE_OR_MAG_TYPE_MIXTURE_REQUIRES_STRATIFICATION")

    def test_mismatch_and_conflicting_overlap_fail_closed(self):
        rows=[{"id":"us123","time":"2020-01-01T00:00:02Z","mag":"5.2","magType":"mw","magSource":"us","net":"us"},
              {"id":"us123","time":"2020-01-01T00:00:02Z","mag":"5.2","magType":"mw","magSource":"ak","net":"us"}]
        with tempfile.TemporaryDirectory() as d:
            result=audit.reconcile("test",self.accepted,rows,Path(d))
        self.assertEqual(result["status"],"FAIL_RECONCILIATION")
        self.assertTrue(result["conflicts"])
        self.assertTrue(result["mismatches"])

if __name__=="__main__":
    unittest.main()
