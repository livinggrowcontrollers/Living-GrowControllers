import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import decoder


class HistoryIdentityTests(unittest.TestCase):
    def test_csv_writer_uses_stable_growmaster_id_not_local_uuid(self):
        local_uuid = "android-local-uuid"
        stable_device_id = "growmaster-d064"
        config_data = {
            "devices": {
                local_uuid: {
                    "device_id": stable_device_id,
                    "hostname": stable_device_id,
                    "name": "Growmaster Display Name",
                }
            }
        }
        frame = {
            "timestamp": 100,
            "device_id": local_uuid,
            "webserver": {},
        }

        with tempfile.TemporaryDirectory() as directory:
            csv_file = Path(directory) / "history.csv"
            with patch.object(decoder, "CSV_FILE", str(csv_file)), patch.object(
                decoder.config,
                "_init",
                return_value=config_data,
            ):
                decoder._write_csv([frame])

            with csv_file.open(
                newline="",
                encoding="utf-8",
            ) as source:
                row = next(csv.DictReader(source))

        self.assertEqual(row["device_id"], stable_device_id)
        self.assertEqual(
            row["device_name"],
            "Growmaster Display Name",
        )


if __name__ == "__main__":
    unittest.main()
