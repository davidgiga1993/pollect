class AppConfig:
    def __init__(self, config):
        self.package = config.get('package')
        self.name = config.get('name', self.package)
