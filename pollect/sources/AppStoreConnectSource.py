import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from appstoreconnect.api import APIError

from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from appstoreconnect import Api


class ProdTypeIds:
    IN_APP_PURCHASE = 'IA1'
    UPDATE_UNIVERSAL = '7F'
    REDOWNLOAD_UNIVERSAL = '3F'
    FREE_OR_PAID_UNIVERSAL = '1F'

    @staticmethod
    def is_download(p_id: str) -> bool:
        """
        Checks if the given product type id is a download (excluding updates)
        """
        return p_id == ProdTypeIds.FREE_OR_PAID_UNIVERSAL

    @staticmethod
    def is_iap(p_id: str) -> bool:
        """
        Checks if the given product type id is a download (excluding updates)
        """
        return p_id == ProdTypeIds.IN_APP_PURCHASE


class SkuMetrics:
    def __init__(self, sku: str):
        self.sku = sku
        self.units = 0


class AppStoreConnectSource(Source):
    def __init__(self, config):
        super().__init__(config)
        self._key_id = config['keyId']
        self._key_file = config['keyFile']
        self._issuer_id = config['issuerId']
        self._vendor = config['vendorNumber']
        self._db_dir = config.get('dbDir', 'db')

    def _probe(self) -> Optional[ValueSet] or List[ValueSet]:
        self.log.info('Downloading AppStore report...')
        report_file = os.path.join(self._db_dir, 'report_' + self._vendor + '.csv')

        # The latest report is always 1 day old
        report_date = datetime.today() - timedelta(days=1)

        api = Api(self._key_id, self._key_file, self._issuer_id)
        try:
            api.download_sales_and_trends_reports(filters={
                'vendorNumber': self._vendor,
                'frequency': 'DAILY',
                'reportDate': report_date.strftime('%Y-%m-%d')},
                save_to=report_file)
        except APIError as e:
            if 'is not available yet' in str(e):
                # Ignore as the report is simply not yet available
                return None
            raise e

        with open(report_file, encoding='utf-8') as file:
            lines = file.readlines()

        if len(lines) < 2:
            return None

        sku_map = {}  # type: Dict[str, SkuMetrics]
        headline = lines[0].split('\t')
        sku_col = self._find_column('SKU', headline)
        prod_type_col = self._find_column('Product Type Identifier', headline)
        units_col = self._find_column('Units', headline)
        dev_proceeds_col = self._find_column('Developer Proceeds', headline)

        for line in lines[1:]:
            row = line.split('\t')
            sku = row[sku_col]
            if sku not in sku_map:
                sku_map[sku] = SkuMetrics(sku)
            sku_metrics = sku_map[sku]
            units = int(row[units_col])

            if ProdTypeIds.is_download(row[prod_type_col]) or \
                    ProdTypeIds.is_iap(row[prod_type_col]):
                # Only increment the unit counter if the
                # item was a download or IAP
                sku_metrics.units += units

        # Now create the metrics
        data = ValueSet(labels=['sku'])
        for sku, item in sku_map.items():
            data.add(Value(item.units, label_values=[sku], name='units'))

        meta_data = ValueSet()
        meta_data.add(Value(int(report_date.timestamp()), name='latestUpdate'))
        return [data, meta_data]

    @staticmethod
    def _find_column(name, headline):
        idx = 0
        for item in headline:
            if name == item:
                return idx
            idx += 1
        raise Exception('Column with name "' + name + '" not found')
