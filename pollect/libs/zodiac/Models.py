import base64
import json
import time
from typing import Dict, Optional

from pollect.libs.api.Serializable import Serializable


class SystemInfo(Serializable):
    def __init__(self):
        super().__init__()
        self.id: int = 0
        self.serial_number: str = ''
        self.created_at: str = ''
        self.updated_at: str = ''
        self.name: str = ''
        self.device_type: str = ''
        self.owner_id: str = ''
        self.updating: bool = False
        self.firmware_version: Optional[str] = None
        self.target_firmware_version: Optional[str] = None


class Credentials(Serializable):
    def __init__(self):
        super().__init__()
        self.AccessKeyId: str = ''
        self.SecretKey: str = ''
        self.Expiration: str = ''
        self.IdentityId: str = ''


class OAuthPool(Serializable):
    def __init__(self):
        super().__init__()
        self.AccessToken: str = ''
        self.ExpiresIn: int = 0
        self.TokenType: str = 'Bearer'
        self.RefreshToken: str = ''
        self.IdToken: str = ''


class LoginReply(Serializable):
    def __init__(self):
        super().__init__()
        self.username: str = ''
        self.email: str = ''
        self.first_name: str = ''
        self.last_name: str = ''
        self.address: str = ''
        self.address_1: str = ''
        self.address_2: str = ''
        self.city: str = ''
        self.state: str = ''
        self.country: str = ''
        self.postal_code: str = ''
        self.id: int = 0
        self.authentication_token: str = ''
        self.session_id: str = ''
        self.created_at: str = ''
        self.updated_at: str = ''
        self.time_zone: str = ''
        self.phone: str = ''
        self.opt_in_1: str = ''
        self.opt_in_2: str = ''
        self.role: str = ''
        self.cognitoPool: Dict[str, str] = {}
        self.credentials: Credentials = Credentials()
        self.userPoolOAuth: OAuthPool = OAuthPool()

    def is_logged_in(self) -> bool:
        return self.userPoolOAuth.ExpiresIn != 0

    def is_expired(self) -> bool:
        # Very crude JWT parsing
        jwt_payload_b64 = self.userPoolOAuth.IdToken.split('.')[1]
        missing_padding = len(jwt_payload_b64) % 4
        if missing_padding:
            jwt_payload_b64 += '=' * (4 - missing_padding)
        jwt_payload = base64.b64decode(jwt_payload_b64)
        jwt_payload = json.loads(jwt_payload)
        exp = jwt_payload.get('exp', 0)
        return time.time() >= exp


class PoolCleanerInfo(Serializable):
    def __init__(self):
        super().__init__()
        self.deviceId: str = ''
        self.state = PoolCleanerState()
        self.ts: int = 0


class PoolCleanerState(Serializable):
    def __init__(self):
        super().__init__()
        self.reported = ReportedPoolCleanerState()


class ReportedPoolCleanerState(Serializable):
    def __init__(self):
        super().__init__()
        self.aws = AwsState()
        self.equipment = Equipment()
        self.dt: str = ''
        """
        Device type(?)
        cb: Battery powered device,
        vr: Line powered device
        """

        self.vt: str = ''
        """
        Some sort of part number?
        """


class Equipment(Serializable):
    def __init__(self):
        super().__init__()
        self.robot = Robot()


class ProgramCycles:
    WATERLINE = 0
    QUICK_CLEAN = 1
    SMART_CLEAN = 2
    DEEP_CLEAN = 3
    CUSTOM = 4


class Robot(Serializable):
    def __init__(self):
        super().__init__()
        self.equipmentId: str = ''
        self.errorCode: int = 0
        self.errorState: int = 0
        self.canister: int = 0
        self.durations = CycleDurations()
        self.state: int = 0
        """
        State of the device
        0: Stopped
        1: Running
        2: Remote control
        """
        self.prCyc: int = 0
        """
        See PROGRAM_CYCLES
        """

        self.stepper: int = 0
        self.stepperAdjTime: int = 0
        self.totalHours: int = 0
        self.customCyc: int = 0
        self.customIntensity: int = 0
        self.cycleStartTime: int = 0
        """
        Unix timestamp when the clean cycle was started
        """

        self.firstSmrtFlag: int = 0
        self.liftControl: int = 0
        self.logger: int = 0
        self.repeat: int = 0

        self.rmt_ctrl: int = 0
        """
        Indicates if remote control is enabled
        """

        self.scanTimeDuration: int = 0

        # Schedules
        self.schConf0Enable: int = 0
        self.schConf0Hour: int = 0
        self.schConf0Min: int = 0
        self.schConf0Prt: int = 0
        self.schConf0WDay: int = 0
        self.schConf1Enable: int = 0
        self.schConf1Hour: int = 0
        self.schConf1Min: int = 0
        self.schConf1Prt: int = 0
        self.schConf1WDay: int = 0
        self.schConf2Enable: int = 0
        self.schConf2Hour: int = 0
        self.schConf2Min: int = 0
        self.schConf2Prt: int = 0
        self.schConf2WDay: int = 0
        self.schConf3Enable: int = 0
        self.schConf3Hour: int = 0
        self.schConf3Min: int = 0
        self.schConf3Prt: int = 0
        self.schConf3WDay: int = 0
        self.schConf4Enable: int = 0
        self.schConf4Hour: int = 0
        self.schConf4Min: int = 0
        self.schConf4Prt: int = 0
        self.schConf4WDay: int = 0
        self.schConf5Enable: int = 0
        self.schConf5Hour: int = 0
        self.schConf5Min: int = 0
        self.schConf5Prt: int = 0
        self.schConf5WDay: int = 0
        self.schConf6Enable: int = 0
        self.schConf6Hour: int = 0
        self.schConf6Min: int = 0
        self.schConf6Prt: int = 0
        self.schConf6WDay: int = 0

    def get_remaining_time(self) -> int:
        """
        Returns the number of seconds until the cleaning cycle completes
        """
        duration_sec = self.get_duration() * 60
        delta_sec = time.time() - self.cycleStartTime
        return round(duration_sec - delta_sec)

    def get_duration(self) -> int:
        """
        Returns the duration of the current program cycle.
        :return: Duration in minutes
        """
        if self.prCyc == ProgramCycles.WATERLINE:
            return self.durations.waterTim
        if self.prCyc == ProgramCycles.QUICK_CLEAN:
            return self.durations.quickTim
        if self.prCyc == ProgramCycles.SMART_CLEAN:
            if self.firstSmrtFlag != 0:
                return self.durations.firstSmartTim
            return self.durations.smartTim
        if self.prCyc == ProgramCycles.DEEP_CLEAN:
            return self.durations.deepTim
        if self.prCyc == ProgramCycles.CUSTOM:
            return self.durations.customTim
        raise ValueError(f'No duration for program cycle {self.prCyc}')

    def is_running(self) -> bool:
        return self.state != 0


class CycleDurations(Serializable):
    def __init__(self):
        super().__init__()
        self.customTim: int = 0
        """
        Custom cycle duration in minutes
        """

        self.deepTim: int = 0
        """
        Deep clean cycle duration in minutes
        """

        self.firstSmartTim: int = 0
        """
        First-time smart clean cycle duration in minutes
        """

        self.smartTim: int = 0
        """
        Smart clean cycle duration in minutes
        """

        self.quickTim: int = 0
        """
        Quick clean cycle duration in minutes
        """

        self.waterTim: int = 0
        """
        Waterline duration in minutes
        """


class AwsState(Serializable):
    STATUS_CONNECTED = 'connected'
    STATUS_DISCONNECTED = 'disconnected'

    def __init__(self):
        super().__init__()
        self.session_id: str = ''
        self.status: str = ''
        self.timestamp: int = 0


class BasicCommand:
    FAILURE_VALUE = "FF"
    REQUEST_DESTINATION = "0A"
    RESPONSE_DESTINATION = "00"
    SUCCESS_VALUE = "01"


class GetCleanerStatusCommand:
    def __init__(self):
        self.command = 'GetCleanerStatus'
        self.raw_value = '11'

    def get_hex_for_request(self, a: any, b: str) -> str:
        return self.request_command()

    def request_command(self) -> str:
        return BasicCommand.REQUEST_DESTINATION + self.raw_value
