import time
import unittest

from pollect.libs.zodiac.Models import Robot, ProgramCycles


class TestZodiacApi(unittest.TestCase):
    def test_duration(self):
        robot = Robot()
        robot.cycleStartTime = (time.time() - 60 * 60)  # 1h ago
        robot.prCyc = ProgramCycles.SMART_CLEAN
        robot.durations.smartTim = 160
        self.assertEquals(100,  round(robot.get_remaining_time()/60))