from pollect.libs.google.FileProvider import FileProvider


class MetaMetric:
    def __init__(self, gcs_name: str, export_name: str, file_provider: FileProvider):
        self.gcs_name = gcs_name
        self.export_name = export_name
        self.file_provider = file_provider
