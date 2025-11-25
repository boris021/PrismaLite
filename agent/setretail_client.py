# agent/setretail_client.py

import base64
import requests
from lxml import etree

class SetRetailClient:
    def __init__(self, host: str):
        self.endpoint = f"http://{host}:8090/SET-ERPIntegration/FiscalInfoExport"

    def get_purchases_by_operday(self, date_operday: str) -> str:
        """
        Возвращает XML чеков как строку.
        """
        soap_xml = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                          xmlns:plug="http://plugins.operday.ERPIntegration.crystals.ru/">
          <soapenv:Header/>
          <soapenv:Body>
            <plug:getPurchasesByOperDay>
              <dateOperDay>{date_operday}</dateOperDay>
            </plug:getPurchasesByOperDay>
          </soapenv:Body>
        </soapenv:Envelope>
        """

        headers = {"Content-Type": "text/xml; charset=utf-8"}
        resp = requests.post(self.endpoint, data=soap_xml.encode("utf-8"), headers=headers)
        resp.raise_for_status()

        # внутри SOAP находится base64 XML
        tree = etree.fromstring(resp.content)
        b64 = tree.xpath("//*[local-name()='return']/text()")[0]
        xml_raw = base64.b64decode(b64).decode("utf-8")
        return xml_raw
