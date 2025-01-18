import json
import os
from typing import Optional, List

from pollect.core.ValueSet import ValueSet, Value
from pollect.libs.zodiac.Models import LoginReply
from pollect.libs.zodiac.ZodiacApi import ZodiacApi
from pollect.sources.Source import Source


class ZodiacPoolSource(Source):
    """
    Metrics about zodiac pool cleaners.
    Tested with Zodiac Alpha 63 IQ
    """
    AUTH_FILE = "zodiac-token.json"

    def __init__(self, config):
        super().__init__(config)
        self._user = config['user']
        self._password = config['password']
        self.api = ZodiacApi()
        self.expires_in = 0

    def setup_source(self, global_conf):
        super().setup_source(global_conf)

        # Restore auth (if possible)
        if not os.path.isfile(self.AUTH_FILE):
            self._login()
            return

        with open(self.AUTH_FILE, "r") as f:
            login_data = json.load(f)

        reply = LoginReply()
        reply.deserialize(login_data)
        # Verify login
        try:
            self.api.user = reply
            self.api.get_system_list_v2()
        except ValueError as e:
            self.log.warning(f'{e}, trying to login again')
            self._login()
            return

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        values = ValueSet(labels=['device_serial'])
        for device in self.api.get_system_list_v2():
            state = self.api.get_device_info(device.serial_number)
            robot = state.state.reported.equipment.robot

            values.add(Value(robot.state, [device.serial_number], 'state'))
            values.add(Value(robot.prCyc, [device.serial_number], 'program_cycle'))
            values.add(Value(robot.errorCode, [device.serial_number], 'error_code'))

            remaining = -1
            if robot.is_running():
                remaining = robot.get_remaining_time()

            values.add(Value(remaining, [device.serial_number], 'remaining_time'))

        self._persist_auth()
        return values

    def _persist_auth(self):
        if self.api.user.userPoolOAuth.ExpiresIn == self.expires_in:
            return

        self.expires_in = self.api.user.userPoolOAuth.ExpiresIn
        with open(self.AUTH_FILE, "w") as f:
            json.dump(self.api.user.get_data(), f)

    def _login(self):
        self.api.login(self._user, self._password)
        self._persist_auth()
