import shutil

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source


class DiskUsageSource(Source):
    def __init__(self, config):
        super().__init__(config)
        self.disks = config.get('disks')

    def _probe(self):
        data = ValueSet(['disk', 'type'])

        for disk in self.disks:
            disk_name = self.sanitize_disk_name(disk)
            try:
                usage = shutil.disk_usage(disk)
            except FileNotFoundError:
                continue
            data.add(Value(usage.total, label_values=[disk_name, 'total']))
            data.add(Value(usage.used, label_values=[disk_name, 'used']))
            data.add(Value(usage.free, label_values=[disk_name, 'free']))

        return data

    @staticmethod
    def sanitize_disk_name(disk: str):
        disk = disk.replace('\\', '/')
        disk = disk.replace(':', '')
        if disk.startswith('/'):
            # Most likely a linux path
            return disk.replace('/', '_')
        # Windows path - remove all slashes as we only use the drive letter as name
        return disk.replace('/', '')
